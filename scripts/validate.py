#!/usr/bin/env python3
"""Offline checks. A pass is never an authorization to flash a phone."""
import argparse
import hashlib
import json
import re
import struct
import zipfile
import zlib
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
    observed = re.search(r"-g([0-9a-f]+)-ab([0-9]+)-", device["kernel_release"])
    if not observed or not lock["kernel"]["commit"].startswith(observed[1]):
        raise ValueError("Pinned source does not match the observed kernel commit")
    if lock["kernel"]["upstream_build_id"] != observed[2]:
        raise ValueError("Upstream build ID does not match the observed kernel")
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
    # image_size is the memory footprint (_end - _text), including BSS;
    # it can legitimately exceed the length of the on-disk Image.
    if size < path.stat().st_size or size < 64:
        raise ValueError("Image memory footprint is smaller than its file")
    return {"architecture": "arm64", "page_size": 4096,
            "memory_footprint": size, "file_size": path.stat().st_size}


def reference_kernel(archive, reference):
    if sha256(archive) != reference["archive_sha256"]:
        raise ValueError("Official reference archive digest mismatch")
    with zipfile.ZipFile(archive) as zipped:
        boot = zipped.read("boot-6.6.img")
    if boot[:8] != b"ANDROID!" or struct.unpack_from("<I", boot, 40)[0] != 4:
        raise ValueError("Unexpected reference boot header")
    size = struct.unpack_from("<I", boot, 8)[0]
    kernel = boot[4096:4096 + size]
    if hashlib.sha256(kernel).hexdigest() != reference["kernel_sha256"]:
        raise ValueError("Official reference kernel digest mismatch")
    return kernel


def reference_config(archive, reference):
    kernel = reference_kernel(archive, reference)
    pos = kernel.find(b"IKCFG_ST")
    if pos == -1:
        raise ValueError("Official kernel does not contain IKCONFIG")
    cfg = zlib.decompress(kernel[pos + 8:], wbits=31)
    if hashlib.sha256(cfg).hexdigest() != reference["config_sha256"]:
        raise ValueError("Official reference configuration digest mismatch")
    return cfg.decode()


def reference_module_material(kernel, reference):
    """Extract only pinned public data from the authenticated reference bytes."""
    if hashlib.sha256(kernel).hexdigest() != reference["kernel_sha256"]:
        raise ValueError("Reference kernel digest mismatch for module trust")
    material = {}
    for name in ("certificate", "unprotected", "protected_exports"):
        entry = reference["module_trust"][name]
        start, size = entry["offset"], entry["size"]
        if start < 0 or size <= 0 or start + size > len(kernel):
            raise ValueError(f"Invalid reference range: {name}")
        data = kernel[start:start + size]
        if hashlib.sha256(data).hexdigest() != entry["sha256"]:
            raise ValueError(f"Reference module trust digest mismatch: {name}")
        material[name] = data
    return material


def check_module_trust(image, system_map, material, table_sizes):
    """Check trusted certificate and protection tables at their linked addresses."""
    raw = Path(image).read_bytes()
    required = {"_text", "system_certificate_list", "system_certificate_list_size",
                "gki_unprotected_symbols", "gki_protected_exports_symbols"}
    addresses = {}
    for line in Path(system_map).read_text().splitlines():
        fields = line.split()
        if len(fields) == 3 and fields[2] in required:
            if fields[2] in addresses:
                raise ValueError(f"Ambiguous linked symbol: {fields[2]}")
            addresses[fields[2]] = int(fields[0], 16)
    if addresses.keys() != required:
        raise ValueError("Missing linked symbols for module trust verification")

    def read_at(name, size):
        offset = addresses[name] - addresses["_text"]
        if offset < 0 or size <= 0 or offset + size > len(raw):
            raise ValueError(f"Linked data outside Image: {name}")
        return raw[offset:offset + size]

    size = struct.unpack("<Q", read_at("system_certificate_list_size", 8))[0]
    cert = material["certificate"]
    if not cert or cert not in read_at("system_certificate_list", size):
        raise ValueError("Original module certificate missing from builtin trusted keyring")
    for name in ("unprotected", "protected_exports"):
        expected = material[name]
        if table_sizes.get(f"gki_{name}_symbols") != len(expected):
            raise ValueError(f"Module protection table size differs from reference: {name}")
        if not expected or read_at(f"gki_{name}_symbols", len(expected)) != expected:
            raise ValueError(f"Module protection table differs from reference: {name}")
    return {"original_certificate_in_builtin_keyring": True,
            "unprotected_table_matches_original": True,
            "protected_exports_table_matches_original": True,
            "original_certificate_sha256": hashlib.sha256(cert).hexdigest(),
            "scope": "Static trust and symbol-policy checks; actual device modules and hardware remain untested"}


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
                 "MODVERSIONS", "CFI_CLANG", "LTO_NONE", "SECURITY_SELINUX",
                 "SECURITY", "HARDENED_USERCOPY", "FORTIFY_SOURCE", "MODULE_SIG",
                 "MODULE_SIG_ALL", "MODULE_SIG_PROTECT", "MODULE_SIG_SHA1",
                 "SYSTEM_TRUSTED_KEYRING", "TRIM_UNUSED_KSYMS"):
        if cfg.get("CONFIG_" + name) != "y":
            raise ValueError(f"Missing required CONFIG_{name}=y")
    if cfg.get("CONFIG_SYSTEM_TRUSTED_KEYS") != '"certs/upstream-gki.pem"':
        raise ValueError("Original module certificate is not configured as trusted")
    if cfg.get("CONFIG_UNUSED_KSYMS_WHITELIST") != '"abi_symbollist.raw"':
        raise ValueError("Unexpected module symbol whitelist")
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
        print("Input consistency and upstream identity OK; rebuilt-kernel module compatibility and hardware remain unverified.")
    elif args.compare:
        report = compare(*args.compare)
        print(json.dumps(report, indent=2, sort_keys=True))
        raise SystemExit(0 if report["passed"] else 1)
    else:
        parser.error("Choose --inputs or --compare")
