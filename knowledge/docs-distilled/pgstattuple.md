---
source_url: https://www.postgresql.org/docs/current/pgstattuple.html
fetched_at: 2026-06-23T00:00:00Z
anchor_sha: 9a60f295bcb1
distilled_by: pg-docs-miner (cloud routine)
docs_version: current (PG18)
primary: false
---

# Docs distilled — pgstattuple (tuple-level bloat statistics)

`pgstattuple` measures *physical* tuple-level density — live vs dead vs free —
by actually scanning the relation, the ground-truth way to answer "is this table
bloated / does it need VACUUM?" independent of the cumulative-stats estimates.
Default access is the **`pg_stat_scan_tables`** role (or `GRANT EXECUTE`).
`[from-docs]`

## pgstattuple(regclass) — the full-scan truth

- Output: `table_len, tuple_count, tuple_len, tuple_percent, dead_tuple_count,
  dead_tuple_len, dead_tuple_percent, free_space, free_percent`. `[from-docs]`
- It acquires only an **`AccessShareLock`** (the least-restrictive lock) but
  does a **full scan** — so it's a real I/O cost on a big table, and the result
  is not an instantaneous snapshot (concurrent updates affect it). `[from-docs]`
- Non-obvious accounting identity: `table_len` is **always greater** than
  `tuple_len + dead_tuple_len + free_space`. The gap is fixed page-header
  overhead, the per-page line-pointer array, and alignment padding — i.e. the
  per-page structural cost the storage layer imposes. `[from-docs]`

## pgstattuple_approx(regclass) — VM/FSM shortcut

- Output mirrors `pgstattuple` but flags estimates: `table_len, scanned_percent,
  approx_tuple_count, approx_tuple_len, approx_tuple_percent, dead_tuple_count,
  dead_tuple_len, dead_tuple_percent, approx_free_space, approx_free_percent`.
  `[from-docs]`
- The trick: it **skips pages whose visibility-map bit is set** (all-visible →
  no dead tuples) and reads their free space from the **FSM**, assuming the rest
  of each skipped page is live tuples. Only non-skippable pages are scanned
  tuple-by-tuple; total live count is then estimated the same way VACUUM derives
  `pg_class.reltuples`. `[from-docs]`
- Crucial asymmetry: **dead-tuple stats are exact**, live-tuple stats are
  estimated. So it's reliable for "how much dead space is there" but
  approximate for "how many live rows". `[from-docs]`

## Index variants

- `pgstatindex(regclass)` (B-tree): `version, tree_level, index_size,
  root_block_no, internal_pages, leaf_pages, empty_pages, deleted_pages,
  avg_leaf_density, leaf_fragmentation`. The bloat indicators are
  `deleted_pages` + `leaf_fragmentation` (and falling `avg_leaf_density`).
  `[from-docs]`
- `pgstatginindex(regclass)`: `version, pending_pages, pending_tuples` — the
  pending list (GIN's fast-insert buffer) is the bloat signal; a large pending
  list means `gin_clean_pending_list`/autovacuum is behind. `[from-docs]`
- `pgstathashindex(regclass)`: `version, bucket_pages, overflow_pages,
  bitmap_pages, unused_pages, live_items, dead_tuples, free_percent` — high
  `overflow_pages` relative to `bucket_pages` signals hash bloat. `[from-docs]`

## Links into corpus

- Heap page layout (where the page-overhead gap comes from): [docs-distilled/storage-page-layout.md](./storage-page-layout.md)
- Visibility map (what `pgstattuple_approx` skips on): [docs-distilled/storage-vm.md](./storage-vm.md)
- FSM (free-space source for skipped pages): [docs-distilled/storage-fsm.md](./storage-fsm.md)
- Per-page byte-level confirmation: [docs-distilled/pageinspect.md](./pageinspect.md)
- B-tree / GIN / hash structure behind the index variants: [docs-distilled/btree.md](./btree.md), [docs-distilled/gin.md](./gin.md), [docs-distilled/hash-index.md](./hash-index.md)
- Relevant skills: `debugging`, `access-method-apis`. VACUUM's reltuples
  estimation is the shared mechanism behind `approx_tuple_count`.
