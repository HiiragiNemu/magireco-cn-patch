"""The user-approved compose-item repair must be distributed, not device-local."""
import argparse
import hashlib
from pathlib import Path

p = argparse.ArgumentParser()
p.add_argument('--root', type=Path, default=Path(__file__).resolve().parents[1])
a = p.parse_args()
name = 'madomagi/resource/image_native/item/compose_item_xxx_b.png'
f = a.root / name
expected = 'a5ea45b39484a2a0aa3e36b5a47a2f3485877fa6bffc20bf490162cb8d08c481'
actual = hashlib.sha256(f.read_bytes()).hexdigest() if f.is_file() else None
if actual != expected:
    print('FAIL compose-item public repair: missing or old image; actual=' + str(actual))
    raise SystemExit(1)
print('PASS compose-item public repair: exact user-approved PNG')
