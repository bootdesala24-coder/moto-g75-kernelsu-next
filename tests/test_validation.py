import json
import struct
import sys
import tempfile
import unittest
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parents[1] / "scripts"))
from validate import check_image, compare, symbols, validate_inputs

REQUIRED = ("ARM64", "ARM64_4K_PAGES", "KPROBES", "EXT4_FS", "MODULES", "MODVERSIONS",
            "CFI_CLANG", "LTO_NONE", "SECURITY_SELINUX", "SECURITY",
            "HARDENED_USERCOPY", "FORTIFY_SOURCE")


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
            cfg = "".join(f"CONFIG_{name}=y\n" for name in REQUIRED)
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


if __name__ == "__main__":
    unittest.main()
