# `storage/lmgr/README-SSI` — summary

- **Source path:** `source/src/backend/storage/lmgr/README-SSI` (646 lines)
- **Last verified commit:** `ef6a95c7c64de07dff4dd1f1da88ffae7b086ef3` (2026-06-01)
- **Implementation:** `predicate.c` (see `knowledge/files/src/backend/storage/lmgr/predicate.c.md`)

Documents PostgreSQL's Serializable Snapshot Isolation (SSI) implementation. About 90 % of the linked code is generic predicate locking; SSI itself is the layer that watches for the dangerous structure.

## Section map

| README lines | Topic |
|---|---|
| 13-31 | Credits and Cahill papers |
| 34-72 | Why SSI: tradeoffs vs. snapshot isolation and S2PL `[from-README]` |
| 75-104 | SSI vs. S2PL — the rationale for non-blocking reads `[from-README]` |
| 107-148 | Apparent serial order, rw/wr/ww dependencies, anomaly cycles `[from-README]` |
| 151-197 | **SSI algorithm**: the `Tin → Tpivot → Tout` dangerous structure + the two PG-specific optimisations `[from-README]` |
| 200-251 | What it does *not* cover (system tables, temp tables, hint bits, sequences) and SQLSTATE 40001 `[from-README]` |
| 253-298 | Predicate locking — why intent locks don't work, why locks are non-blocking, granularity promotion `[from-README]` |
| 301-323 | Heap locking — table scan vs tuple read; what conflicts with what `[from-README]` |
| 325-403 | **Index AM implementations** — B-tree leaf, GIN entry-tree + fastupdate, GiST per-level, hash bucket-page `[from-README]` |
| 405-589 | **Innovations** — six concrete differences from the papers + the proof that SIREAD on the original tuple version need not be propagated to new versions (lines 480-519) `[from-README]` |
| 591-625 | R&D open issues (WAL replay, external replication) `[from-README]` |
| 627-646 | References |

## Key facts to anchor on

1. **Tin/Tpivot/Tout dangerous structure** (`README-SSI:160-174`): SSI tracks only rw-conflict edges between *concurrent* transactions; aborts a transaction only when both legs of the pivot exist *and* the two optimisations (`Tout` committed before the others, or `Tin` is read-only with Tout committed before Tin's snapshot) say abort is required `[from-README]`.
2. **Predicate-lock granularity** (`README-SSI:281-298`): three levels — tuple, page, relation. Coarser-granularity acquisition releases finer ones; acquiring finer when coarser is held is a no-op.
3. **Heap locking** (`README-SSI:301-323`): tuple read locks individual tuples; table scan locks the whole relation. **Page-level locks do not lock gaps on the page** — they're just aggregation. Inserts conflict with relation-level SIREAD but not page-level.
4. **Index AM rules** (`README-SSI:367-402`): B-tree leaf, GIN entry-tree leaf (with posting-tree-root for equality scans, *and* fastupdate forces "insert conflicts with all scans"), GiST every level, hash primary bucket pages (both old and new during split).
5. **SLRU summarisation** (`README-SSI:583-588`): finished-transaction commit-sequence numbers spill to `pg_serial` SLRU when in-memory state fills.
6. **Subtransaction handling** (`README-SSI:461-467`): "all xid usage in SSI, including predicate locking, is based on the top level xid"; subtransaction reads survive a subtxn rollback for SSI purposes.

## Hard-to-find canonical statement

The README-SSI is itself the authoritative source for the **lock-acquisition order specific to predicate locks**:

> `predicate.c:84-141` reproduces this same order with much more operational detail. When citing predicate-lock LWLock ordering, prefer `predicate.c:84-141` over README-SSI — the C-file comment is what `CreatePredicateLock` and friends actually obey.

## files-examined rows

| path | depth | date | commit | doc |
|---|---|---|---|---|
| source/src/backend/storage/lmgr/README-SSI | full-read | 2026-06-01 | ef6a95c | knowledge/files/src/backend/storage/lmgr/README-SSI.md |

## Synthesized by
<!-- backlinks:auto -->
- [subsystems/optimizer.md](../../../../../subsystems/optimizer.md)
- [subsystems/storage-lmgr.md](../../../../../subsystems/storage-lmgr.md)
