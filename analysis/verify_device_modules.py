#!/usr/bin/env python3
"""Check a build against requirements extracted from the owner's actual modules.

This does not execute modules or establish hardware compatibility. The signed
module corpus and module-to-module dependencies were inspected separately.
"""
import argparse
import json
from pathlib import Path


def verify(build, requirements):
    build = Path(build)
    core = {}
    for line in (build / 'Module.symvers').read_text().splitlines():
        fields = line.split()
        if len(fields) < 4:
            raise ValueError('Malformed Module.symvers')
        crc, name, owner, export = fields[:4]
        if owner == 'vmlinux':
            if name in core:
                raise ValueError('Duplicate core export')
            core[name] = {'crc': crc.lower(), 'export': export,
                          'namespace': fields[4] if len(fields) > 4 else ''}
    wanted = requirements['required_core_exports']
    if not wanted or len(wanted) != requirements['required_core_export_count']:
        raise ValueError('Empty or inconsistent device requirements')
    failures = []
    for name, req in wanted.items():
        actual = core.get(name)
        if actual is None:
            failures.append({'symbol': name, 'reason': 'missing core export'})
            continue
        if actual['crc'] != req['crc']:
            failures.append({'symbol': name, 'reason': 'CRC mismatch',
                             'expected': req['crc'], 'actual': actual['crc']})
        if actual['namespace'] and actual['namespace'] not in req['allowed_namespaces']:
            failures.append({'symbol': name, 'reason': 'undeclared namespace',
                             'namespace': actual['namespace']})
        if actual['export'] not in ('EXPORT_SYMBOL', 'EXPORT_SYMBOL_GPL'):
            failures.append({'symbol': name, 'reason': 'unsupported export class'})
        if actual['export'] == 'EXPORT_SYMBOL_GPL' and not req['all_consumers_gpl_compatible']:
            failures.append({'symbol': name, 'reason': 'GPL-only export used by incompatible consumer'})
    provenance = json.loads((build / 'provenance.json').read_text())
    magic = provenance['kernel_release'] + requirements['vermagic_suffix']
    if magic.encode() + b'\0' not in (build / 'Image').read_bytes():
        failures.append({'reason': 'expected module vermagic not present in Image'})
    return {'static_core_module_checks_passed': not failures,
            'required_core_exports_checked': len(wanted),
            'module_file_records': requirements['module_file_records'],
            'unique_module_hashes': requirements['unique_module_hashes'],
            'workflow_commit': provenance['workflow_commit'],
            'run_id': provenance['run_id'], 'variant': provenance['variant'],
            'failures': failures, 'hardware_tested': False, 'installable': False,
            'scope': 'Required core CRCs, GPL export use, declared namespaces and vermagic; hardware behavior and full ABI equivalence are not established'}


if __name__ == '__main__':
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument('--build-dir', required=True, type=Path)
    parser.add_argument('--requirements', type=Path,
                        default=Path(__file__).resolve().parents[1] / 'docs/device-module-requirements.json')
    parser.add_argument('--output', type=Path)
    args = parser.parse_args()
    report = verify(args.build_dir, json.loads(args.requirements.read_text()))
    text = json.dumps(report, indent=2, sort_keys=True) + '\n'
    if args.output:
        args.output.write_text(text)
    print(text, end='')
    raise SystemExit(0 if report['static_core_module_checks_passed'] else 1)
