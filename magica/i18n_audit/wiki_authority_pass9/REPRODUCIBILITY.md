# Wiki authority pass9.1 — reproducibility freeze

This follow-up fixes the repository-level reproducibility blocker found after pass9 was integrated.
It does **not** change any of the 23 authoritative JSON dictionaries or Totentanz UI/CSS/assets.

## Recheck of translation authority

The current `HiiragiNemu/wiki-data` default branch still resolves to
`42641f87818b37262032fd4dc5d5c756a48fed7a`, the exact Wiki working HEAD already pinned and
reviewed by pass9. There is therefore no newer Wiki corpus to mine after pass9.

The fail-closed source result remains:

- 57,056 CN client/dump authority fields preserved with zero collisions.
- 5,678 Wiki proposals reviewed and accepted.
- 114 LLM Doppel records / 342 fields rechecked against Wiki: 189 fields replaced by Wiki,
  153 already equivalent.
- 11,055 fields remain conservatively classified `llm_or_other` because no independent
  baseline/dump/Wiki identity was proven. They are **not** promoted by fuzzy guessing merely to
  reduce the residual count.

For the 23 runtime dictionaries, this pass9 layer is the preferred authority over the current
`main`/automation text when they disagree. Current `main` contains useful newer UI/runtime work
and heuristic translation merges, but it does not supersede the field-level dump/Wiki provenance
ledger. Translation-only values from other branches may be merged only with per-string evidence.

## Root cause of the pass9 P0

The first pass9 repository snapshot mixed three different byte/behavior states:

1. `layer_manifest.json` recorded the pre-commit Windows CRLF jQuery
   (`5,058,264` bytes, SHA-256 `b8a0ff7c...`).
2. Git stored the same audited file normalized to LF
   (`5,058,057` bytes, SHA-256 `56eab41d...`).
3. CI rebuilt jQuery with the repository's stale `Build_JS_Injector.py`, producing a third file.

The third state was not only a byte-order/newline problem. The root builder still contained an
older runtime translator. Rebuilding with it could reintroduce cross-dictionary skill guessing,
creator-field rewriting, and less strict schema preservation that pass8-final had already fixed.

## Fix

- `Build_JS_Injector.py` now preserves the exact audited safe runtime code already present in
  pass9 jQuery and fails closed if the code outside the dictionary payload changes.
- Dictionary order is an explicit 23-name tuple; the build fails if a dictionary is missing or an
  unexpected JSON appears.
- Original jQuery and the audited prefix/suffix are SHA-256 pinned.
- Output is emitted as UTF-8 bytes with LF only; no platform newline conversion is used.
- `.gitattributes` pins the builder, original jQuery, 23 dictionaries, generated jQuery and audit
  records to LF.
- `layer_manifest.json` and `LAYER_SHA256SUMS.txt` now describe Git/CI bytes, not a pre-commit
  Windows worktree.
- `verify_reproducible_build.py` performs manifest 24/24 verification and two isolated rebuilds.

## Frozen result

```text
23 JSON dictionaries: manifest 23/23
jQuery:               5,058,057 bytes
jQuery SHA-256:        56eab41dfb5691da806a831dfd86dfe2aab59800d0dddf06465077ef978af925
isolated build A:      same bytes / same SHA-256
isolated build B:      same bytes / same SHA-256
A == B:                yes
A == committed jQuery: yes
Node syntax:           pass
manifest:              24/24
```

Machine-readable output is in `repository_reproducibility_verification.json`.

## Merge boundary

Directly reusable Chinese authority layer:

- `magica/js/libs/*.json` — exactly 23 files;
- the dictionary payload inside `magica/js/libs/jquery-3.7.1.min.js`;
- the deterministic root `Build_JS_Injector.py` and pass9 audit records.

Do **not** replace Totentanz's current CSS/UI/routes/fonts/images with the old 401-file archive.
In particular, preserve the files listed in `preserve_paths.txt` and all files under the parallel
`magica/research/totentanz-cn-overlay/` work unless deliberately integrating its own follow-up.
