# engine_i18n unknown 212 semantic quality audit

- Scope: 212 rows previously carrying an unknown source tier.
- Accepted current wording: 172.
- Corrections proposed: 40 (high 8, medium 25, low 7).
- Exact official CN native proposals: 35; root semantic proposals: 5.
- Product writes made by the audit export itself: 0.

## UTF-8 binding

Every review record is rebuilt from the current UTF-8 `madomagi/engine_i18n.tsv`, not from a recoded export. The binding consists of `row_id`, one-based physical line, exact Japanese source, and exact current Chinese value. The sidecar uses schema 2 and includes all four fields. Any line movement, source drift, current-value drift, duplicate ID, missing review row, or correction-set mismatch fails closed.

## Formal mechanism terms

`Accele`, `Blast`, `Charge`, `Magia`, `Puella Historia`, `Survive`, `Variable`, `Navi`, and `JC` remain when they are formal game or mechanism names.

## Application and rollback

The sidecar remains audit-only and every row retains `product_write_allowed=false`.
`tools/apply-engine-final-root-review.py` is the separate fail-closed product
operation. It changed exactly 40 rows in `madomagi/engine_i18n.tsv`: 35 exact
dual-ABI official-CN strings and five root-reviewed semantic corrections. The
recorded sequence `apply -> verify -> rollback -> verify -> reapply` passed, and
the final product is in the applied state with all 212 source/line/target
bindings verified. The rollback manifest contains only those 40 rows.

The original 212-row exact-before verification is retained as
`engine_unknown_212_preapply_binding_verification.json` and explicitly marked
as a pre-application snapshot. Current-state evidence is in
`engine_unknown_212_application_verification.json` and
`engine_unknown_212_roundtrip_verification.json`.

## Machine-review integration

The schema-2 sidecar is consumed only after all existing official, Wiki, and
confirmed-human branches. Two reviewed rows (`Survive` and `Variable`) remain
under their stronger Wiki formal-mechanism records. The sidecar therefore
takes over 210 rows: 35 official exact and 175 manual-semantic-reviewed. The
generated engine partition is 58 official, 252 root-reviewed, 3 Wiki, and 1
intentional structural fragment; unverified is zero. Historical
`origin_machine_translated=unknown` remains visible in evidence and notes and
is not rewritten as official/Wiki provenance.
