# Visible residue closure — round 4

This layer handles the stable player-visible residue found after round 3.

- Product changes: **39** across **6** primary files.
- Wiki authority changes: **7** (`Kyubert` and the mixed title are resolved to
  the stable Wiki name `小丘比`).
- New careful root translations: **32**.
- Protected authority retained unchanged: **0**.

The old CN client and Wiki were checked before fallback translation. For the
remaining English/Japanese story labels they either retained the source text or
had no Chinese value, so those fields are honestly tagged
`new-root-translation` and `not-yet-human-reviewed`; they are not represented as
official or Wiki Chinese.

`closure_manifest.json` is the stable-key source of truth. The runtime folder
contains prepared bytes, exact before/after hashes, rollback state and modified
and rollback verification records. `jquery-3.7.1.min.js` is regenerated from
the standalone dictionaries and is never edited as an independent authority
source.
