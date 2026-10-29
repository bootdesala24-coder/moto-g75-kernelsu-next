import json
import struct
import sys
import tempfile
import unittest
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parents[1] / "scripts"))
from validate import (check_config, check_image, check_module_trust, compare,
                      reference_module_material, symbols, validate_inputs)

REQUIRED = ("ARM64", "ARM64_4K_PAGES", "KPROBES", "EXT4_FS", "MODULES", "MODVERSIONS",
            "CFI_CLANG", "LTO_NONE", "SECURITY_SELINUX", "SECURITY",
            "HARDENED_USERCOPY", "FORTIFY_SOURCE", "MODULE_SIG", "MODULE_SIG_ALL",
            "MODULE_SIG_PROTECT", "MODULE_SIG_SHA1", "SYSTEM_TRUSTED_KEYRING",
            "TRIM_UNUSED_KSYMS")


def required_config():
    return ("".join(f"CONFIG_{name}=y\n" for name in REQUIRED)
            + 'CONFIG_SYSTEM_TRUSTED_KEYS="certs/upstream-gki.pem"\n'
            + 'CONFIG_UNUSED_KSYMS_WHITELIST="abi_symbollist.raw"\n')


class ValidationTests(unittest.TestCase):
    def test_inputs_are_consistent_but_not_hardware_validated(self):
        _, device = validate_inputs()
        self.assertFalse(device["exact_source_match_verified"])
        self.assertFalse(device["device_boot_test_passed"])

    def test_image_checks_page_size_and_allows_bss_memory_footprint(self):
        with tempfile.TemporaryDirectory() as temp:
            path = Path(temp) / "Image"
            raw = bytearray(128)
            raw[56:60] = b"ARM\x64"
            struct.pack_into("<QQ", raw, 16, 128, 2)
            path.write_bytes(raw)
            self.assertEqual(check_image(path)["page_size"], 4096)
            struct.pack_into("<Q", raw, 24, 4)  # 16 KB
            path.write_bytes(raw)
            with self.assertRaises(ValueError):
                check_image(path)
            struct.pack_into("<QQ", raw, 16, 256, 2)
            path.write_bytes(raw)
            self.assertEqual(check_image(path)["memory_footprint"], 256)
            struct.pack_into("<Q", raw, 16, 64)
            path.write_bytes(raw)
            with self.assertRaises(ValueError):
                check_image(path)
            path.write_bytes(raw[:32])
            with self.assertRaises(ValueError):
                check_image(path)

    def test_image_rejects_non_arm64_and_big_endian(self):
        with tempfile.TemporaryDirectory() as temp:
            path = Path(temp) / "Image"
            path.write_bytes(b"\x7fELF" + bytes(124))
            with self.assertRaises(ValueError):
                check_image(path)
            raw = bytearray(128)
            raw[56:60] = b"ARM\x64"
            struct.pack_into("<QQ", raw, 16, 128, 3)
            path.write_bytes(raw)
            with self.assertRaises(ValueError):
                check_image(path)

    def test_comparison_detects_crc_removal_and_configuration_changes(self):
        with tempfile.TemporaryDirectory() as temp:
            a, b = Path(temp) / "a", Path(temp) / "b"
            a.mkdir()
            b.mkdir()
            cfg = required_config()
            (a / "kernel.config").write_text(cfg)
            (b / "kernel.config").write_text(cfg + "CONFIG_KSU=y\n")
            syms = "0x12345678\tfoo\tvmlinux\tEXPORT_SYMBOL\n"
            (a / "Module.symvers").write_text(syms)
            (b / "Module.symvers").write_text(syms)
            report = compare(a, b)
            self.assertTrue(report["passed"])
            self.assertFalse(report["installable"])
            (b / "Module.symvers").write_text(syms.replace("12345678", "87654321"))
            self.assertEqual(compare(a, b)["changed"], ["foo"])
            (b / "Module.symvers").write_text(syms.replace("foo", "bar"))
            self.assertEqual(compare(a, b)["removed"], ["foo"])
            (b / "Module.symvers").write_text(syms)
            (b / "kernel.config").write_text(cfg + "CONFIG_KSU=y\nCONFIG_SMP=y\n")
            self.assertFalse(compare(a, b)["passed"])

    def test_empty_or_duplicate_symbols_fail_closed(self):
        with tempfile.TemporaryDirectory() as temp:
            path = Path(temp) / "Module.symvers"
            for text in ("", "garbage\n", "0x12345678 foo vmlinux EXPORT_SYMBOL\n" * 2):
                path.write_text(text)
                with self.assertRaises(ValueError):
                    symbols(path)

    def test_module_protection_cannot_be_disabled(self):
        with tempfile.TemporaryDirectory() as temp:
            path = Path(temp) / "config"
            for setting in ("MODULE_SIG", "MODULE_SIG_PROTECT", "SYSTEM_TRUSTED_KEYRING"):
                path.write_text(required_config().replace(f"CONFIG_{setting}=y", f"CONFIG_{setting}=n"))
                with self.assertRaises(ValueError):
                    check_config(path, "reference")
            path.write_text(required_config().replace('"certs/upstream-gki.pem"', '""'))
            with self.assertRaises(ValueError):
                check_config(path, "reference")

    def test_pinned_reference_material_rejects_corruption(self):
        import copy
        import hashlib
        raw = b"certificate|unprotected|protected"
        ref = {"kernel_sha256": hashlib.sha256(raw).hexdigest(), "module_trust": {}}
        offset = 0
        for name, data in zip(("certificate", "unprotected", "protected_exports"), raw.split(b"|")):
            ref["module_trust"][name] = {"offset": offset, "size": len(data),
                                          "sha256": hashlib.sha256(data).hexdigest()}
            offset += len(data) + 1
        self.assertEqual(reference_module_material(raw, ref)["certificate"], b"certificate")
        with self.assertRaises(ValueError):
            reference_module_material(raw + b"changed", ref)
        changed = copy.deepcopy(ref)
        changed["module_trust"]["certificate"]["offset"] += 1
        with self.assertRaises(ValueError):
            reference_module_material(raw, changed)

    def test_certificate_must_be_in_linked_keyring_and_tables_must_match(self):
        with tempfile.TemporaryDirectory() as temp:
            image, syms = Path(temp) / "Image", Path(temp) / "System.map"
            raw = bytearray(512)
            material = {"certificate": b"PUBLIC-CERT", "unprotected": b"foo\0bar\0",
                        "protected_exports": b"baz\0"}
            sizes = {"gki_unprotected_symbols": 8, "gki_protected_exports_symbols": 4}
            raw[128:139] = material["certificate"]
            struct.pack_into("<Q", raw, 192, 32)
            raw[256:264] = material["unprotected"]
            raw[300:304] = material["protected_exports"]
            syms.write_text("1000 T _text\n1080 D system_certificate_list\n"
                            "10c0 D system_certificate_list_size\n"
                            "1100 d gki_unprotected_symbols\n"
                            "112c d gki_protected_exports_symbols\n")
            image.write_bytes(raw)
            self.assertTrue(check_module_trust(image, syms, material, sizes)["original_certificate_in_builtin_keyring"])
            with self.assertRaises(ValueError):
                check_module_trust(image, syms, material, dict(sizes, gki_unprotected_symbols=12))
            # A certificate elsewhere in Image does not make it a trusted key.
            raw[400:411], raw[128:139] = material["certificate"], bytes(11)
            image.write_bytes(raw)
            with self.assertRaises(ValueError):
                check_module_trust(image, syms, material, sizes)
            raw[128:139] = material["certificate"]
            raw[300] ^= 1
            image.write_bytes(raw)
            with self.assertRaises(ValueError):
                check_module_trust(image, syms, material, sizes)


if __name__ == "__main__":
    unittest.main()
