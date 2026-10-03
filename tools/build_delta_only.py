"""Build only the cumulative delta from one reviewed Git tree and frozen baselines."""
from __future__ import annotations
import copy, gzip, hashlib, json, sys, zipfile
from pathlib import Path
from build_coherent_resources import ROOT, git, identity, save

HANDOFF = ROOT / 'docs/story-quality/client-integration'
sys.path.insert(0, str(HANDOFF))
import delta_only_guard as guard
from client_candidate_tools import load_packet, read_blobs


def build(repo, ref, scenario, full_js, previous_delta, out):
    repo, out = Path(repo), Path(out)
    source = git(repo, 'rev-parse', ref).decode().strip()
    ready = json.loads(git(repo, 'show', source + ':docs/story-quality/client-integration/READY.json'))
    packet = load_packet(repo / ready['manifest'], ready['manifest_sha256'])
    packet['manifest_sha256'] = ready['manifest_sha256']
    lock = json.loads(git(repo, 'show', source + ':docs/story-quality/client-integration/delta-only-baseline-lock.json'))
    scene, full, old = map(guard.inventory, (scenario, full_js, previous_delta))
    guard.validate_delta(old, lock['full_js']['sha256'], lock['full_js']['version'])
    if old['metadata']['version'] < lock['previous_delta']['version']:
        raise ValueError('Published parent predates reviewed cumulative floor')
    if old['metadata']['version'] == lock['previous_delta']['version'] and old['archive_sha256'] != lock['previous_delta']['sha256']:
        raise ValueError('Same parent version has conflicting bytes')
    lock = copy.deepcopy(lock)
    lock['previous_delta'].update(version=old['metadata']['version'], sha256=old['archive_sha256'], bytes=old['archive_bytes'])
    plan = guard.make_plan(str(repo), source, packet, scene, full, old, lock, require_integrated=True)
    raw = read_blobs(str(repo), source, plan['required_delta_paths'])
    m = dict(schema=guard.SCHEMA, version=old['metadata']['version'] + 1,
             base_js_version=lock['full_js']['version'], base_js_sha256=full['archive_sha256'],
             source_authority=dict(mode='delta_only_cumulative', source_commit=source,
                 scenario_version=lock['scenario']['version'], scenario_sha256=scene['archive_sha256'],
                 previous_delta_version=old['metadata']['version'], previous_delta_sha256=old['archive_sha256'],
                 previous_paths=sorted(p for p in old['files'] if p != guard.META),
                 client_manifest_sha256=ready['manifest_sha256']),
             entries=[dict(path=p, size=len(b), sha256=hashlib.sha256(b).hexdigest()) for p,b in sorted(raw.items())])
    if out.exists() and any(out.iterdir()):
        raise ValueError('Candidate output must be new')
    out.mkdir(parents=True, exist_ok=True)
    def put(z, name, data):
        i = zipfile.ZipInfo(name, (2026, 1, 1, 0, 0, 0)); i.compress_type = zipfile.ZIP_DEFLATED; i.external_attr = 0o100644 << 16
        z.writestr(i, data, compresslevel=9)
    save(out / 'cn_js_delta_manifest.json', m)
    archive = out / 'cn_js_delta.zip'
    with zipfile.ZipFile(archive, 'w') as z:
        for p,b in sorted(raw.items()): put(z,p,b)
        put(z,guard.META,(out / 'cn_js_delta_manifest.json').read_bytes())
    result = guard.verify_maps(plan, guard.inventory(archive))
    ident = identity(archive)
    save(out / 'version_js_delta.json', dict(version=m['version'], size=ident['size'], md5=ident['md5'],
                                           base_js_version=m['base_js_version'], base_js_sha256=m['base_js_sha256']))
    result.update(source_commit=source, delta=ident, scenario=identity(Path(scenario)), full_js=identity(Path(full_js)),
                  previous_delta=identity(Path(previous_delta)), client_manifest_sha256=ready['manifest_sha256'],
                  story_payloads=sum(guard.story(p) for p in raw), nonstory_payloads=sum(not guard.story(p) for p in raw),
                  publication='NOT_PUBLISHED')
    (out.parent / 'delta-plan.json.gz').write_bytes(gzip.compress(json.dumps(plan, ensure_ascii=False).encode(),mtime=0))
    save(out.parent / 'prepared-report.json', result)
    return result


def mirror_authority(metadata, assets, repo=ROOT):
    """Verify each delta entry and missing story differences against its pinned current Git tree."""
    m = metadata['cn_js_delta_manifest.json']; a = m['source_authority']; source = a['source_commit']
    if a.get('mode') != 'delta_only_cumulative' or len(source) != 40 or any(c not in '0123456789abcdef' for c in source):
        raise ValueError('Invalid cumulative source authority')
    try: git(repo, 'cat-file', '-e', source + '^{commit}')
    except Exception: git(repo, 'fetch', 'origin', source)
    # A delayed mirror is allowed after docs-only changes, not after different product bytes.
    drift = git(repo, 'diff', '--name-only', source, 'HEAD', '--', 'magica', 'madomagi', 'configures/js-delta-baseline.json').strip()
    if drift: raise ValueError('Mirror checkout has a different product authority')
    lock = json.loads(git(repo,'show',source+':docs/story-quality/client-integration/delta-only-baseline-lock.json'))
    for name,key,version in [('cn_js_update.zip','full_js','version_js.json'),('cn_scenario_update.zip','scenario','version_scenario.json')]:
        if (assets[name]['digest'] != 'sha256:'+lock[key]['sha256'] or assets[name]['size'] != lock[key]['bytes']
                or metadata[version]['version'] != lock[key]['version']): raise ValueError('Frozen baseline changed: '+name)
    if a.get('scenario_sha256') != lock['scenario']['sha256'] or a.get('scenario_version') != lock['scenario']['version']:
        raise ValueError('Wrong frozen Scenario authority')
    cfg = json.loads(git(repo,'show',source+':configures/js-delta-baseline.json'))
    paths = [e['path'] for e in m['entries']]
    stories = [p.decode() for p in git(repo,'ls-tree','-rz','--name-only',source,'--',guard.PREFIX).split(b'\0') if p]
    allraw = read_blobs(str(repo),source,sorted(set(paths)|set(stories)))
    expected = {p:dict(size=len(b),sha256=hashlib.sha256(b).hexdigest()) for p,b in allraw.items()}
    frozen = dict(metadata['cn_scenario_update_manifest.json']['files'])
    js = metadata['cn_js_update_manifest.json'].get('files',{})
    if isinstance(js,dict): frozen.update(js)
    required = set(cfg['supplemental_product_paths']) | set(a['previous_paths'])
    required |= {p for p in stories if expected[p]['sha256'] != frozen.get(p,{}).get('sha256')}
    try: git(repo,'cat-file','-e',cfg['base_source_commit']+'^{commit}')
    except Exception: git(repo,'fetch','origin',cfg['base_source_commit'])
    touched = [p.decode() for p in git(repo,'diff','--name-only','-z',cfg['base_source_commit'],source).split(b'\0') if p]
    required |= {p for p in touched if guard.product(p) and p != guard.META}
    if not required <= set(paths): raise ValueError('Mirror cumulative payload omits current or previous repairs')
    if len(paths) != len(set(paths)): raise ValueError('Duplicate delta paths')
    for entry in m['entries']:
        p=entry['path']
        if not (guard.product(p) or guard.story(p)) or expected[p] != {k:entry[k] for k in ('size','sha256')}:
            raise ValueError('Delta differs from authoritative Git bytes: '+p)
    return expected
