# Access methods — pluggable indexes and pluggable table storage

PostgreSQL ships with two distinct plug points for storage code: **index access
methods** (the older one, formalized as a callback struct in 9.6) and **table
access methods** (added in v12). They are completely independent APIs but share
the same dispatch pattern: a `pg_am` catalog row names a handler function, the
handler returns a pointer to a statically allocated routine struct, and the
core code dispatches through function pointers on that struct.

This doc is the long-form companion to the operational `access-method-apis`
skill. Read that for the per-callback checklist.

## Layered model

```
   SQL          CREATE INDEX i ON t USING btree (col)
                CREATE TABLE  t USING heap (col int)
                                │
                  parser, planner, executor
                                │
       ┌────────────────────────┼────────────────────────┐
       │                                                 │
   genam.c / indexam.c                              tableam.h inline
   (executor-facing wrappers,                        wrappers (table_*)
    snapshot setup, locking,                              │
    bookkeeping)                                          │
       │                                                 │
   IndexAmRoutine *                                  TableAmRoutine *
   (per pg_am row)                                   (per pg_am row)
       │                                                 │
   nbtree / brin / gin / gist / hash / spgist     heap (heapam_handler.c)
       │                                                 │
                       buffer manager, smgr, WAL, MVCC snapshots
```

The wrapper layer is the contract surface. `index_beginscan`,
`index_getnext_slot`, `index_endscan` in `indexam.c` and the `table_*` inline
functions in `tableam.h` are what executor code calls; they in turn dereference
the routine struct. **A new AM never has callers outside this layer** — the
planner and executor are AM-agnostic.

This separation is why we say "heap is just one table AM": the heap-specific
code in `src/backend/access/heap/` is exactly the same kind of guest as a
hypothetical `zheap` or `columnar` would be. The wrapper layer doesn't know.

## Index AM contract — what it must guarantee

Beyond the function-pointer surface, an index AM commits to:

- **Idempotent inserts under crash recovery** — every operation must be
  durable through WAL, and replay must produce a state consistent with the
  pre-crash heap. In-tree AMs do this with a custom resource manager (see
  `wal-and-xlog`).
- **Two-pass vacuum**: `ambulkdelete` removes index entries whose heap TIDs the
  vacuum callback flags as dead. It can be called multiple times (heap is
  vacuumed in batches). `amvacuumcleanup` runs once at the end.
- **Concurrency**: scans and modifications happen in parallel. Each AM picks
  its own page-level locking discipline. Btree uses Lehman & Yao
  right-link-and-restart; GiST uses the same idea plus NSN versions.
- **Strategy/support function model**: operators applicable to the index are
  catalogued in `pg_amop` (strategy numbers) and `pg_amproc` (support function
  numbers). The AM body looks up support functions through `index_getprocinfo`
  (which caches `FmgrInfo`). Strategy numbers are AM-private; standard "less
  than / equal / greater than" semantics for btree-compatible AMs are bridged
  through `amtranslatecmptype` to the AM-neutral `CompareType` enum.

The static flag fields on `IndexAmRoutine` aren't decoration — the planner
reads `amcanorder`, `amcanunique`, `amcanmulticol`, `amoptionalkey`,
`amsearcharray`, `amsearchnulls`, `amcanparallel`, `amcaninclude` before it
ever considers using the index. Get them wrong and you'll get
"can't happen" assertion failures or silent wrong results.

## Why pluggable index AMs existed before pluggable tables

PostgreSQL has been "pluggable" for indexes since the late-90s
`pg_am`/`pg_amop`/`pg_amproc` catalogs, even when the interface was a hardcoded
set of C functions rather than a vtable. Adding GiST (1999) and GIN (2006)
without forking the executor proved the model. Formalizing it as
`IndexAmRoutine` in 9.6 (commit `65c5fcd35`) was a refactor, not a
functional change — it stopped the executor reaching for AM-specific
hardcoded functions, made out-of-tree AMs realistic, and gave us BRIN (also
9.6) and bloom (`contrib/bloom`).

## Why pluggable table AMs were added (v12, 2019)

For 20+ years "heap" was hard-wired. The push to formalize a table-AM API came
from several directions at once:

- **Undo-log MVCC (zheap)**: EnterpriseDB's prototype to store old row versions
  in a separate undo log instead of MVCC chains in the heap. Needs different
  visibility, different vacuum, different on-disk layout — but the same
  executor, planner, indexes, WAL, and clients should keep working.
