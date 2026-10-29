"""Read-only ELF/module inspection. Never loads or executes phone binaries."""
import argparse
import collections
import hashlib
import json
import struct
import subprocess
import tempfile
from pathlib import Path

BASE = BUILD = CERTIFICATE = PROTECTED_EXPORTS = None


def sha(data):
    return hashlib.sha256(data).hexdigest()


def string(data, offset):
    if not 0 <= offset < len(data):
        raise ValueError('String offset outside section')
    end = data.index(b'\0', offset)
    return data[offset:end].decode('utf-8')


def inspect(path):
    raw = path.read_bytes()
    if raw[:6] != b'\x7fELF\x02\x01' or struct.unpack_from('<HH', raw, 16) != (1, 183):
        raise ValueError(f'Not an ARM64 little-endian relocatable ELF: {path}')
    offset = struct.unpack_from('<Q', raw, 40)[0]
    entsize, count, strindex = struct.unpack_from('<HHH', raw, 58)
    if entsize != 64 or not 0 < count < 65535 or strindex >= count:
        raise ValueError('Unsupported ELF section layout')
    sections = []
    for i in range(count):
        values = struct.unpack_from('<IIQQQQIIQQ', raw, offset + i * entsize)
        name, typ, flags, addr, off, size, link, info, align, entrysize = values
        if typ != 8 and off + size > len(raw):
            raise ValueError('Section outside ELF')
        sections.append({'name_offset': name, 'type': typ, 'data': raw[off:off+size] if typ != 8 else b'',
                         'link': link, 'info': info, 'size': size, 'entry_size': entrysize})
    names = sections[strindex]['data']
    for s in sections:
        s['name'] = string(names, s['name_offset'])
    byname = {s['name']: s for s in sections}
    modinfo = collections.defaultdict(list)
    for part in byname['.modinfo']['data'].split(b'\0'):
        if b'=' in part:
            key, value = part.decode().split('=', 1)
            modinfo[key].append(value)
    versions = {}
    data = byname.get('__versions', {'data': b''})['data']
    if len(data) % 64:
        raise ValueError('Unsupported __versions layout')
    for i in range(0, len(data), 64):
        crc = struct.unpack_from('<Q', data, i)[0]
        name = string(data[i+8:i+64], 0)
        if name in versions or crc > 0xffffffff:
            raise ValueError('Ambiguous or oversized symbol version')
        versions[name] = f'0x{crc:08x}'
    symtab = byname['.symtab']
    strings = sections[symtab['link']]['data']
    if symtab['entry_size'] != 24 or len(symtab['data']) % 24:
        raise ValueError('Unsupported symbol table')
    elf_symbols = list(struct.iter_unpack('<IBBHQQ', symtab['data']))
    relocations = {}
    for s in sections:
        if s['type'] == 4 and sections[s['info']]['name'] in ('__ksymtab', '__ksymtab_gpl'):
            if s['entry_size'] != 24 or sections[s['link']]['name'] != '.symtab':
                raise ValueError('Unsupported export relocation table')
            for off, info, addend in struct.iter_unpack('<QQq', s['data']):
                relocations[(s['info'], off)] = (info >> 32, info & 0xffffffff, addend)
    exports, undefined, weak = {}, [], []
    for i in range(0, len(symtab['data']), 24):
        nameoff, info, other, index, value, size = struct.unpack_from('<IBBHQQ', symtab['data'], i)
        name = string(strings, nameoff)
        if index == 0 and name:
            (weak if info >> 4 == 2 else undefined).append(name)
        if name.startswith('__ksymtab_') and index < len(sections):
            section = sections[index]['name']
            if section not in ('__ksymtab', '__ksymtab_gpl'):
                continue
            crcdata = byname[section.replace('__ksymtab', '__kcrctab')]['data']
            if value % 12 or value // 12 * 4 + 4 > len(crcdata):
                raise ValueError('Unexpected PREL32 export table layout')
            crc = struct.unpack_from('<I', crcdata, value // 12 * 4)[0]
            refindex, kind, addend = relocations[(index, value + 8)]
            refsym = elf_symbols[refindex]
            if kind != 261 or refsym[3] >= len(sections):
                raise ValueError('Unsupported namespace relocation')
            namespace = string(sections[refsym[3]]['data'], refsym[4] + addend)
            exports[name[len('__ksymtab_'):]] = {'crc': f'0x{crc:08x}', 'gpl_only': section.endswith('_gpl'),
                                               'namespace': namespace}
    signature = {'present': False, 'verified_with_original_certificate': False}
    marker = b'~Module signature appended~\n'
    if raw.endswith(marker):
        signature['present'] = True
        footer = raw[-len(marker)-12:-len(marker)]
        algo, hashid, idtype, signerlen, keyidlen, pad, siglen = struct.unpack('>BBBBB3sI', footer)
        if (idtype, signerlen, keyidlen, pad) != (2, 0, 0, b'\0'*3):
            raise ValueError('Unsupported module signature format')
        start = len(raw) - len(marker) - 12 - siglen
        if start <= 0:
            raise ValueError('Invalid module signature size')
        with tempfile.TemporaryDirectory(dir=BASE) as tmp:
            content, sig = Path(tmp)/'content', Path(tmp)/'signature.der'
            content.write_bytes(raw[:start]); sig.write_bytes(raw[start:start+siglen])
            result = subprocess.run(['openssl', 'cms', '-verify', '-binary', '-inform', 'DER',
                '-in', str(sig), '-content', str(content), '-certfile', str(CERTIFICATE),
                '-nointern', '-noverify', '-out', '/dev/null'], capture_output=True, text=True)
            signature.update(size=siglen, verified_with_original_certificate=result.returncode == 0,
                             verification_message=result.stderr.strip())
    return {'path': str(path.relative_to(BASE)), 'size': len(raw), 'sha256': sha(raw),
            'modinfo': dict(modinfo), 'versions': versions, 'exports': exports,
            'undefined': sorted(set(undefined)), 'weak_undefined': sorted(set(weak)), 'signature': signature}


def main():
    paths = sorted((BASE/'modules').rglob('*.ko')) + sorted((BASE/'vendor-ramdisk-modules').rglob('*.ko'))
    records = []
    for i, path in enumerate(paths):
        records.append(inspect(path))
        if (i+1) % 100 == 0:
            print(f'Inspected {i+1}/{len(paths)} modules', flush=True)
    (BASE/'module-inventory.json').write_text(json.dumps(records, indent=2)+'\n')
    core = {}
    for line in (BUILD/'Module.symvers').read_text().splitlines():
        fields = line.split()
        if fields[2] == 'vmlinux':
            core[fields[1]] = {'crc': fields[0], 'provider': 'experimental-vmlinux',
                              'namespace': fields[4] if len(fields)>4 else '',
                              'gpl_only': fields[3] == 'EXPORT_SYMBOL_GPL', 'trusted': True}
    providers = collections.defaultdict(list)
    for name, item in core.items():
        providers[name].append(item)
    for module in records:
        for name, data in module['exports'].items():
            providers[name].append(dict(data, provider=module['path'],
                                       trusted=module['signature']['verified_with_original_certificate']))
    unprotected = set((BUILD/'abi_symbollist.raw').read_text().splitlines())
    protected_exports = {line.strip() for line in PROTECTED_EXPORTS.read_text().splitlines() if line.strip() and not line.lstrip().startswith('#')}
    missing, mismatched, policy, no_versions, unversioned, collisions, namespace_errors, license_errors = [], [], [], [], [], [], [], []
    checked_core, checked_modules = 0, 0
    for module in records:
        path = module['path']
        trusted = module['signature']['verified_with_original_certificate']
        if not module['versions']:
            no_versions.append(path)
        for name in module['undefined']:
            if name not in module['versions']:
                unversioned.append({'module': path, 'symbol': name})
        for name, crc in module['versions'].items():
            available = [core[name]] if name in core else providers.get(name, [])
            if not available:
                missing.append({'module': path, 'symbol': name, 'crc': crc})
            elif all(p['crc'] != crc for p in available):
                mismatched.append({'module': path, 'symbol': name, 'expected': crc, 'providers': available})
            elif name in core:
                checked_core += 1
            else:
                checked_modules += 1
            if not trusted and available and all(p['trusted'] for p in available) and name not in unprotected:
                policy.append({'module': path, 'symbol': name, 'reason': 'unsigned import from trusted provider outside allowlist'})
            for p in available:
                if p.get('namespace') and p['namespace'] not in module['modinfo'].get('import_ns', []):
                    namespace_errors.append({'module': path, 'symbol': name, 'namespace': p['namespace']})
                compatible = {'GPL', 'GPL v2', 'GPL and additional rights', 'Dual BSD/GPL', 'Dual MIT/GPL', 'Dual MPL/GPL'}
                if p.get('gpl_only') and not all(l in compatible for l in module['modinfo'].get('license', [''])):
                    license_errors.append({'module': path, 'symbol': name})
        if not trusted:
            for name in module['exports']:
                if name in protected_exports:
                    policy.append({'module': path, 'symbol': name, 'reason': 'unsigned export of protected symbol'})
        for name in module['exports']:
            if name in core:
                collisions.append({'module': path, 'symbol': name})
    summary = {'module_files': len(records), 'unique_module_hashes': len({m['sha256'] for m in records}),
        'groups': dict(collections.Counter(m['path'].split('/')[1] if m['path'].startswith('modules/') else 'vendor_boot' for m in records)),
        'signature_present': sum(m['signature']['present'] for m in records),
        'signature_verified_original': sum(m['signature']['verified_with_original_certificate'] for m in records),
        'signature_failures': [m['path'] for m in records if m['signature']['present'] and not m['signature']['verified_with_original_certificate']],
        'vermagic': dict(collections.Counter(str(m['modinfo'].get('vermagic')) for m in records)),
        'checked_core_import_records': checked_core, 'checked_module_import_records': checked_modules,
        'missing_count': len(missing), 'crc_mismatch_count': len(mismatched), 'policy_issue_count': len(policy),
        'no_versions': no_versions, 'unversioned_undefined': unversioned,
        'namespace_errors': namespace_errors, 'license_errors': license_errors,
        'core_export_collisions': collisions, 'missing': missing, 'crc_mismatches': mismatched, 'policy_issues': policy,
        'comparison_build_run': json.loads((BUILD/'provenance.json').read_text())['run_id'], 'provider_loading_order_checked': False,
        'namespace_and_license_enforcement_checked': True, 'hardware_tested': False, 'installable': False}
    (BASE/'module-comparison.json').write_text(json.dumps(summary, indent=2)+'\n')
    print(json.dumps({k:v for k,v in summary.items() if k not in ('missing','crc_mismatches','policy_issues','unversioned_undefined','core_export_collisions')},indent=2))
    print('Missing samples',missing[:12]);print('CRC mismatch samples',mismatched[:8]);print('Policy samples',policy[:8])


if __name__ == '__main__':
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument('--data-dir', required=True, type=Path,
                        help='Directory containing modules/ and vendor-ramdisk-modules/ extracted from the owner files')
    parser.add_argument('--build-dir', required=True, type=Path)
    parser.add_argument('--certificate', required=True, type=Path,
                        help='Pinned original public module certificate, PEM')
    parser.add_argument('--protected-exports', required=True, type=Path,
                        help='Original source android/abi_gki_protected_exports_aarch64')
    args = parser.parse_args()
    BASE, BUILD = args.data_dir.resolve(), args.build_dir.resolve()
    CERTIFICATE, PROTECTED_EXPORTS = args.certificate.resolve(), args.protected_exports.resolve()
    main()
