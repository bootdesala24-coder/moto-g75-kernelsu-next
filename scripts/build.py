#!/usr/bin/env python3
"""Build an explicitly non-installable GKI experiment from pinned sources."""
import argparse
import json
import os
import re
import shutil
import subprocess
import tarfile
from pathlib import Path

from validate import ROOT, check_config, check_image, sha256, validate_inputs


def run(*args, cwd=None, env=None, capture=False):
    print("+", " ".join(map(str, args)), flush=True)
    result = subprocess.run(list(map(str, args)), cwd=cwd, env=env, check=True,
                            text=True, stdout=subprocess.PIPE if capture else None)
    return result.stdout.strip() if capture else ""


def checkout(url, commit, destination, full=False):
    if destination.exists():
        raise ValueError(f"Refusing to reuse existing source directory: {destination}")
    if full:
        run("git", "clone", "--no-checkout", url, destination)
    else:
        run("git", "init", destination)
        run("git", "remote", "add", "origin", url, cwd=destination)
        run("git", "fetch", "--depth=1", "origin", commit, cwd=destination)
    run("git", "checkout", "--detach", commit, cwd=destination)
    if run("git", "rev-parse", "HEAD", cwd=destination, capture=True) != commit:
        raise ValueError("Checked-out source commit mismatch")


def json_write(path, data):
    path.write_text(json.dumps(data, indent=2, sort_keys=True) + "\n")


