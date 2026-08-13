# Product application status — 2026-08-07

Base authority/integration line: `research/totentanz-magica-cn-overlay-pass9-final-20260807@de8d97378f2c87c9927d232cb56d9331181de7d8`

Final isolated materialization base: `research/totentanz-gacha-cn-authority-20260807@a25ca643aee8b10df720c038550f245cf605c5e4`

## Fully materialized product layer

All audited current-Totentanz gacha outputs are now present as product bytes on this final isolated branch:

- `magica/js/gacha/GachaResult.js` — official `协助Pt`
- `magica/js/campaign/box_gacha/CampaignBoxGachaTop.js` — reward-box terminology and popup wording materialized
- `magica/template/campaign/box_gacha/CampaignBoxGachaTop.html` — reward-box terminology and draw-confirmation wording materialized
- `magica/template/campaign/gacha_lineup/CampaignGachaLineUp.html` — official `可选对象一览`
- `magica/template/gacha/GachaTop.html` — official `可选对象一览` / `获得履历` / `卡池一览`
- `magica/template/gacha/GachaProbabilityPop.html` — official `掉落率` / `Pickup对象魔法少女` / `Pickup对象记忆结晶`
- `magica/template/gacha/GachaResult.html` — current-only result template; absent from v3/pass8
- `magica/template/gacha/SelectableGachaCharaSelect.html` — official legacy types + explicitly supplemental post-CN-service types
- `magica/template/gacha/SelectableGachaPieceSelect.html` — official selectable-memoria wording

`magica/template/gacha/GachaAnimation.html` already matched the audited output before this final materialization and therefore requires no product diff.

The canonical fail-closed generator remains `apply_gacha_overlay.py`; its expected SHA-256 table is the byte-level contract for the audited outputs.

## Isolation / preservation boundary

The final branch was created from the pre-materialization clean head `a25ca643aee8b10df720c038550f245cf605c5e4` and the three remaining product blobs were attached in one isolated Git commit. This intentionally excludes an unrelated concurrent workflow change observed on the older working research branch.

The final three-file product delta contains only:

- `magica/js/campaign/box_gacha/CampaignBoxGachaTop.js`
- `magica/template/campaign/box_gacha/CampaignBoxGachaTop.html`
- `magica/template/gacha/GachaTop.html`

No `magica/css/**`, image/resource, route, selector, Puella Historia, `magica/js/libs/**`, pass14 runtime layer, or other branch ref is modified by this final materialization. Current Totentanz remains the structural/UI base.
