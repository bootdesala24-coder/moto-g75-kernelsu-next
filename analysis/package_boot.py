#!/usr/bin/env python3
"""Package a test candidate for the inspected XT2437-1, never flash a device."""
import argparse
import json
import shutil
import struct
import subprocess
import sys
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(ROOT / 'scripts'))
from validate import (check_config, check_image, check_module_trust, compare,
                      reference_kernel, reference_module_material, sha256)
from verify_device_modules import verify

EXPECTED = {
    'stock_boot': '6ae39d54a44b84cbf950d46749ccfec683a0fb922fa648a9136e0d10a6821b0e',
    'stock_init': '7746e1b3746360975563767f3af657ef47eaa4ab0eeb9c359cc38be94399b340',
    'current_boot': '55c2ccece3ef93e0daba10a8b8a9332f83d3dcf6437cfaa973678851776c4c71',
    'current_init': 'eaaa88a4d55572e34510fba22066f7f9c4eb3837fb463b63e9221680fad8514c',
    'manager': '774a5511f7034a4930e881114e202319cbdc34c5aaaa5c7c6b6d2902364e4c58',
    'avbtool': 'e5a664a38db623da00f080219bc0ee60a640a9dc4a872803616fae4938ac749b',
}


def inspect_build(path, variant):
    for line in (path / 'SHA256SUMS').read_text().splitlines():
        digest, name = line.split('  ', 1)
        if Path(name).name != name or sha256(path / name) != digest:
            raise ValueError(f'Artifact digest mismatch: {name}')
    provenance = json.loads((path / 'provenance.json').read_text())
    if provenance['variant'] != variant or not provenance['build_succeeded']:
        raise ValueError('Incomplete or unexpected build artifact')
    check_config(path / 'kernel.config', variant)
    check_image(path / 'Image')
    return provenance


def main(args):
    for name, digest in EXPECTED.items():
        if sha256(getattr(args, name)) != digest:
            raise ValueError(f'Unexpected input: {name}')
    lock = json.loads((ROOT / 'sources.lock.json').read_text())
    root = inspect_build(args.build_dir, 'kernelsu-next')
    baseline = inspect_build(args.reference_build, 'reference')
    if (root['workflow_commit'], root['run_id']) != (baseline['workflow_commit'], baseline['run_id']):
        raise ValueError('Build variants must come from the same workflow run and commit')
    if root['sources'] != lock or baseline['sources'] != lock:
        raise ValueError('Build sources differ from project pins')
    comparison = compare(args.reference_build, args.build_dir)
    if not comparison['passed'] or comparison['added']:
        raise ValueError('Build variants have unexpected ABI/configuration differences')
    material = reference_module_material(reference_kernel(args.reference_zip, lock['upstream_reference']),
                                         lock['upstream_reference'])
    trust = {}
    for label, build in [('reference', args.reference_build), ('kernelsu-next', args.build_dir)]:
        sizes = {}
        for line in (build / 'module-trust-symbols.txt').read_text().splitlines():
            fields = line.split()
            if len(fields) != 4 or fields[3] in sizes:
                raise ValueError('Malformed linked module policy symbols')
            sizes[fields[3]] = int(fields[1], 16)
        trust[label] = check_module_trust(build / 'Image', build / 'System.map', material, sizes)
    requirements = json.loads((ROOT / 'docs/device-module-requirements.json').read_text())
    modules = verify(args.build_dir, requirements)
    if not modules['static_core_module_checks_passed']:
        raise ValueError('Device module requirements failed')

    template = args.stock_boot.read_bytes()
    if (template[:8] != b'ANDROID!' or struct.unpack_from('<I', template, 40)[0] != 4
            or struct.unpack_from('<I', template, 12)[0] != 0
            or struct.unpack_from('<I', template, 20)[0] != 1584
            or struct.unpack_from('<I', template, 1580)[0] != 0):
        raise ValueError('Unexpected original boot layout')
    kernel = (args.build_dir / 'Image').read_bytes()
    header = bytearray(template[:4096])
    struct.pack_into('<I', header, 8, len(kernel))
    args.output_dir.mkdir(parents=True, exist_ok=False)
    boot = args.output_dir / 'boot.img'
    # Keep the original header fields, empty ramdisk and uncompressed kernel.
    # Discard obsolete signatures/descriptors rather than attach them to new bytes.
    boot.write_bytes(header + kernel + bytes((-len(kernel)) % 4096))
    inspection = json.loads((ROOT / 'docs/boot-image-inspection.json').read_text())
    command = [sys.executable, str(args.avbtool), 'add_hash_footer', '--image', str(boot),
               '--partition_name', 'boot', '--partition_size', str(len(template)),
               '--algorithm', 'NONE', '--hash_algorithm', 'sha256',
               '--salt', inspection['outer_hash_descriptors'][0]['salt']]
    for name, value in inspection['outer_avb_properties'].items():
        command += ['--prop', name + ':' + value]
    subprocess.run(command, check=True)
    checked = subprocess.run([sys.executable, str(args.avbtool), 'verify_image', '--image', str(boot)],
                             capture_output=True, text=True, check=True)
    image = boot.read_bytes()
    if len(image) != len(template) or image[4096:4096+len(kernel)] != kernel:
        raise ValueError('Packaged kernel or partition size differs')
    for i in range(4096):
        if not 8 <= i < 12 and image[i] != template[i]:
            raise ValueError('Unexpected change outside the kernel-size header field')
    boot.rename(args.output_dir / 'boot-kernelsu-next.img')
    for source, name in [
        (args.stock_init, 'init_boot-sem-magisk.img'),
        (args.current_boot, 'boot-magisk-backup-a.img'),
        (args.current_init, 'init_boot-magisk-backup-a.img'),
        (args.manager, 'KernelSU_Next_v3.4.2_33355-release.apk'),
    ]:
        shutil.copy2(source, args.output_dir / name)
    report = {'target': 'moto g75 XT2437-1 / sorap / W1UQ36H.73-38 / retbr / slot a',
              'kernel_release': root['kernel_release'], 'kernelsu_release': lock['kernelsu']['tag'],
              'workflow_commit': root['workflow_commit'], 'run_id': root['run_id'],
              'comparison': comparison, 'module_trust_checks': trust, 'device_module_checks': modules,
              'original_input_sha256': EXPECTED, 'boot_header_version': 4, 'ramdisk_size': 0,
              'kernel_compression': 'none', 'boot_partition_size': len(template),
              'outer_avb_algorithm': 'NONE', 'outer_avb_hash_verified': True,
              'outer_avb_verification_output': checked.stdout.strip(),
              'oem_signature': False, 'device_boot_test_passed': False,
              'delivery_status': 'Candidate for an owner-controlled hardware test; no guarantee of safe boot'}
    (args.output_dir / 'VALIDACAO.json').write_text(json.dumps(report, indent=2, ensure_ascii=False) + '\n')
    print(json.dumps({'output_directory': str(args.output_dir),
                      'boot_sha256': sha256(args.output_dir / 'boot-kernelsu-next.img'),
                      'device_boot_test_passed': False}, indent=2))


if __name__ == '__main__':
    parser = argparse.ArgumentParser(description=__doc__)
    for name in (*EXPECTED, 'build_dir', 'reference_build', 'reference_zip', 'output_dir'):
        parser.add_argument('--' + name.replace('_', '-'), required=True, type=Path)
    main(parser.parse_args())