- **Columnar storage**: column-oriented analytics formats (Citus's `cstore_fdw`,
  later `columnar`, and others) wanted to live as native tables, not foreign
  tables, so the planner and inheritance/partitioning would treat them as
  first-class.
- **Transparent Data Encryption (TDE)**: per-table or per-tablespace
  encryption was hard to retrofit into heap; cleaner as a separate AM.
- **Append-only / log-structured / index-organized**: row formats where TIDs
  aren't (block, offset) but synthetic.

Andres Freund did most of the v12 work (commits `e0c4ec07284`, `eb004
3848cb` and a long series), and the API has been gently extended every release
since (notably for parallel sequential scans of non-heap AMs, sampling
support, and the read-stream interface that arrived in v17).

## What "heap is just one table AM" still doesn't mean

The API is real but not perfect. Several things still leak heap assumptions:

- **`ItemPointer` (TID)** — 6 bytes, (block, offset), used everywhere indexes
  reference rows, used in syscaches, exposed to SQL as `tid` and `ctid`. A
  non-heap AM must fabricate TIDs. This is the single biggest porting issue.
  An AM that wants more than 2^48 logical rows per table or doesn't have a
  natural offset-in-block concept has to use TID indirection internally.
- **Visibility map and FSM** — only the heap maintains these. Index-only scans
  consult the visibility map directly (`VM_ALL_VISIBLE`) and would just see
  "no" forever for a non-heap AM unless that AM also writes a VM fork.
- **HOT (heap-only tuples)** — a heap-specific optimisation; no API surface.
  Non-heap AMs return their own equivalent through the `TU_UpdateIndexes`
  return value of `tuple_update` (`TU_None` / `TU_Summarizing` / `TU_All`).
- **VACUUM scheduling** — `relation_vacuum` is the callback, but autovacuum's
  decisions are still driven by `pg_stat_all_tables` counters that heap
  produces. A non-heap AM has to fake these or live with autovacuum never
  visiting it.
- **TOAST** — `relation_needs_toast_table` lets an AM opt out, but if you opt
  in you get heap-style out-of-line storage with all of heap's machinery.
- **`relation_size(MAIN_FORKNUM)`** — BRIN and ANALYZE use this to find the
  block-range of "interesting" pages, which presumes block-oriented storage.

The comment in `tableam.sgml` about these being "subject to change as the API
matures" has stood since v12; expect more deheapification in future releases.

## Opclass and strategy mapping in depth

For an index AM, a search like `WHERE col > 10` works because:

1. Planner inspects the index's opclass(es) on the indexed column.
2. The opclass has `pg_amop` entries linking specific operators (`>` for the
   column's type) to a **strategy number** (in btree, 5 = `BTGreaterStrategyNumber`).
3. Executor passes `ScanKey { sk_strategy = 5, sk_argument = Int4GetDatum(10) }`
   to `amrescan`.
4. AM body interprets the strategy number — btree's `_bt_first` decides which
   tree edge to descend; gist's `gistgettuple` calls the `consistent` support
   function.

Strategy numbers are AM-local. The `amtranslatestrategy` /
`amtranslatecmptype` callbacks let the planner reason about a heterogeneous
opclass family in terms of generic `COMPARE_LT`/`COMPARE_EQ`/`COMPARE_GT`
semantics. This is how merge-joins can use non-btree AMs as the driver, and
how partition pruning can reuse partition-key opclasses across AMs.

Support functions (`pg_amproc`) are pure C functions the AM calls to do
type-specific work it can't hardcode: btree's `cmp` (proc 1), gist's
`consistent`/`union`/`compress`/`decompress`/`penalty`/`picksplit`/`equal`
(procs 1..7), gin's `compare`/`extractValue`/`extractQuery`/`consistent`,
hash's `hash` and `hashextended`.

## Pointers

- `knowledge/architecture/wal.md` — AMs that store data must integrate with
  WAL via a custom rmgr (or Generic WAL for low-frequency changes).
- `knowledge/architecture/mvcc.md` — table AMs choose their own MVCC scheme
  but must implement `tuple_satisfies_snapshot` over snapshots core gives them.
- `.claude/skills/catalog-conventions/SKILL.md` — adding an in-tree AM means
  editing `pg_am.dat`, `pg_opclass.dat`, `pg_amop.dat`, `pg_amproc.dat`.
- `.claude/skills/wal-and-xlog/SKILL.md` — for the rmgr side.
- `doc/src/sgml/indexam.sgml`, `doc/src/sgml/tableam.sgml` — the user-facing
  reference chapters; deeper than this doc on locking and semantic
  requirements.
