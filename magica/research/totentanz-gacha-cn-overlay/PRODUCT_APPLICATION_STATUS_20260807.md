# Product application status — 2026-08-07

Base: `research/totentanz-magica-cn-overlay-pass9-final-20260807@f25b445d7bcb9b9710f51d82ca9330995185d623`

## Materialized in this branch

The following current-Totentanz product files are committed with the audited CN text layer:

- `magica/js/gacha/GachaResult.js` — official `协助Pt`
- `magica/template/campaign/gacha_lineup/CampaignGachaLineUp.html` — official `可选对象一览`
- `magica/template/gacha/GachaProbabilityPop.html` — official `掉落率` / `Pickup对象魔法少女` / `Pickup对象记忆结晶`
- `magica/template/gacha/GachaResult.html` — current-only result template; absent from v3/pass8
- `magica/template/gacha/SelectableGachaCharaSelect.html` — official legacy types + explicitly supplemental post-CN-service types
- `magica/template/gacha/SelectableGachaPieceSelect.html` — official selectable-memoria wording

`magica/template/gacha/GachaAnimation.html` already matched the audited output on the base branch and therefore has no product diff.

## Audited/generated but not promoted as product bytes yet

The canonical generator `apply_gacha_overlay.py` also produces and hash-verifies these current-structure outputs:

- `magica/js/campaign/box_gacha/CampaignBoxGachaTop.js`
- `magica/template/campaign/box_gacha/CampaignBoxGachaTop.html`
- `magica/template/gacha/GachaTop.html`

Their expected SHA-256 values are recorded by the generator/audit. They remain generated-only in this branch rather than accepting any non-byte-exact transfer. Run the generator from a clean checkout and verify its fail-closed hashes before promoting these three files.

This distinction is intentional: do not report the branch as a fully materialized 10-file gacha product overlay until those three generated outputs are promoted byte-for-byte.

## Preservation boundary

No `magica/css/**`, image/resource, route, selector, Puella Historia, or pass9 runtime-dictionary file is changed by the materialized product diff. Current Totentanz remains the structural/UI base.
