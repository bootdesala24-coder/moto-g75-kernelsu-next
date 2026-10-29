import json
import tempfile
import unittest
from pathlib import Path

from verify_device_modules import verify


class DeviceModuleChecks(unittest.TestCase):
    def test_rejects_abi_namespace_license_and_vermagic_regressions(self):
        with tempfile.TemporaryDirectory() as directory:
            root = Path(directory)
            requirements = {'required_core_export_count': 1, 'module_file_records': 1,
                            'unique_module_hashes': 1, 'vermagic_suffix': ' SMP aarch64',
                            'required_core_exports': {'driver_api': {
                                'crc': '0x12345678', 'allowed_namespaces': ['ALLOWED'],
                                'all_consumers_gpl_compatible': False}}}
            (root / 'provenance.json').write_text(json.dumps({
                'kernel_release': 'test-kernel', 'workflow_commit': 'test',
                'run_id': 'test', 'variant': 'test'}))
            (root / 'Image').write_bytes(b'test-kernel SMP aarch64\0')
            good = '0x12345678\tdriver_api\tvmlinux\tEXPORT_SYMBOL\tALLOWED\n'
            (root / 'Module.symvers').write_text(good)
            self.assertTrue(verify(root, requirements)['static_core_module_checks_passed'])
            for changed in (good.replace('12345678', '87654321'),
                            good.replace('driver_api', 'missing_api'),
                            good.replace('vmlinux', 'some/module'),
                            good.replace('ALLOWED', 'UNDECLARED'),
                            good.replace('EXPORT_SYMBOL', 'EXPORT_SYMBOL_GPL')):
                (root / 'Module.symvers').write_text(changed)
                self.assertFalse(verify(root, requirements)['static_core_module_checks_passed'])
            (root / 'Module.symvers').write_text(good)
            (root / 'Image').write_bytes(b'test-kernel incompatible-magic\0')
            self.assertFalse(verify(root, requirements)['static_core_module_checks_passed'])


if __name__ == '__main__':
    unittest.main()
