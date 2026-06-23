---
source_url: https://www.postgresql.org/docs/current/amcheck.html
fetched_at: 2026-06-23T00:00:00Z
anchor_sha: 9a60f295bcb1
distilled_by: pg-docs-miner (cloud routine)
docs_version: current (PG18)
primary: false
---

# Docs distilled — amcheck (index + heap corruption verification)

`amcheck` verifies that an index (B-tree, GIN) or heap is **structurally and
logically consistent** — the tool you reach for when a wrong-answer bug might be
a corrupt index rather than a planner/executor bug, or when validating that a
new operator class / opclass support function behaves. It runs the *same*
procedures an index scan would (including user opclass code), so it doubles as a
check that B-tree support-function 1 comparisons are deterministic and immutable.
`[from-docs]`

## The B-tree functions — locking is the whole decision

```
bt_index_check(index regclass, heapallindexed boolean, checkunique boolean) returns void
bt_index_parent_check(index regclass, heapallindexed boolean, rootdescend boolean, checkunique boolean) returns void
```

- `bt_index_check` takes only **`AccessShareLock`** on the index + its heap — so
  it runs concurrently with reads *and writes*, safe for production, and works
  on hot-standby replicas. It verifies items are in logical order within each
  page. `[from-docs]`
- `bt_index_parent_check` is the strict superset: it additionally checks
  **parent/child downlinks**, but takes a **`ShareLock`** (blocks `INSERT` /
  `UPDATE` / `DELETE` / `VACUUM` / utility commands) — **not for production**,
  and **cannot run on a hot standby** (unlike `bt_index_check`). `[from-docs]`
- `rootdescend = true` (parent_check only) re-finds each tuple via a fresh
  search from the root — catches transient inconsistencies a linear scan misses,
  at extra cost. `[from-docs]`
- `checkunique = true` verifies a unique index has no more than one *visible*
  duplicate. `[from-docs]`

## heapallindexed — the cross-check that catches the most

- `heapallindexed = true` (available on both functions) runs a "dummy"
  `CREATE INDEX CONCURRENTLY` in memory: it fingerprints every heap tuple and
  verifies the existing index would only contain entries findable in that
  fingerprint — i.e. **every heap tuple is indexed**. `[from-docs]`
- Cost: several times slower; bounded by **`maintenance_work_mem`**. The doc
  gives a concrete tuning fact: **~2 bytes per tuple** suffices for ≤2%
  probability of missing an inconsistency. It does **not** escalate the
  relation-level lock. `[from-docs]`
- This mode is what catches collation mismatches between primary and standby,
  storage-subsystem bit-flips (especially with checksums off), and single-bit
  memory errors. `[from-docs]`

## GIN and heap

- `gin_index_check(index regclass)` verifies GIN parent-child tuple
  consistency and the balanced-tree invariant (an internal page references
  *only* leaf or *only* internal pages, never mixed). `[from-docs]`
- `verify_heapam(relation regclass, on_error_stop bool, check_toast bool,
  skip text, startblock bigint, endblock bigint, ...) returns setof record`
  reports both **structural** corruption (invalidly formatted page data) and
  **logical** corruption (well-formed pages that are wrong relative to the
  cluster — missing TOAST entries, transaction IDs older than the cluster
  minimum). Output rows carry `blkno, offnum, attnum, msg`. `[from-docs]`

## What it cannot detect

- Pages that are correctly formatted, internally consistent, and pass their own
  checksums **may still hold logical corruption** that the B-tree checks won't
  see. `[from-docs]`
- It does **not** read from the filesystem if the block is already in shared
  buffers at check time — so it won't catch on-disk corruption that's masked by
  a clean cached copy. `[from-docs]`

## Operational notes

- While running, `amcheck` temporarily sets `search_path` to
  `pg_catalog, pg_temp` (so opclass code can't be hijacked via search_path).
  `[from-docs]`
- Permissions can be `GRANT`ed to non-superusers, but the docs caution: an
  attacker who can both run checks and induce corruption could infer structural
  properties of data. `[from-docs]`

## Links into corpus

- B-tree structure the checks validate: [docs-distilled/btree.md](./btree.md)
- Index page layout (what `bt_index_check` walks): [docs-distilled/pageinspect.md](./pageinspect.md)
- HOT / heap tuple validity (`verify_heapam`): [docs-distilled/storage-hot.md](./storage-hot.md), [docs-distilled/storage-toast.md](./storage-toast.md)
- Index AM callback contract (opclass code the checks invoke): [docs-distilled/indexam.md](./indexam.md), [docs-distilled/xindex.md](./xindex.md)
- Relevant skills: `access-method-apis` (opclass correctness), `debugging`,
  `locking` (the AccessShareLock-vs-ShareLock distinction is the production-safety
  boundary).
