# Manual visible text closure — round 3

This layer closes player-visible strings that were absent from the official CN
client and from the Wiki authority layer.

- Inventory: **124** records.
- Product writes: **120** careful root translations.
- Retained/no-op: **4** records (two image-only help entries and two legal
  licence bodies).
- Human-review status: the 120 product writes are deliberately marked
  `not-yet-human-reviewed` and `rough-production-root-translation`.
- Authority order: official CN > Wiki > confirmed human > this layer.

The stable item manifest is `manual_translation_round3.json`; the tabular copy
is `manual_translation_round3.tsv`. Transactional inputs, exact before/after
hashes and per-file rollback material are stored under `runtime/`.

The applied product scope is limited to eight files:

- `magica/css/patrol/PatrolDeckView.css`
- `magica/css/regularEvent/groupBattle/RegularEventGroupBattleRanking.css`
- `magica/css/regularEvent/groupBattle/RegularEventGroupBattleUser.css`
- `magica/js/event/EventWalpurgis/json/stamp/commentList.json`
- `magica/json/announcements/announcements.json`
- `magica/json/event_banner/event_banner.json`
- `magica/resource/image_web/_json/SecondPartLastInfo.json`
- `magica/resource/image_web/_json/help.json`

Later verified layers may add unrelated changes to the same file. Verification
therefore protects every round-3 replacement while allowing only explicitly
declared later-layer changes; it does not rewrite a file back to an older
snapshot.
