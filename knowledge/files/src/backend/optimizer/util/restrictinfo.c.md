# restrictinfo.c — RestrictInfo node construction and classification

- **Source:** 678 lines · **Last verified commit:** `ef6a95c7c64`
- **Depth:** read

## Purpose

The RestrictInfo wraps a qual expression with planner-useful metadata
(required_relids, clause_relids, security_level, pseudoconstant flag,
join_relids, …). Lazy initialization: many fields depend on context and
are filled later. [from-comment:42-48]

## Public entries

- `make_restrictinfo(...)` (51) — main builder.
- `make_plain_restrictinfo` (102) — internal/recursive entry, also used
  for inner OR's RestrictInfos.
- `commute_restrictinfo(rinfo, comm_op)` (349) — make a commuted variant
  for derived index quals; shares sub-structure with source.
  [from-comment:340-346]
- `restriction_is_or_clause` (406), `restriction_is_securely_promotable`
  (421) — security_level check for safe early evaluation.
- `get_actual_clauses` (459) — strip RestrictInfo wrappers; only safe
  when no pseudoconstants present. [from-comment:453-457]
- `extract_actual_clauses(list, pseudoconstant)` (484) — split bare
  clauses by pseudoconstant flag; constant-TRUE always dropped.
- `extract_actual_join_clauses` (512) — for outer joins: separate
  pushed-down from join-level. [from-comment:505-511]
- `clause_is_computable_at(rinfo, relids)` style helpers (574),
  `join_clause_is_movable_into` (660) — clause placement legality
  during parameterized-path generation. Rejects `is_clone` variants to
  prevent duplicate parameterized paths differing only in OJ nullingrel
  bits. [from-comment:563-572]

## Tags
`[verified-by-code]` ×3, `[from-comment]` ×6
