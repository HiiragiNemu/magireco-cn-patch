# DSV4 low-tier review terminal handoff

This directory is the byte-exact, deterministic terminal assembly for the v26
low-authority translation review. It is audit evidence only and is excluded
from `cn_js_update.zip`.

Terminal state:

- inventory: 1,912 items
- DSV4 reviewed: 1,472 items / 74 accepted batches
- approved: 1,390
- correction proposed: 37
- unresolved after review: 45
- DSV4-unreviewed manual handoff: 440
- total human decisions required: 522
- product-tree writes: 0
- protected authority changes: 0
- network-configuration writes: 0

Human reviewers should begin with `nonapproved_review.tsv` (all 522 decisions),
then use `human_review.tsv`, `full_review.tsv`, and `provenance.tsv` for full
context. `manifest.json`, `verification_record.json`, and `SHA256SUMS.txt` bind
the inventory and every generated artifact. `correction_patch.json` and
`rollback.json` target isolated low-tier staging only; unresolved rows and
protected authority text are not eligible for application.

Rebuild implementation: `tools/assemble-dsv4-v3-terminal.py`.

For the complete 522-row decision gate, copy `human_review.tsv`, fill only its
decision columns, and run `tools/validate-dsv4-human-review.py` against the
immutable `full_review.tsv`. The narrower
`tools/validate-dsv4-manual-decisions.py` validates only the 440 rows handed
over without a DSV4 verdict.
