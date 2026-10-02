"""Stage source-bound story candidates outside Git; verify actual package layers. Never publish.

Python standard library only. This tool cannot commit, modify a repository, or call a release API.
Use the client's existing coherent resource workflow for integration and publication.
"""
from __future__ import annotations
import argparse, contextlib, copy, gzip, hashlib, json, subprocess, sys, zipfile
from pathlib import Path, PurePosixPath
from exact_json import apply, blob
from translation_rules import validate

PREFIX = 'madomagi/resource/scenario/'
CONFIG = 'configures/js-delta-baseline.json'

def sha(raw: bytes) -> str:
    return hashlib.sha256(raw).hexdigest()

def encoded(value: object) -> bytes:
    return (json.dumps(value, ensure_ascii=False, indent=2) + '\n').encode('utf-8')

def safe_path(path: str) -> str:
    p = PurePosixPath(path)
    if not path or p.is_absolute() or '..' in p.parts or '\\' in path or ':' in path or str(p) != path:
        raise ValueError('Unsafe or noncanonical relative path: ' + repr(path))
    return path

def load_packet(path: Path, expected_sha256: str) -> dict:
    raw = path.read_bytes()
    if sha(raw) != expected_sha256:
        raise ValueError('Manifest checksum differs from READY.json')
    packet = json.loads(gzip.decompress(raw))
    if packet.get('kind') != 'source_bound_unreleased_story_integration' or packet.get('published') is not False:
        raise ValueError('Not an approved unpublished integration packet')
    entries = packet['files']; seen = set()
    for entry in entries:
        path = safe_path(entry['path'])
        if not path.startswith(PREFIX) or not path.endswith('.json') or path in seen:
            raise ValueError('Invalid/duplicate story path')
        seen.add(path)
        if sha(entry['candidate_utf8'].encode('utf-8')) != entry['after_sha256'] or blob(entry['candidate_utf8'].encode('utf-8')) != entry['after_blob']:
            raise ValueError('Candidate payload does not match proof')
    if len(entries) != packet['target_count']:
        raise ValueError('Target count mismatch')
    return packet

def candidate_from_source(raw: bytes, entry: dict) -> tuple[bytes, str]:
    digest = blob(raw)
    if digest == entry['after_blob'] and sha(raw) == entry['after_sha256']:
        return raw, 'already_integrated'
    if digest != entry['before_blob'] or sha(raw) != entry['before_sha256']:
        raise ValueError('SOURCE DRIFT; reconcile this file rather than overwrite: ' + entry['path'])
    revised = apply(raw, entry['operations'])
    validate(raw, revised, entry['operations'])
    if blob(revised) != entry['after_blob'] or sha(revised) != entry['after_sha256']:
        raise ValueError('Candidate reconstruction mismatch')
    if revised != entry['candidate_utf8'].encode('utf-8'):
        raise ValueError('Candidate bytes mismatch')
    if apply(revised, [[at, new, old] for at, old, new in entry['operations']]) != raw:
        raise ValueError('Non-reversible candidate')
    return revised, 'staged_only'

def config_with_targets(raw: bytes, packet: dict) -> bytes:
    cfg = json.loads(raw)
    old = cfg.get('supplemental_product_paths')
    frozen = packet['config_before']
    if not isinstance(old, list) or any(not isinstance(p, str) for p in old) or len(old) != len(set(old)):
        raise ValueError('Invalid supplemental paths')
    if not set(frozen['supplemental_product_paths']).issubset(old):
        raise ValueError('Existing delta ownership was removed; reconcile before integration')
    for key, value in frozen.items():
        if key != 'supplemental_product_paths' and cfg.get(key) != value:
            raise ValueError('JS baseline identity changed; revalidate against new baseline')
    result = copy.deepcopy(cfg)
    targets = {e['path'] for e in packet['files']}
    for p in old + sorted(targets): safe_path(p)
    result['supplemental_product_paths'] = old + sorted(targets - set(old))
    if result == cfg:
        return raw
    return encoded(result)

def git(repo: str, *args: str) -> bytes:
    path = Path(repo)
    prefix = ['--git-dir=' + str(path)] if (path / 'HEAD').is_file() and (path / 'objects').is_dir() else ['-C', str(path)]
    proc = subprocess.run(['git', *prefix, *args], stdout=subprocess.PIPE, stderr=subprocess.PIPE, timeout=180)
    if proc.returncode:
        raise RuntimeError(proc.stderr.decode('utf-8', errors='replace'))
    return proc.stdout

