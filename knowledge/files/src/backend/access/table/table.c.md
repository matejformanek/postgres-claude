# table.c

- **Source path:** `source/src/backend/access/table/table.c`
- **Lines:** 153
- **Last verified commit:** `ef6a95c7c64`
- **Companion files:** `table.h`, `access/common/relation.c` (the layer beneath), `tableam.c`, `tableamapi.c`.

## Purpose

Thin wrappers over `relation_open*` that ALSO enforce "this must be something you can do row-level access on" — i.e. the relkind is `r`, `S`, `t`, `v`, `m`, `f`, or `p` (regular table, sequence, toast value, view, matview, foreign table, partitioned table). Anything else gets `ERRCODE_WRONG_OBJECT_TYPE`. [from-comment, table.c:13-19]

## Top-of-file comment

> "Generic routines for table related code… This file contains table_ routines that implement access to tables (in contrast to other relation types like indexes) that are independent of individual table access methods." [from-comment, table.c:13-18]

## Public surface

- `table_open` (40) — `relation_open` + `validate_relation_as_table`.
- `try_table_open` (60) — `try_relation_open` + (if non-NULL) `validate_relation_as_table`.
- `table_openrv` (83), `table_openrv_extended` (103) — Same idiom, but the relation is identified by a `RangeVar` (name + optional schema).
- `table_close` (126) — Forwards to `relation_close` (no relkind validation needed on close).
- `validate_relation_as_table` (139, static inline) — The relkind guard; raises with `errdetail_relkind_not_supported` on mismatch.

## Key invariants

- These wrappers accept `RELKIND_SEQUENCE` and `RELKIND_TOASTVALUE` — both have heap storage and are accessed via the tableam interface, so they are legitimate "tables" to `table_open`. (The narrower `sequence_open` exists for callers that specifically want SEQUENCE-only.) [verified-by-code, table.c:140-153]
- These wrappers DO NOT validate that the relation has physical storage — view/foreign-table-attached callers must still check before reading from the heap. [from-comment, table.c:33-36]
- All locking semantics inherit from `relation_open` — including the "lock first, then look up" rule. [inferred, table.c is a thin wrapper]

## Cross-references

- Direct callers: nearly every backend that touches user data (executor, copy, vacuum, analyze, ANALYZE, DDL).
- Most calls into the per-AM API (`tableam.h` inline wrappers) require a Relation opened by `table_open` — i.e. `rd_tableam` is non-NULL.

## Confidence tag tally
`[verified-by-code]=4 [from-comment]=2 [from-readme]=0 [inferred]=1 [unverified]=0`

## Synthesized by
<!-- backlinks:auto -->
- [subsystems/optimizer.md](../../../../../subsystems/optimizer.md)
