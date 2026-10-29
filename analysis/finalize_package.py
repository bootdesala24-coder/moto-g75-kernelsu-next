#!/usr/bin/env python3
"""Create the delivery ZIP from an explicit list of validated files."""
import argparse
import hashlib
import json
import zipfile
from pathlib import Path
from package_boot import EXPECTED, sha256

ROOT = Path(__file__).resolve().parents[1]
FILES = (
    'FONTES.txt', 'KernelSU_Next_v3.4.2_33355-release.apk', 'LEIA-ME.txt',
    'SHA256SUMS.txt', 'VALIDACAO.json', 'boot-kernelsu-next.img',
    'boot-magisk-backup-a.img', 'conferir-pacote.cmd',
    'init_boot-magisk-backup-a.img', 'init_boot-sem-magisk.img',
    'preparar-migracao.sh', 'restaurar-modulos-magisk.sh',
)


def main(folder, archive):
    for source, destination in [
        ('LEIA-ME-PACOTE.txt', 'LEIA-ME.txt'),
        ('conferir-pacote.cmd', 'conferir-pacote.cmd'),
        ('preparar-migracao.sh', 'preparar-migracao.sh'),
        ('restaurar-modulos-magisk.sh', 'restaurar-modulos-magisk.sh'),
    ]:
        text = (ROOT / 'windows' / source).read_text()
        if destination.endswith('.cmd'):
            text = text.replace('\n', '\r\n')
        (folder / destination).write_bytes(text.encode())
    for filename, original in [
        ('boot-magisk-backup-a.img', 'current_boot'),
        ('init_boot-magisk-backup-a.img', 'current_init'),
        ('init_boot-sem-magisk.img', 'stock_init'),
        ('KernelSU_Next_v3.4.2_33355-release.apk', 'manager'),
    ]:
        if sha256(folder / filename) != EXPECTED[original]:
            raise ValueError(f'Packaged file mismatch: {filename}')
    digests = {name: sha256(folder / name) for name in FILES if name != 'SHA256SUMS.txt'}
    (folder / 'SHA256SUMS.txt').write_text(''.join(f'{digest}  {name}\n' for name, digest in sorted(digests.items())))
    with zipfile.ZipFile(archive, 'w', zipfile.ZIP_DEFLATED, compresslevel=6) as zipped:
        for name in FILES:
            zipped.write(folder / name, name)
    with zipfile.ZipFile(archive) as zipped:
        if zipped.namelist() != list(FILES) or zipped.testzip() is not None:
            raise ValueError('Unexpected ZIP contents or CRC error')
        for name, digest in digests.items():
            with zipped.open(name) as stream:
                if hashlib.file_digest(stream, 'sha256').hexdigest() != digest:
                    raise ValueError(f'ZIP member digest mismatch: {name}')
    report = {'file_name': archive.name, 'size': archive.stat().st_size,
              'sha256': sha256(archive), 'files': list(FILES),
              'boot_sha256': digests['boot-kernelsu-next.img'], 'device_boot_test_passed': False}
    (ROOT / 'docs/delivery-package.json').write_text(json.dumps(report, indent=2) + '\n')
    print(json.dumps(report, indent=2))


if __name__ == '__main__':
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument('--folder', required=True, type=Path)
    parser.add_argument('--archive', required=True, type=Path)
    args = parser.parse_args()
    main(args.folder, args.archive)
