# Independent proposal review

- Proposal SHA-256: `b8da9d62b6ab26410d000cc630e6b72662eb81a9d93c88f8113d9aa25ba9173e`
- Reviewed: 5678
- Accepted: 5678
- Rejected: 0
- Official dump lock collisions: 0

## Emotion mapping

- Total reviewed: 1726
- Fuzzy: 1472 (minimum ratio 0.820512821; below 0.90: 130)
- Bipartite: 149 (minimum ratio 0.514285714; below 0.70: 24)
- Numeric signature failures: 0
- Conjunct-count failures: 0
- Scope signature failures: 0
- Typed Wiki-page membership failures: 0

## Global unique exact

- Total reviewed: 155
- Baseline/source exact failures: 0
- Reproduced Wiki-pair failures: 0

## Doppel

- LLM set: 114 records / 342 fields
- Equivalence states: `{"ALREADY_EQUIVALENT": 153, "PROPOSED_CORRECT": 189}`
- Three-dictionary name groups: 217; split or missing: 0

## Residual interpretation risks

- `wiki_emotion_typed_bipartite` remains an inferred one-to-one assignment, but every accepted row is constrained to the same character page and preserves all numeric, conjunction, and scope signatures.
- `wiki_global_unique_exact` is exact on normalized Japanese but has weaker typed context than keyed methods; every accepted row reproduces a unique Wiki pair and passes the target-field checks.
- Wiki community wording is treated as the requested authority even when less polished than the LLM text; this review tests provenance, identity, structure, and alignment rather than stylistic rewriting.
- `pieceList.json/1285` uses `家常便贩` intentionally: `memoria.notes` documents the `日常自販機` / `日常茶飯事` pun.
- Memoria 1749 deliberately retains `(ry`, mirroring the source's internet-slang truncation rather than an unmatched-parenthesis defect.

## Source identity

- Working repository HEAD: `42641f87818b37262032fd4dc5d5c756a48fed7a`
- i18n reference branch: `186326575607a98c1f1810fa09ada67016420145`
- Both commits resolve `data/` to tree `9495350e70fbdbf03970b008c05aa006a823c11d`.