def read_blobs(repo: str, ref: str, paths: list[str]) -> dict[str, bytes]:
    path = Path(repo)
    prefix = ['--git-dir=' + str(path)] if (path / 'HEAD').is_file() and (path / 'objects').is_dir() else ['-C', str(path)]
    unique = list(dict.fromkeys(paths))
    for name in unique:
        safe_path(name)
        if '\n' in name or '\r' in name: raise ValueError('Invalid batch path')
    request = ''.join(ref + ':' + name + '\n' for name in unique).encode('utf-8')
    proc = subprocess.run(['git', *prefix, 'cat-file', '--batch'], input=request, stdout=subprocess.PIPE, stderr=subprocess.PIPE, timeout=180)
    if proc.returncode: raise RuntimeError(proc.stderr.decode('utf-8', errors='replace'))
    result = {}; offset = 0
    for name in unique:
        end = proc.stdout.find(b'\n', offset)
        header = proc.stdout[offset:end].split()
        if end < 0 or len(header) != 3 or header[1] != b'blob': raise ValueError('Missing or invalid source blob: ' + name)
        size = int(header[2]); offset = end + 1; raw = proc.stdout[offset:offset + size]
        if len(raw) != size or proc.stdout[offset+size:offset+size+1] != b'\n' or blob(raw) != header[0].decode(): raise ValueError('Corrupt source batch result')
        result[name] = raw; offset += size + 1
    if offset != len(proc.stdout): raise ValueError('Unexpected source batch output')
    return result

def preflight(repo: str, ref: str, packet: dict) -> tuple[dict[str, bytes], dict]:
    commit = git(repo, 'rev-parse', ref + '^{commit}').decode().strip()
    candidates = {}; statuses = {}
    source = read_blobs(repo, commit, [e['path'] for e in packet['files']] + [e['path'] for e in packet['preservation_guards']] + [CONFIG])
    for entry in packet['files']:
        raw = source[entry['path']]
        revised, status = candidate_from_source(raw, entry)
        candidates[entry['path']] = revised; statuses[entry['path']] = status
    for entry in packet['preservation_guards']:
        if entry['path'] in candidates: continue
        raw = source[entry['path']]
        if sha(raw) != entry['sha256']:
            raise ValueError('Preserved source changed; refresh handoff instead of rolling it back: ' + entry['path'])
    candidates[CONFIG] = config_with_targets(source[CONFIG], packet)
    report = {'source_revision': commit, 'target_count': len(statuses), 'states': statuses,
              'old_supplemental_paths_preserved': True, 'all_targets_selected_for_delta': True,
              'repositories_written': False, 'published': False}
    return candidates, report

def write_isolated(files: dict[str, bytes], destination: Path) -> None:
    destination = destination.resolve()
    if destination.exists():
        raise ValueError('Output directory must not already exist')
    for parent in [destination.parent, *destination.parents]:
        if (parent / '.git').exists() or ((parent / 'HEAD').is_file() and (parent / 'objects').is_dir()):
            raise ValueError('Refusing to materialize into a Git repository')
    for name in files: safe_path(name)
    destination.mkdir(parents=True, exist_ok=False)
    for name, raw in files.items():
        target = destination.joinpath(*PurePosixPath(name).parts)
        target.parent.mkdir(parents=True, exist_ok=True)
        target.write_bytes(raw)

class ZipLayer:
    def __init__(self, path: Path):
        self.path = path; self.archive = zipfile.ZipFile(path); self.entries = {}; self.cache = {}
        try:
            for entry in self.archive.infolist():
                if entry.is_dir(): continue
                name = safe_path(entry.filename)
                if name in self.entries: raise ValueError('Duplicate ZIP entry: ' + name)
                self.entries[name] = entry
        except Exception:
            self.archive.close()
            raise
    def digest(self, name: str) -> str:
        if name not in self.cache:
            with self.archive.open(self.entries[name]) as stream:
                h = hashlib.sha256()
                for block in iter(lambda: stream.read(1024 * 1024), b''): h.update(block)
            self.cache[name] = h.hexdigest()
        return self.cache[name]
    def close(self): self.archive.close()

