"""Reuse released bytes when a rebuild has identical member names and contents."""
import argparse
import hashlib
from pathlib import Path
import shutil
import zipfile


def inventory(path):
    with zipfile.ZipFile(path) as archive:
        names = [i.filename for i in archive.infolist() if not i.is_dir()]
        if len(names) != len(set(names)):
            raise ValueError('Duplicate ZIP members')
        return {name: hashlib.sha256(archive.read(name)).hexdigest() for name in names}


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
