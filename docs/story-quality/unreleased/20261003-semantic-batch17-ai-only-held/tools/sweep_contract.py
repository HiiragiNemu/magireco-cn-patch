"""Validate traceable residual-review coverage; this does not automate semantic judgment."""
from __future__ import annotations
import hashlib
import json
from collections import Counter
from typing import Any


def encoded(value: Any) -> bytes:
    return (json.dumps(value, ensure_ascii=False, indent=2) + '\n').encode('utf8')


def validate_coverage(source: list[dict], slices: list[dict], require_complete: bool = True) -> dict:
    if [row['sweep_id'] for row in source] != list(range(len(source))):
        raise ValueError('Source IDs are not an exact sequential frozen set')
    seen: dict[int, dict] = {}
    for part in slices:
        decisions = part['rows']
        if not decisions:
            raise ValueError('Empty review slice')
        ids = [r['sweep_id'] for r in decisions]
        if ids != list(range(ids[0], ids[-1] + 1)) or ids[0] < 0 or ids[-1] >= len(source):
            raise ValueError('Slice must contain a contiguous in-range source span')
        selected = source[ids[0]:ids[-1] + 1]
        if hashlib.sha256(encoded(selected)).hexdigest() != part['slice_sha256']:
            raise ValueError('Slice source hash mismatch')
        for src, dec in zip(selected, decisions, strict=True):
            num = dec['sweep_id']
            if num in seen:
                raise ValueError('Duplicated review row')
            for key in ['id', 'ordinal', 'address']:
                if dec[key] != src[key]:
                    raise ValueError('Source identity/address drift')
            if dec['japanese'] != src['jp'] or dec['prior_candidate'] != src['cn']:
                raise ValueError('Source Japanese/current Chinese drift')
            if not isinstance(dec.get('rationale'), str) or not dec['rationale'].strip():
                raise ValueError('Missing review rationale')
            if dec['disposition'] not in ('retain', 'correct'):
                raise ValueError('Unresolved disposition')
            if (dec['after'] == src['cn']) != (dec['disposition'] == 'retain'):
                raise ValueError('Disposition contradicts actual text change')
            seen[num] = dec
    pending = sorted(set(range(len(source))) - set(seen))
    if require_complete and pending:
        raise ValueError('Review coverage has gaps')
    corrected = [r for r in seen.values() if r['disposition'] == 'correct']
    return {
        'source_fields': len(source), 'reviewed_fields': len(seen),
        'retained_fields': sum(r['disposition'] == 'retain' for r in seen.values()),
        'corrected_fields': len(corrected),
        'source_scripts': len({r['id'] for r in source}),
        'amended_scripts': len({r['id'] for r in corrected}),
        'pending_fields': len(pending),
        'pending_scripts': len({source[i]['id'] for i in pending}),
        'new_full_review_stories': 0, 'passed': not pending,
        'boundary': 'Coverage and source identity only; semantic judgments remain explicit saved decisions.'
    }