def verify_layers(packet: dict, scenario_path: Path, delta_path: Path, full_js_path: Path | None = None,
                  base_paths: list[Path] | None = None) -> dict:
    with contextlib.ExitStack() as stack:
        def opened(path):
            layer = ZipLayer(path); stack.callback(layer.close); return layer
        scenario = opened(scenario_path); delta = opened(delta_path)
        full_js = opened(full_js_path) if full_js_path else None
        bases = [opened(path) for path in (base_paths or [])]
        # Replaying delta last must preserve every one of its scenario paths, not just this batch.
        overlaps = 0
        for layer in [delta, *([full_js] if full_js else [])]:
            for name in layer.entries:
                if name.startswith(PREFIX) and name.endswith('.json'):
                    if name not in scenario.entries or layer.digest(name) != scenario.digest(name):
                        raise ValueError('Stale/mismatched last-writer story layer: ' + name)
                    overlaps += 1
        expected = {e['path']: e['sha256'] for e in packet['preservation_guards']}
        expected.update({e['path']: e['after_sha256'] for e in packet['files']})
        target_paths = {e['path'] for e in packet['files']}
        for name, digest in expected.items():
            if name not in scenario.entries or scenario.digest(name) != digest:
                raise ValueError('Full Scenario failed target/preservation proof: ' + name)
            if name in target_paths and (name not in delta.entries or delta.digest(name) != digest):
                raise ValueError('New reviewed target missing or outdated in JS delta: ' + name)
        for name in packet['config_before']['supplemental_product_paths']:
            if name not in delta.entries:
                raise ValueError('Previously owned delta entry is missing: ' + name)
        # Check both normal source order and cached-delta replay after a full resource reinstall.
        final_checks = 0
        for order in [[*bases, scenario, *([full_js] if full_js else []), delta],
                      [*bases, *([full_js] if full_js else []), delta, scenario, delta]]:
            for name, digest in expected.items():
                winner = next((layer for layer in reversed(order) if name in layer.entries), None)
                if winner is None or winner.digest(name) != digest:
                    raise ValueError('Final resource bytes regress after install/replay: ' + name)
                final_checks += 1
        return {'passed': True, 'reviewed_targets_in_both_packages': len(target_paths),
                'preservation_and_target_paths': len(expected), 'story_layer_overlap_checks': overlaps,
                'final_layer_hash_checks': final_checks, 'full_js_supplied': full_js is not None,
                'base_layers_supplied': len(bases), 'published': False, 'device_test_performed': False,
                'limitation': 'Static ZIP overlay verification only. Client must run actual supported install/offline/redownload flows and read device bytes.'}

def main() -> None:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument('--manifest', required=True, type=Path)
    parser.add_argument('--manifest-sha256', required=True)
    sub = parser.add_subparsers(dest='action', required=True)
    for action in ['check-source', 'check-integrated', 'stage']:
        sp = sub.add_parser(action); sp.add_argument('--repo', required=True); sp.add_argument('--ref', default='HEAD')
        if action == 'stage': sp.add_argument('--output', type=Path, required=True)
    sp = sub.add_parser('verify-packages'); sp.add_argument('--scenario', type=Path, required=True); sp.add_argument('--delta', type=Path, required=True)
    sp.add_argument('--full-js', type=Path, required=True); sp.add_argument('--base', type=Path, action='append', default=[])
    args = parser.parse_args(); packet = load_packet(args.manifest, args.manifest_sha256)
    if args.action in ['check-source','check-integrated','stage']:
        files, report = preflight(args.repo, args.ref, packet)
        if args.action == 'check-integrated':
            if any(state != 'already_integrated' for state in report['states'].values()):
                raise ValueError('Not all candidate bytes have been integrated; building would publish stale text')
            live_config = git(args.repo, 'show', report['source_revision'] + ':' + CONFIG)
            if config_with_targets(live_config, packet) != live_config:
                raise ValueError('New scenario paths are not yet selected for JS delta')
            report['integrated_source_ready_for_client_build'] = True
        if args.action == 'stage':
            files['INTEGRATION_PREFLIGHT.json'] = encoded(report)
            write_isolated(files, args.output); report['isolated_output'] = str(args.output.resolve())
    else: report = verify_layers(packet, args.scenario, args.delta, args.full_js, args.base)
    print(json.dumps(report, ensure_ascii=False, indent=2))

if __name__ == '__main__':
    try: main()
    except (ValueError, OSError, RuntimeError, zipfile.BadZipFile) as exc:
        print('BLOCKED: ' + str(exc), file=sys.stderr); sys.exit(2)
