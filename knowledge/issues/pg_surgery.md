# Issues — `contrib/pg_surgery`

Heap-surgery extension (`heap_force_kill`, `heap_force_freeze`). 1 source file / ~421 LOC.

**Parent docs:** `knowledge/files/contrib/pg_surgery/heap_surgery.c.md`.

**Source:** 4 entries surfaced 2026-06-09 by A14-1.

## Headlines

1. **`heap_force_freeze` on aborted-xact tuple makes it visible to ALL snapshots** including prior ones that already observed it as aborted — silently resurrects rolled-back rows. Documented only as "potentially-garbled data" — the snapshot violation is unnamed.
2. **Accepts system catalog OIDs** — superuser confusion → instant catalog corruption. Properly gated by `object_ownercheck` (unlike A14 sibling modules that have no C-side check) but no `IsCatalogRelation` reject.
3. **`heap_force_freeze` on HOT-chain root leaves successors dangling** — undocumented; can corrupt HOT chains silently.
4. `log_newpage_buffer` FPI per modified page — undocumented WAL amplification.

## Entries — `heap_surgery.c`

- [ISSUE-correctness: accepts system catalog OIDs; superuser confusion → instant catalog corruption (confirmed)] — `:111-127`
- [ISSUE-correctness: force-freeze on aborted-xact tuple makes it visible to ALL snapshots including prior ones (likely)] — `:289-308`
- [ISSUE-resource: `log_newpage_buffer` FPI per modified page; undocumented WAL amplification (nit)] — `:319-328`
- [ISSUE-correctness: force-freeze on HOT-chain root leaves successors dangling (maybe)] — `:289-308`

## Cross-sweep references

- A14 pg_visibility `pg_truncate_visibility_map` — same "no catalog filter on dangerous superuser tool" pattern.
- A12 amcheck `verify_heapam(check_toast=true)` documented "can crash backend" — pg_surgery silently corrupts, less honest.
