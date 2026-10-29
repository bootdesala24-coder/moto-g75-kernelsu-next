"""Exercise file preservation with mock phone properties in a temporary directory."""
import os
import subprocess
import tempfile
import unittest
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]


class MigrationScripts(unittest.TestCase):
    def test_guards_backup_repeat_and_non_overwriting_restore(self):
        with tempfile.TemporaryDirectory(dir=ROOT) as directory:
            work = Path(directory)
            data = work / 'data-adb'
            data.mkdir()
            bins = work / 'mock-bin'
            bins.mkdir()
            mocks = {
                'id': '#!/bin/sh\necho 0\n',
                'getprop': '''#!/bin/sh
case "$1" in
ro.boot.hardware.sku) if [ "${G75_BAD_SKU:-0}" = 1 ]; then echo WRONG; else echo XT2437-1; fi;;
ro.build.display.id) echo W1UQ36H.73-38;;
ro.boot.slot_suffix) echo _a;;
esac
''',
                'sha256sum': '''#!/bin/sh
case "$1" in
*/boot_a) echo '55c2ccece3ef93e0daba10a8b8a9332f83d3dcf6437cfaa973678851776c4c71  boot_a';;
*/init_boot_a) echo 'eaaa88a4d55572e34510fba22066f7f9c4eb3837fb463b63e9221680fad8514c  init_boot_a';;
esac
''',
            }
            for name, contents in mocks.items():
                path = bins / name
                path.write_text(contents)
                path.chmod(0o755)
            scripts = {}
            for name in ('preparar-migracao.sh', 'restaurar-modulos-magisk.sh'):
                path = work / name
                path.write_text((ROOT / 'windows' / name).read_text().replace('/data/adb', str(data)))
                scripts[name] = path
            env = dict(os.environ, PATH=str(bins) + os.pathsep + os.environ['PATH'])
            folders = ('modules', 'modules_update', 'post-fs-data.d', 'service.d', 'post-mount.d', 'boot-completed.d')
            for name in folders:
                (data / name).mkdir()
                (data / name / 'preserve.txt').write_text('original:' + name)
            run = lambda name, e=env: subprocess.run(['sh', str(scripts[name])], env=e,
                                                     capture_output=True, text=True)
            backup = data / 'g75-magisk-backup-20261029'
            self.assertNotEqual(run('preparar-migracao.sh', dict(env, G75_BAD_SKU='1')).returncode, 0)
            self.assertFalse(backup.exists())
            self.assertEqual(run('preparar-migracao.sh').returncode, 0)
            self.assertNotEqual(run('preparar-migracao.sh').returncode, 0)
            for name in folders:
                self.assertFalse((data / name).exists())
                self.assertEqual((backup / name / 'preserve.txt').read_text(), 'original:' + name)
            (data / 'modules').mkdir()
            (data / 'modules' / 'new.txt').write_text('new data must survive')
            self.assertNotEqual(run('restaurar-modulos-magisk.sh').returncode, 0)
            self.assertEqual((data / 'modules' / 'new.txt').read_text(), 'new data must survive')
            (data / 'modules' / 'new.txt').unlink()
            self.assertEqual(run('restaurar-modulos-magisk.sh').returncode, 0)
            for name in folders:
                self.assertEqual((data / name / 'preserve.txt').read_text(), 'original:' + name)


if __name__ == '__main__':
    unittest.main()