def main(variant):
    lock, device = validate_inputs()
    work = ROOT / "work" / variant
    work.mkdir(parents=True, exist_ok=False)
    artifacts = ROOT / "artifacts" / variant
    artifacts.mkdir(parents=True, exist_ok=True)
    source, ksu = work / "linux", work / "KernelSU-Next"
    output, compiler = work / "out", work / "clang"
    report = {"variant": variant, "build_succeeded": False, "installable": False,
              "device_tested": False, "vendor_abi_verified": False,
              "source_tag": lock["kernel"]["tag"],
              "observed_kernel_identifiers_match_upstream": True,
              "target_firmware": device["firmware"],
              "exact_source_match_verified": False, "sources": lock,
              "workflow_commit": os.environ.get("GITHUB_SHA"),
              "run_id": os.environ.get("GITHUB_RUN_ID")}
    json_write(artifacts / "provenance.json", report)
    (artifacts / "DO-NOT-FLASH.txt").write_text(
        "EXPERIMENTAL BUILD — NOT AN INSTALLATION PACKAGE\n"
        "Source: android15-6.6-2025-05_r19; target firmware: W1UQ36H.73-38.\n"
        "Source commit and upstream build ID match the photographed kernel release.\n"
        "The exact installed kernel and vendor modules have not been validated.\n"
        "No boot.img, init_boot.img, AnyKernel ZIP or flashing command is supplied.\n"
        "A successful build does not establish device compatibility or security.\n")
    shutil.copy2(ROOT / "device.json", artifacts)
    shutil.copy2(ROOT / "sources.lock.json", artifacts)
    checkout(lock["kernel"]["url"], lock["kernel"]["commit"], source)

    makefile = (source / "Makefile").read_text()
    version = ".".join(re.search(rf"^{part}\s*=\s*(\d+)$", makefile, re.M)[1]
                       for part in ("VERSION", "PATCHLEVEL", "SUBLEVEL"))
    common = (source / "build.config.common").read_text()
    constants = (source / "build.config.constants").read_text()
    if version != lock["kernel"]["version"]:
        raise ValueError("Unexpected kernel source version")
    if not re.search(r"^KMI_GENERATION=8$", common, re.M):
        raise ValueError("Unexpected KMI generation")
    if not re.search(r"^BRANCH=android15-6.6$", common, re.M):
        raise ValueError("Unexpected KMI branch")
    if f"CLANG_VERSION={lock['clang']['version']}\n" not in constants:
        raise ValueError("Toolchain does not match source build configuration")

    archive = work / "clang.tar.gz"
    run("curl", "--fail", "--location", "--retry", "3", "--retry-delay", "5",
        "--connect-timeout", "30", "--max-time", "1200", "--output", archive,
        lock["clang"]["archive"])
    report["compiler_archive_sha256"] = sha256(archive)
    compiler.mkdir()
    with tarfile.open(archive, "r:gz") as tar:
        tar.extractall(compiler, filter="data")
    # Verify all compiler files against the upstream Git tree BEFORE execution.
    run("git", "init", compiler)
    run("git", "config", "core.autocrlf", "false", cwd=compiler)
    run("git", "config", "core.filemode", "true", cwd=compiler)
    run("git", "add", "--all", "--force", cwd=compiler)
    compiler_tree = run("git", "write-tree", cwd=compiler, capture=True)
    if compiler_tree != lock["clang"]["directory_tree"]:
        raise ValueError(f"Compiler Git tree mismatch: {compiler_tree}")
    report["compiler_tree_verified"] = compiler_tree
    archive.unlink()
    env = dict(os.environ)
    env["PATH"] = str(compiler / "bin") + os.pathsep + env["PATH"]
    epoch = run("git", "show", "-s", "--format=%ct", "HEAD", cwd=source, capture=True)
    env.update(SOURCE_DATE_EPOCH=epoch, KBUILD_BUILD_TIMESTAMP="@" + epoch,
               KBUILD_BUILD_USER="kernel-lab", KBUILD_BUILD_HOST="github-actions",
               KBUILD_BUILD_VERSION="1", KCONFIG_NOTIMESTAMP="1")
    report["clang_version"] = run("clang", "--version", env=env, capture=True)
    report["host_packages"] = run("dpkg-query", "-W", "-f=${Package}=${Version}\n",
                                  capture=True).splitlines()
    json_write(artifacts / "provenance.json", report)

    if variant == "kernelsu-next":
        checkout(lock["kernelsu"]["url"], lock["kernelsu"]["commit"], ksu, full=True)
        tag_commit = run("git", "rev-parse", lock["kernelsu"]["tag"] + "^{commit}",
                         cwd=ksu, capture=True)
        if tag_commit != lock["kernelsu"]["commit"]:
            raise ValueError("KernelSU release tag moved")
        (source / "drivers/kernelsu").symlink_to("../../KernelSU-Next/kernel")
        with (source / "drivers/Makefile").open("a") as stream:
            stream.write("\nobj-$(CONFIG_KSU) += kernelsu/\n")
        with (source / "drivers/Kconfig").open("a") as stream:
            stream.write('\nsource "drivers/kernelsu/Kconfig"\n')
        report["ksu_commit_count"] = run("git", "rev-list", "--count", "HEAD",
                                          cwd=ksu, capture=True)

    make = ["make", "-C", source, f"O={output}", "ARCH=arm64", "LLVM=1",
            "LLVM_IAS=1", "CROSS_COMPILE=aarch64-linux-gnu-", "LOCALVERSION=",
            "KCFLAGS=-D__ANDROID_COMMON_KERNEL__"]
    run(*make, "gki_defconfig", env=env)
    config = output / ".config"
    shutil.copy2(config, artifacts / "initial-gki.config")
    cfgargs = [source / "scripts/config", "--file", config,
               "--set-str", "LOCALVERSION", "-android15-8-lab-4k",
               "--disable", "LOCALVERSION_AUTO", "--disable", "LTO_NONE",
               "--enable", "LTO_CLANG", "--enable", "LTO_CLANG_THIN"]
    if variant == "kernelsu-next":
        cfgargs += ["--enable", "KSU", "--disable", "KSU_DEBUG",
                    "--disable", "KSU_DISABLE_MANAGER", "--disable", "KSU_DISABLE_POLICY"]
    run(*cfgargs, env=env)
    run(*make, "olddefconfig", env=env)
    check_config(config, variant)
    shutil.copy2(config, artifacts / "kernel.config")
    (artifacts / "source-integration.diff").write_text(
        run("git", "diff", "--no-ext-diff", cwd=source, capture=True) + "\n")
    jobs = min(os.cpu_count() or 2, 4)
    run(*make, f"-j{jobs}", "Image", "Image.gz", "Image.lz4", "modules", env=env)
    image = output / "arch/arm64/boot/Image"
    report["image_checks"] = check_image(image)
    check_config(config, variant)
    release = (output / "include/config/kernel.release").read_text().strip()
    if release != "6.6.87-android15-8-lab-4k":
        raise ValueError(f"Unexpected kernel release: {release}")
    report["kernel_release"] = release
    symbol_map = (output / "System.map").read_text()
    has_ksu = bool(re.search(r"\bkernelsu_init(?:\.|$)", symbol_map, re.M))
    if has_ksu != (variant == "kernelsu-next"):
        raise ValueError("KernelSU built-in symbol presence does not match variant")
    for name in ("Image", "Image.gz", "Image.lz4"):
        shutil.copy2(output / "arch/arm64/boot" / name, artifacts / name)
    for name in ("Module.symvers", "System.map"):
        shutil.copy2(output / name, artifacts / name)
    shutil.copy2(config, artifacts / "kernel.config")
    report["build_succeeded"] = True
    report["builtin_kernelsu_symbol_present"] = has_ksu
    json_write(artifacts / "provenance.json", report)
    (artifacts / "SHA256SUMS").write_text("".join(
        f"{sha256(path)}  {path.name}\n"
        for path in sorted(artifacts.iterdir()) if path.is_file() and path.name != "SHA256SUMS"))
    print("Build verified as an EXPERIMENT. Device compatibility is NOT established.")


if __name__ == "__main__":
    parser = argparse.ArgumentParser()
    parser.add_argument("variant", choices=("reference", "kernelsu-next"))
    main(parser.parse_args().variant)
