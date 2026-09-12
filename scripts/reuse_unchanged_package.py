"""Reuse released bytes for equal members, ignoring CRLF/LF in UTF-8 text only."""
import argparse
import hashlib
from pathlib import Path
import shutil
import zipfile


TEXT_SUFFIXES = {'.json', '.js', '.css', '.html', '.tsv', '.txt'}


def content_digest(name, body):
    # Git text checkout can change CRLF to LF. This changes neither translation
    # values nor JS logic. Never normalize binary assets or parse/reserialize JSON.
    if Path(name).suffix.lower() in TEXT_SUFFIXES:
        try:
            body.decode('utf-8')
        except UnicodeDecodeError:
            pass
        else:
            body = body.replace(b'\r\n', b'\n')
    return hashlib.sha256(body).hexdigest()


def inventory(path):
    with zipfile.ZipFile(path) as archive:
        names = [i.filename for i in archive.infolist() if not i.is_dir()]
        if len(names) != len(set(names)):
            raise ValueError('Duplicate ZIP members')
        return {name: content_digest(name, archive.read(name)) for name in names}


def reuse(candidate, baseline):
    if inventory(candidate) == inventory(baseline):
        shutil.copyfile(baseline, candidate)
        print('UNCHANGED_PRODUCT_REUSED', candidate)
        return True
    print('CHANGED_PRODUCT_BUILD', candidate)
    return False


if __name__ == '__main__':
    p = argparse.ArgumentParser(description=__doc__)
    p.add_argument('candidate', type=Path)
    p.add_argument('baseline', type=Path)
    a = p.parse_args()
    reuse(a.candidate, a.baseline)
