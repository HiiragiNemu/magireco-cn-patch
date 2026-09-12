"""Publish only the seven source-bound finalized hot-update objects."""
import argparse, hashlib, json, os
from pathlib import Path

NAMES = ['cn_js_update.zip', 'cn_scenario_update.zip', 'cn_js_update_manifest.json', 'cn_scenario_update_manifest.json', 'manifest.json', 'version_js.json', 'version_scenario.json']
EXPECTED = Path('configures/finalized-localization-assets.json')
PAYLOAD = Path('payload')
BACKUP = Path('production-backup')

def digest(path):
    with path.open('rb') as f: return hashlib.file_digest(f, 'sha256').hexdigest()

def save(path, data):
    path.parent.mkdir(parents=True, exist_ok=True)
    path.write_text(json.dumps(data, ensure_ascii=False, indent=2), encoding='utf-8')

def local():
    data = json.loads(EXPECTED.read_text(encoding='utf-8'))
    assert set(data['files']) == set(NAMES)
    for name in NAMES:
        p = PAYLOAD / name; row = data['files'][name]
        assert p.stat().st_size == row['bytes'] and digest(p) == row['sha256'], name
    for scope in ['js', 'scenario']:
        name = f'cn_{scope}_update.zip'; v = json.loads((PAYLOAD/f'version_{scope}.json').read_text(encoding='utf-8'))
        with (PAYLOAD/name).open('rb') as f: md5 = hashlib.file_digest(f, 'md5').hexdigest()
        assert v['size'] == (PAYLOAD/name).stat().st_size and v['md5'] == md5
    print('SEVEN_FINALIZED_LOCAL_OBJECTS_VERIFIED')
    return data

def main(mode):
    expected = local()
    if mode == 'verify-local': return
    import boto3
    from botocore.config import Config
    required = ['R2_ENDPOINT', 'R2_ACCESS_KEY', 'R2_SECRET_KEY', 'R2_BUCKET']
    missing = [key for key in required if not os.environ.get(key)]
    if missing: raise RuntimeError('Missing production configuration names: ' + ', '.join(missing))
    s3 = boto3.client('s3', endpoint_url=os.environ['R2_ENDPOINT'].rstrip('/'), aws_access_key_id=os.environ['R2_ACCESS_KEY'], aws_secret_access_key=os.environ['R2_SECRET_KEY'], region_name=os.environ.get('R2_REGION') or 'auto', config=Config(signature_version='s3v4'))
    bucket = os.environ['R2_BUCKET']
    def remote(name):
        try: response = s3.get_object(Bucket=bucket, Key=name)
        except s3.exceptions.ClientError as e:
            if str(e.response.get('Error', {}).get('Code')) in ['404', 'NoSuchKey', 'NotFound']: return None
            raise
        h = hashlib.sha256(); size = 0
        while block := response['Body'].read(8*1024*1024): h.update(block); size += len(block)
        return dict(bytes=size, sha256=h.hexdigest())
    if mode == 'backup':
        BACKUP.mkdir(exist_ok=True); record = {}
        for name in NAMES:
            row = remote(name); record[name] = row
            if row is not None:
                s3.download_file(bucket, name, str(BACKUP/name))
                assert digest(BACKUP/name) == row['sha256']
            save(BACKUP/'index.json', record)
        print('PRODUCTION_BACKUP_VERIFIED'); return
    old = json.loads((BACKUP/'index.json').read_text(encoding='utf-8'))
    assert set(old) == set(NAMES)
    results = {}
    for name in NAMES:
        current = remote(name); new = expected['files'][name]
        assert current in [old[name], new], ('Concurrent production object change', name)
        target = old[name] if mode == 'rollback' else new
        if current != target:
            if target is None:
                assert mode == 'rollback' and current == new
                s3.delete_object(Bucket=bucket, Key=name)
            else:
                source = (BACKUP if mode == 'rollback' else PAYLOAD)/name
                assert digest(source) == target['sha256']
                s3.upload_file(str(source), bucket, name, ExtraArgs={'CacheControl':'no-cache, must-revalidate', 'ContentType':'application/zip' if name.endswith('.zip') else 'application/json'})
        results[name] = remote(name); assert results[name] == target, name
        save(Path('publish-evidence.json'), dict(mode=mode, source_commit=expected['source_commit'], objects=results))
        print('R2_BODY_VERIFIED', name, flush=True)

if __name__ == '__main__':
    p = argparse.ArgumentParser(); p.add_argument('mode', choices=['verify-local','backup','apply','rollback'])
    main(p.parse_args().mode)
