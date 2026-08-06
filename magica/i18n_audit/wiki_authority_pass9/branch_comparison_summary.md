# patch-front branch comparison

Generated: `2026-08-06T19:41:33+08:00`

## Recommendation

Use `pass8_final` (`e4b466d6cb6c16ec018b61c7d074e2d213601889e758ef6db4dc4dd041c54e53`) as the current text baseline, then
apply Wiki-authority replacements. Keep `origin/main` as the repository/branch base,
but merge its translation-only changes selectively and only with per-string evidence.

## Remote heads

| Ref | Commit | Date | magica tree | Files |
|---|---|---|---|---:|
| `origin/main` | `3c983a778429` | `2026-08-06T05:40:28Z` | `045f7cf6203a` | 415 |
| `origin/automation/full-cn-v4-20260804` | `71fe2f9f3296` | `2026-08-04T10:13:00+08:00` | `5c6a6d936e97` | 401 |
| `origin/automation/full-cn-v4-run-20260804` | `800f80cbf364` | `2026-08-04T10:13:14+08:00` | `5c6a6d936e97` | 401 |
| `origin/temp/scenario-sync-20260731-2345` | `177acfcc1fd5` | `2026-08-01T02:33:42+08:00` | `8c5f90eef326` | 24 |


## Key findings

- The two automation heads have the same `magica` tree and zero `magica` diffs.
- The automation run branch is byte-identical to v3 in
  `400/401` files;
  only `magica/js/libs/jquery-3.7.1.min.js` differs.
- pass8 differs from automation in `176`
  files and from main in `196` files.
- main versus pass8 structured JSON text: `24655`
  differing cells. Of `26260` pass8 text
  improvements/additions, main matches
  `2215`, remains at baseline
  for `2911`, has another
  value for `13094`, and is
  missing `8040`.
- pass8 supplies auditable official CN APK/dump authority, 57,056 checked authority
  fields, 130,208/130,208 dump occurrences, 28,987 runtime cases, and 6,195 provenance
  rows. The automation scripts use Google/Argos; their head commits did not change
  checked-in `magica` content.

See `branch_comparison_report.json` for complete metrics and
`pass8_vs_main_json_text_diff.tsv` for field-level review.
