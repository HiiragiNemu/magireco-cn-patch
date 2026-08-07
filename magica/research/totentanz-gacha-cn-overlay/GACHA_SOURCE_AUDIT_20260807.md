# Gacha source audit — 2026-08-07

## Decision

The gacha localization is **not** a single-source problem.

- `cn_js_update_v3.zip` and pass8 already contain most legacy/static gacha override files, but they do not prove coverage of the current Totentanz frontend.
- pass8 contains 7 of the 8 current visible-text targets selected for this pass. It does **not** contain the current `template/gacha/GachaResult.html`.
- the 2022 decrypted dump contains `api/page/GachaTop`, `api/page/GachaHistory`, and many `api/gacha/result` responses, so it is authoritative for dynamic API data. It does not contain the static UI labels `协助Pt`, `掉落率`, or `获得履历`.
- `magicaOLD.7z` is therefore still required as the strongest source for static CN UI wording. Current Totentanz is still required as the structural base because the old CN client predates Puella Historia and later gacha/UI features.

## Input hashes

- `magicaOLD.7z`: `ee1f1cf622c245ac45f565f73e88473f4b8b45889941edf2b5646ee8155d1c94`
- `totentanz-frontend.tar.xz`: `a0442432fffd9c18ad9186bd2c1f7572dad5912c4b71490c706abad299d7dbf9`
- `cn_js_update_v3_authoritative_cn_dump_pass8_final.zip`: `e4b466d6cb6c16ec018b61c7d074e2d213601889e758ef6db4dc4dd041c54e53`
- `magireco_cn_dump_20221010_decrypted_json.zip`: `30eec8ab72947521f7e6c8593c7adeb3e9b107c5528701faa50f32cdfdb5f4db`
- `cn_js_update_v3.zip`: `d2ecfe9418b8e3b64bc39610ed645d9f65786df1987c081be134d3ea4efc97c4`

## Current visible-text targets

1. `magica/js/campaign/box_gacha/CampaignBoxGachaTop.js`
2. `magica/js/gacha/GachaResult.js`
3. `magica/template/campaign/box_gacha/CampaignBoxGachaTop.html`
4. `magica/template/gacha/GachaAnimation.html`
5. `magica/template/gacha/GachaResult.html` — absent from v3/pass8; current Totentanz source is mandatory
6. `magica/template/gacha/SelectableGachaCharaSelect.html`
7. `magica/template/gacha/SelectableGachaPieceSelect.html`
8. `magica/template/campaign/gacha_lineup/CampaignGachaLineUp.html`

The previously selected 11-file baseline also includes three string-free controllers that are retained byte-for-byte from Totentanz. Two adjacent controllers (`js/gacha/GachaAnimation.js` and `js/campaign/gacha_lineup/CampaignGachaLineUp.js`) were also scanned and contain no visible CJK string literals, so no override is justified.

## Authority order for gacha UI

1. old official CN frontend (`magicaOLD.7z`) when the same UI slot/semantics exist;
2. official CN APK / decrypted 2022 dump for same semantic API ID/field;
3. pass9 typed/keyed Wiki evidence;
4. pass8 only where it preserves a newer current slot and no stronger official value exists;
5. narrow manual translation for genuinely post-CN-service UI only, explicitly marked non-official.

Do not use automation/main wording merely because it is newer. Current repository text such as `获得记录`, `抽卡概率一览`, `出货率`, and `支援Pt` is lower-authority than the old official CN terms for the corresponding slots.

## Locked terminology

- `ガチャ` → `扭蛋`
- `サポートPt` → `协助Pt`
- probability tab `排出率` → `掉落率`
- history button → `获得履历`
- GachaTop probability button → old official `卡池一览`

## Structural safety

The current Totentanz files, not old CN/pass8 files, are the base for all eight current visible-text targets. Only text/string slots are changed. Validation performed locally:

- modified JS: `node --check` passed;
- current HTML sensitive attributes (`id`, `class`, `href`, `src`, `name`, `data-*`): zero drift;
- EJS `<%` / `%>` delimiter counts: unchanged for all current HTML targets;
- banned low-authority terms (`支援Pt`, `获得记录`, `抽卡概率一览`, `出货率`): zero in this layer;
- required terminology (`扭蛋`, `协助Pt`, `掉落率`, `获得履历`): present.

## New post-CN-service character types

The old CN frontend only supplies official labels for `BALANCE/ATTACK/DEFENSE/MAGIA/HEAL/SUPPORT` (`平衡/攻击/防御/Magia/治疗/协助`) and the labels `Connect` / `Magia`. Later `initialType` values do not have an old CN official counterpart. The Wiki repository search did not yield keyed Chinese entries for `円環マギア` or `ラストコネクト`, so these later type labels are explicitly lower-authority supplemental translations and must not be reported as official CN wording.

## CSS/UI preservation boundary

This gacha pass changes no CSS, image, route, selector, element id/class, or Puella Historia UI file. Do not replace current Totentanz CSS with old CN CSS. The pass9 integration branch's existing Totentanz UI/CSS preservation boundary remains authoritative.
