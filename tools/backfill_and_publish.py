#!/usr/bin/env python3
"""Apply reviewed localization decisions with backups and a deterministic report.

Input TSV columns: path, key (or stable_key), original (or source), replacement
(or suggested/current), decision. Rows with decision=accept/fill/replace are applied.
All edits are backed up under .backfill-backups/<timestamp>; originals are checked
before replacement. Use --check to validate without writing.

Publication is intentionally separate from this helper. The retired
publish-final.yml workflow no longer exists; use the active release workflow after
reviewing the generated report.
"""
from __future__ import annotations
import argparse, csv, hashlib, json, shutil, time
from pathlib import Path

ACCEPT = {"accept","accepted","fill","replace","approved","use"}

def sha(p: Path) -> str:
    return hashlib.sha256(p.read_bytes()).hexdigest()

def field(row, *names):
    for n in names:
        if row.get(n): return row[n]
    return ""

def main() -> int:
    ap=argparse.ArgumentParser()
    ap.add_argument("--review", required=True, type=Path)
    ap.add_argument("--root", type=Path, default=Path("."))
    ap.add_argument("--check", action="store_true")
    args=ap.parse_args(); root=args.root.resolve()
    rows=list(csv.DictReader(args.review.open(encoding="utf-8-sig",newline=""), delimiter="\t"))
    ops=[]
    for i,r in enumerate(rows,1):
        if field(r,"decision","status").strip().lower() not in ACCEPT: continue
        rel=field(r,"path","file","target_path"); old=field(r,"original","source","ja"); new=field(r,"replacement","suggested","current","zh")
        if not rel or not old or not new: raise SystemExit(f"row {i}: path/original/replacement missing")
        p=(root/rel).resolve()
        if root not in p.parents and p != root: raise SystemExit(f"row {i}: path outside root: {rel}")
        if not p.is_file(): raise SystemExit(f"row {i}: missing target: {rel}")
        text=p.read_text(encoding="utf-8")
        count=text.count(old)
        if count != 1: raise SystemExit(f"row {i}: expected one original in {rel}, got {count}")
        ops.append((p,old,new,rel))
    if args.check:
        print(json.dumps({"rows":len(rows),"accepted":len(ops),"mode":"check"},ensure_ascii=False)); return 0
    stamp=time.strftime("%Y%m%dT%H%M%SZ",time.gmtime()); backup=root/".backfill-backups"/stamp
    if not ops: raise SystemExit("no accepted rows")
    for p,old,new,rel in ops:
        dest=backup/rel; dest.parent.mkdir(parents=True,exist_ok=True); shutil.copy2(p,dest)
    changed=[]
    for p,old,new,rel in ops:
        s=p.read_text(encoding="utf-8"); p.write_text(s.replace(old,new,1),encoding="utf-8"); changed.append(rel)
    for p,old,new,rel in ops:
        s=p.read_text(encoding="utf-8")
        if old in s or new not in s: raise SystemExit(f"post-check failed: {rel}")
    report={"timestamp":stamp,"accepted":len(ops),"changed":changed,"backup":str(backup),"sha256":{rel:sha(root/rel) for rel in changed}}
    (root/"backfill-report.json").write_text(json.dumps(report,ensure_ascii=False,indent=2),encoding="utf-8")
    print(json.dumps(report,ensure_ascii=False,indent=2))
    return 0
if __name__ == "__main__": raise SystemExit(main())
