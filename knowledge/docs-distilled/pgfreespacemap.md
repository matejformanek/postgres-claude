---
source_url: https://www.postgresql.org/docs/current/pgfreespacemap.html
fetched_at: 2026-06-23T00:00:00Z
anchor_sha: 9a60f295bcb1
distilled_by: pg-docs-miner (cloud routine)
docs_version: current (PG18)
primary: false
---

# Docs distilled — pg_freespacemap (FSM fork introspection)

`pg_freespacemap` shows what the free-space-map fork *records* for each page —
the value the inserter consults to pick a target page. The headline gotcha for a
backend hacker: **these numbers are deliberately approximate**, so they won't
match `pgstattuple`'s exact `free_space`. Default access is **superuser +
`pg_stat_scan_tables`**; `GRANT`able. `[from-docs]`

## Functions

- `pg_freespace(rel regclass, blkno bigint) returns int2` — FSM-recorded free
  bytes for one page. `[from-docs]`
- `pg_freespace(rel regclass) returns setof (blkno bigint, avail int2)` — same
  for every page. `[from-docs]`

## Why the value is approximate (the non-obvious part)

- The FSM stores free space **in categories, not exact bytes**: values are
  rounded to **1/256th of `BLCKSZ`** (32 bytes at the default 8KB block), and
  they are **not kept fully up to date** as tuples are inserted/updated. So
  `pg_freespace` is a *hint quality* number — exactly what the insertion path
  needs, not an accounting figure. `[from-docs]`
- This is why `pg_freespace` and `pgstattuple.free_space` legitimately differ:
  one is the quantized hint, the other a measured scan. `[inferred]`

## Indexes are different

- For **indexes**, the FSM tracks only **entirely-unused (empty) pages**, not
  in-page free space. So `pg_freespace` on an index is meaningful only as
  "in-use vs empty", not as a byte count. `[from-docs]`

## Links into corpus

- FSM fork internals (the binary-tree structure + categories): [docs-distilled/storage-fsm.md](./storage-fsm.md)
- Exact (scanned) free space for comparison: [docs-distilled/pgstattuple.md](./pgstattuple.md)
- FSM page byte-level decode: [docs-distilled/pageinspect.md](./pageinspect.md) (`fsm_page_contents`)
- Relevant skills: `debugging`, `access-method-apis`. The insertion path's
  target-page choice (`RelationGetBufferForTuple`) is the consumer of this map.
