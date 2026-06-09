# Issues — `contrib/pgrowlocks`

Per-tuple row-lock introspection. 1 source file / ~280 LOC.

**Parent docs:** `knowledge/files/contrib/pgrowlocks/pgrowlocks.c.md`.

**Source:** 5 entries surfaced 2026-06-09 by A14-1.

## Headlines

1. **Exposes per-tuple lock holder PIDs + modes** beyond `pg_locks` coverage — finer-grained side channel into transactional behavior.
2. **No `CHECK_FOR_INTERRUPTS` in per-tuple loop** — cancel-slow on big relations.
3. **Buffer share-lock held across `GetMultiXactIdMembers`** — introduces buffer→SLRU lock ordering (concurrency surface).

## Entries — `pgrowlocks.c`

- [ISSUE-defense-in-depth: exposes per-tuple lock holder PIDs and modes beyond `pg_locks` coverage (nit)] — `:127-263`
- [ISSUE-correctness: no `CHECK_FOR_INTERRUPTS` in per-tuple loop; cancel-slow on big relations (maybe)] — `:125-275`
- [ISSUE-nit: mixed `palloc`'d / string-literal pointers in `values[]` array (nit)] — `:164-166`
- [ISSUE-defense-in-depth: `pg_stat_scan_tables` membership grants pgrowlocks beyond `ACL_SELECT` (nit)] — `:108-115`
- [ISSUE-concurrency: buffer share-lock held across `GetMultiXactIdMembers`; introduces buffer→SLRU lock ordering (maybe)] — `:132-265`

## Cross-sweep references

- A11/A12/A14 monitoring-as-extraction cluster.
