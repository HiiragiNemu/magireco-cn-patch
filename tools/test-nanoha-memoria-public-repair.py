"""Keep the ten user-supplied Nanoha memoria originals in every public overlay."""
import argparse, hashlib, struct, zipfile
from pathlib import Path
EXPECTED = {'madomagi/resource/image_native/memoria/memoria_1356_c.png': '5139764bc68de5fdaad7f9ae0af6c58381d45117ea45d6b305f85347689f3467', 'madomagi/resource/image_native/memoria/memoria_1357_c.png': '73b1d12da466084165e902f331a8b8413d522cd08f457ae17d7d62adaee4f773', 'madomagi/resource/image_native/memoria/memoria_1358_c.png': '9782d3f3b75aba54375e3eb71ff4e12ab6d4c2d7af6c6f0cd0c0d9a24f2c1ea3', 'madomagi/resource/image_native/memoria/memoria_1359_c.png': '97d624203b44399df72b53daf994e89d1a81c8c11e44d2cb6d4bc4a83b675a37', 'madomagi/resource/image_native/memoria/memoria_1360_c.png': '073d507d9987bb7016644c4502aa4c50eaafb05d8f416ffcc7f5109f42964f27', 'madomagi/resource/image_native/memoria/memoria_1361_c.png': 'eb3272b9b54d6f7d7ca073be26a46a12f77858e2a9023189c06ad60e3c3f09e3', 'madomagi/resource/image_native/memoria/memoria_1362_c.png': '7c0feb8970516a33c80ac7f989ebbb05efd517d194d485d8e92f5f728e86b021', 'madomagi/resource/image_native/memoria/memoria_1363_c.png': 'dc99f13ad1fe18d53c3bce96084c7ac4853ddd82dd236464a84c50898bf627ef', 'madomagi/resource/image_native/memoria/memoria_1364_c.png': '8be4c10e976252da1909f1c0d25dcc998e95be024068e360a5b32fbaaf5b1ddc', 'madomagi/resource/image_native/memoria/memoria_1365_c.png': 'f261a035c094775252c25a995f4b876afde643bba19a325261d6292fe6dc118e'}
p=argparse.ArgumentParser()
p.add_argument('--root',type=Path,default=Path(__file__).resolve().parents[1])
p.add_argument('--zip',type=Path)
a=p.parse_args()
z=zipfile.ZipFile(a.zip) if a.zip else None
errors=[]
for name,expected in EXPECTED.items():
    try:
        b=z.read(name) if z else (a.root/name).read_bytes()
        assert b[:8]==b'\x89PNG\r\n\x1a\n'
        assert struct.unpack('>II',b[16:24])==(652,990)
        assert hashlib.sha256(b).hexdigest()==expected
    except (OSError,KeyError,AssertionError): errors.append(name)
if z:z.close()
if errors:
    print('FAIL Nanoha memoria repair: '+str(len(errors))+' missing, blank, or altered original images')
    for name in errors:print(name)
    raise SystemExit(1)
print('PASS Nanoha memoria repair: all 10 user-supplied 652x990 PNG originals match exactly')
