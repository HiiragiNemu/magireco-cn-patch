"""User-requested original APNG restoration, not a generated/static substitute."""
import argparse,hashlib,struct
from pathlib import Path
p=argparse.ArgumentParser();p.add_argument('--root',type=Path,default=Path(__file__).resolve().parents[1]);a=p.parse_args()
b=(a.root/'magica/resource/image_web/common/global/connecting.png').read_bytes()
assert hashlib.sha256(b).hexdigest()=='7d44ac8d75074abaaf0e122ae3fcb96eca910cf59c75ceef44c06c25ddd453ab'
n=8;chunks=[]
while n<len(b):
    length=struct.unpack('>I',b[n:n+4])[0];typ=b[n+4:n+8];data=b[n+8:n+8+length];chunks.append((typ,data));n+=length+12
actl=next(data for typ,data in chunks if typ==b'acTL');assert struct.unpack('>II',actl)==(8,0)
assert sum(typ==b'fcTL' for typ,data in chunks)==8
print('PASS exact previous Connecting APNG: 8 frames, infinite loop')
