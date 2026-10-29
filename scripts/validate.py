#!/usr/bin/env python3
"""Offline checks. A pass is never an authorization to flash a phone."""
import argparse
import hashlib
import json
import re
import struct
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]


def read_json(path):
    return json.loads(Path(path).read_text())


def validate_inputs(root=ROOT):
    lock = read_json(root / "sources.lock.json")
    device = read_json(root / "device.json")
    for key in ("kernel", "kernelsu"):
        if not re.fullmatch(r"[0-9a-f]{40}", lock[key]["commit"]):
            raise ValueError(f"Unpinned {key} commit")
    for key in ("repository_commit", "directory_tree"):
        if not re.fullmatch(r"[0-9a-f]{40}", lock["clang"][key]):
            raise ValueError(f"Unpinned clang {key}")
    if lock["kernel"]["kmi"] != device["kmi"]:
        raise ValueError("Source KMI family differs from observed device")
    if lock["kernel"]["version"] != device["kernel_release"].split("-")[0]:
        raise ValueError("Source kernel version differs from observed device")
    if device["page_size_expected"] != 4096:
        raise ValueError("This experiment targets 4 KB pages only")
    return lock, device


def check_image(path):
    path = Path(path)
    with path.open("rb") as stream:
        header = stream.read(64)
    if len(header) != 64 or header[56:60] != b"ARM\x64":
        raise ValueError("Not a raw ARM64 Linux Image")
    size, flags = struct.unpack_from("<QQ", header, 16)
    if flags & 1:
        raise ValueError("Big-endian Image is not supported")
    if (flags >> 1) & 3 != 1:
        raise ValueError("Image does not declare 4 KB pages")
    if not 64 <= size <= path.stat().st_size:
        raise ValueError("Invalid or truncated Image size")
    return {"architecture": "arm64", "page_size": 4096, "image_size": size}


def config(path):
    result = {}
    for line in Path(path).read_text().splitlines():
        if line.startswith("CONFIG_") and "=" in line:
            key, value = line.split("=", 1)
            result[key] = value
        elif line.startswith("# CONFIG_") and line.endswith(" is not set"):
            result[line[2:-11]] = "n"
    return result


def check_config(path, variant):
    cfg = config(path)
    for name in ("ARM64", "ARM64_4K_PAGES", "KPROBES", "EXT4_FS", "MODULES",
                 "MODVERSIONS", "CFI_CLANG", "LTO_CLANG_THIN", "SECURITY_SELINUX",
                 "SECURITY", "HARDENED_USERCOPY", "FORTIFY_SOURCE"):
        if cfg.get("CONFIG_" + name) != "y":
            raise ValueError(f"Missing required CONFIG_{name}=y")
    if cfg.get("CONFIG_KSU", "n") != ("y" if variant == "kernelsu-next" else "n"):
        raise ValueError("Unexpected KernelSU configuration")
    for name in ("KSU_DEBUG", "KSU_DISABLE_MANAGER", "KSU_DISABLE_POLICY"):
        if cfg.get("CONFIG_" + name, "n") != "n":
            raise ValueError(f"Unsafe experimental setting CONFIG_{name}")
    return cfg


def symbols(path):
    result = {}
    for line in Path(path).read_text().splitlines():
        cols = line.split()
        if len(cols) < 4 or not re.fullmatch(r"0x[0-9a-fA-F]{8}", cols[0]):
            raise ValueError("Malformed Module.symvers")
        crc, name, module, export = cols[:4]
        if name in result:
            raise ValueError(f"Duplicate exported symbol: {name}")
        result[name] = {"crc": crc.lower(), "export": export,
                        "namespace": cols[4] if len(cols) > 4 else ""}
    if not result:
        raise ValueError("Empty Module.symvers")
    return result


def compare(reference, modified):
    reference, modified = Path(reference), Path(modified)
    a = symbols(reference / "Module.symvers")
    b = symbols(modified / "Module.symvers")
    removed = sorted(set(a) - set(b))
    changed = sorted(key for key in a.keys() & b.keys() if a[key] != b[key])
    added = sorted(set(b) - set(a))
    ca = check_config(reference / "kernel.config", "reference")
    cb = check_config(modified / "kernel.config", "kernelsu-next")
    differences = {key: [ca.get(key, "n"), cb.get(key, "n")]
                   for key in ca.keys() | cb.keys()
                   if ca.get(key, "n") != cb.get(key, "n")}
    unexpected = {key: value for key, value in differences.items()
                  if not key.startswith("CONFIG_KSU")}
    report = {"passed": not (removed or changed or unexpected),
              "reference_symbols": len(a), "modified_symbols": len(b),
              "removed": removed, "changed": changed, "added": added,
              "config_changes": differences,
              "unexpected_config_changes": unexpected,
              "vendor_abi_verified": False, "device_tested": False,
              "installable": False,
              "scope": "Comparison against a locally compiled GKI reference, not the installed Motorola kernel"}
    return report


def sha256(path):
    with Path(path).open("rb") as stream:
        return hashlib.file_digest(stream, "sha256").hexdigest()


if __name__ == "__main__":
    parser = argparse.ArgumentParser()
    parser.add_argument("--inputs", action="store_true")
    parser.add_argument("--compare", nargs=2, type=Path)
    args = parser.parse_args()
    if args.inputs:
        validate_inputs()
        print("Input consistency OK; exact firmware/source correspondence remains unverified.")
    elif args.compare:
        report = compare(*args.compare)
        print(json.dumps(report, indent=2, sort_keys=True))
        raise SystemExit(0 if report["passed"] else 1)
    else:
        parser.error("Choose --inputs or --compare")
