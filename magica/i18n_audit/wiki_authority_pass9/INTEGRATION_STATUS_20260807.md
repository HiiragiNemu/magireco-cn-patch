# Wiki authority / Totentanz integration status — 2026-08-07

## Branches and commits

- Authoritative text branch: `wiki-authority-cn-pass9-20260806`
- First authority commit: `1b43d5a9dfc269f4d7121e188161273d5f207d15`
- Reproducibility follow-up (the authority branch second commit): `b00812febaa3164bdf68422dca09f11aa59f255e`
- Parallel Totentanz branch audited here: `research/totentanz-magica-cn-overlay-20260806`
- Parallel branch head at integration fork: `214c962e24d30532468a3d5fd7268e06559cb419`
- Final integration branch: `research/totentanz-magica-cn-overlay-pass9-final-20260807`

## Authority result

The current `wiki-data` working HEAD is the same Wiki snapshot already pinned by pass9;
no newer Wiki corpus was available after the pass9 review. The accepted evidence remains:

- official CN client/dump protected fields: 57,056, with zero authority collisions;
- reviewed Wiki proposals: 5,678 accepted / 0 rejected;
- LLM Doppel recheck: 114 records / 342 fields; 189 fields replaced from Wiki and 153 already equivalent;
- residual `llm_or_other`: 11,055 tracked fields retained fail-closed because no independent
  baseline/dump/Wiki identity was proven.

Do not reduce the residual number by cross-ID or weak fuzzy substitution. A lower number without
source identity would reduce authority rather than improve it.

## Direct merge layer

Use these as the Chinese authority layer for runtime dictionary text:

- `magica/js/libs/*.json` — exactly 23 dictionaries;
- `magica/js/libs/jquery-3.7.1.min.js` — the same dictionaries embedded in the audited safe wrapper;
- `Build_JS_Injector.py` — deterministic fail-closed rebuild;
- `magica/i18n_audit/wiki_authority_pass9/` — provenance and verification records.

Source priority when resolving text conflicts:

1. official CN APK/decrypted dump, same semantic ID and field;
2. protected baseline CN values and creator/proper-name fields;
3. Wiki typed/keyed same-entity Chinese;
4. reviewed exact/typed Wiki mapping with numeric/scope/structure signatures preserved;
5. residual pass8 LLM/other only when no stronger independent authority exists.

Current `main` and historical automation branches may contain broader *coverage* from heuristic or
machine-assisted merges, but those values do not supersede a pass9 field with dump/Wiki provenance.
For pass9 residual fields they are candidates only after per-string evidence.

## Reproducibility P0

Resolved by the authority second commit and copied into the final integration branch:

- fixed explicit 23-dictionary list/order;
- LF checkout/output policy;
- original jQuery SHA-256 pin;
- audited runtime prefix/suffix SHA-256 pins;
- manifest updated to Git/CI bytes;
- jQuery frozen at 5,058,057 bytes / SHA-256
  `56eab41dfb5691da806a831dfd86dfe2aab59800d0dddf06465077ef978af925`;
- isolated double-build verifier requires A == B == committed jQuery and manifest 24/24.

The parallel branch's own `1c3a9115...` reproducibility commit was directionally correct, but used
the current jQuery wrapper as an implicit canonical input. The final integration deliberately uses
the stricter pass9.1 builder that refuses an unreviewed wrapper drift.

## Totentanz overlap / preserve boundary

The authority runtime product layer (`23 JSON + jQuery`) does not overlap the Totentanz new UI/CSS
product files. Preserve the parallel branch's current UI/CSS/routes/images, including its
`MailSendTest`, `SdCharaTest`, `ShopReworkTest`, campaign/event/Puella Historia work and
`magica/research/totentanz-cn-overlay/**` evidence.

The actual overlap between the pass9.1 follow-up and the parallel branch's own reproducibility work
is infrastructure/audit only:

- `.gitattributes`
- `Build_JS_Injector.py`
- `magica/i18n_audit/wiki_authority_pass9/layer_manifest.json`
- `magica/i18n_audit/wiki_authority_pass9/LAYER_SHA256SUMS.txt`
- verification scripts/records under `magica/i18n_audit/wiki_authority_pass9/`

No Totentanz production CSS/UI/image is replaced by the final pass9.1 integration commits.

## Rollback P0

The previous default expression referenced a missing
`magica/research/totentanz-cn-overlay/patches/runtime-overlay.patch` and could fail before its own
patch check. The final integration changes the rollback contract to fail closed:

- default rollback uses the fixed baseline `3c983a778429d5e56a2569aa28ea8c622d988c63`;
- refuses dirty target paths;
- verifies the baseline is an ancestor;
- restores `.gitattributes`, `Build_JS_Injector.py`, `magica/`, and the sync workflow directly from
  the baseline with Git, which also restores binary files;
- verifies both worktree and index against the baseline;
- an explicit `-PatchPath` remains supported when a separately generated binary patch is supplied.

A self-contained patch committed *inside* `magica/` cannot simultaneously cover all of `magica/`
and delete itself while satisfying an exact post-rollback `magica/ == baseline` check; that is a
self-reference problem. The baseline restore removes the missing-patch dependency instead of
pretending a self-referential patch is reproducible.

The chat execution container has no GitHub DNS access and no PowerShell runtime, so the final
PowerShell rollback path was not executed against an isolated remote checkout here. Do not label
that one check as executed until it is run in a Windows/PowerShell clone. The runtime-layer double
build and 24/24 manifest verification *were* executed locally on the reconstructed audited bytes.

## Remaining non-production note

The independent review's terminology note for the test-only `ShopReworkTest.html` remains separate
from the authority runtime layer: its sample label `每日币` should be normalized to the established
`每日硬币` if that test page is being polished for human-facing use. It does not affect production
runtime dictionary injection.
