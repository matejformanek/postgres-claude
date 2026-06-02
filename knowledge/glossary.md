# PostgreSQL internals glossary

Distilled terms for the pg-claude corpus. Grown mechanically by the
`pg-corpus-maintainer` cloud routine (recipe:
`.claude/cloud/pg-corpus-maintainer.md`, Pass 2).

**Provenance.** Each entry is distilled from an existing per-file or long-form
corpus doc (named after "— via"), which carries the underlying `file:line`
verification against `source/` at the corpus's last-verified commit
(`ef6a95c7c64`, 2026-06-01). `file:line` refs are into `source/...` and stay
stable across upstream pulls. Confidence tags follow CLAUDE.md.

Entries are alphabetical (case-insensitive). One `### <term>` heading per term
so future runs can detect what's already defined and append idempotently.

<!-- glossary:auto -->

### AM (access method)
The pluggable interface that lets PostgreSQL support multiple index and table
storage engines behind a uniform API. An index AM advertises its callbacks
through an `IndexAmRoutine` struct returned by its `*handler` function (e.g.
`bthandler`); core code calls `amvalidate` to check an opclass and dispatches
scans/inserts through the struct rather than hard-coding btree behavior.
[from-comment] (`amapi.c:1` — via
`knowledge/files/src/backend/access/index/amapi.c.md`).

### backend
A per-connection PostgreSQL server process. The postmaster forks one backend
per accepted connection; that backend runs `PostgresMain`, the "traffic cop"
read-parse-plan-execute loop, for the life of the session. Because each
session is a fresh fork, backend PIDs are not stable across connects.
[verified-by-code] (`postgres.c:4274` — via
`knowledge/files/src/backend/tcop/postgres.c.md`).

### buffer (shared buffer)
A `BLCKSZ`-sized page slot in the shared buffer pool, the cache between
backends and the storage manager. Each buffer has a fixed-size `BufferDesc`
header carrying its page identity (`tag`) and an atomic 64-bit `state` packing
refcount, usagecount, flags, and content-lock bits; pool and headers are
allocated in shared memory at startup. [verified-by-code]
(`buf_internals.h:326-359`, `buf_init.c:24-145` — via
`knowledge/subsystems/storage-buffer.md`).

### catalog (system catalog)
The set of on-disk tables (`pg_class`, `pg_proc`, `pg_type`, …) that hold all
database metadata — every relation, type, function, and operator is a row in a
catalog. The initial contents are bootstrapped from `.dat`/`.h` files via the
BKI mechanism; editing catalogs has strict OID and `catversion` rules.
[from-README] (via `knowledge/idioms/catalog-conventions.md`).

### ereport
The macro family for reporting errors and log messages, taking an elevel
(DEBUG…NOTICE…ERROR…PANIC), a SQLSTATE, and `errmsg`/`errdetail`/`errhint`
fields. `ERROR` and above do a `longjmp` to the nearest handler. Every C file
that reports errors includes `elog.h`. [verified-by-code] (via
`knowledge/files/src/include/utils/elog.h.md`).

### executor
The engine that runs a finished plan tree. Each query passes through the
`ExecutorStart` / `ExecutorRun` / `ExecutorFinish` / `ExecutorEnd` lifecycle;
`ExecutorRun` (hookable, dispatching to `standard_ExecutorRun`) pulls tuples
through the plan node tree one node at a time. [verified-by-code]
(`execMain.c:308,318` — via
`knowledge/files/src/backend/executor/execMain.c.md`).

### GUC (Grand Unified Configuration)
PostgreSQL's runtime configuration-variable system. Every setting (`work_mem`,
`wal_level`, …) is a `config_generic` record with a bool/int/real/string/enum
subclass; all built-in GUCs are registered into one table by
`build_guc_variables` at startup, and extensions add their own via
`DefineCustom*Variable`. [verified-by-code] (`guc.c:871` — via
`knowledge/files/src/backend/utils/misc/guc.c.md`).

### heap
PostgreSQL's default table access method: tuples are stored as
`HeapTupleHeader`-prefixed rows inside `BLCKSZ` pages, with old/new row
versions coexisting for MVCC. HOT (heap-only-tuple) chains and the
tuple-locking protocol — the trickier invariants — are documented in the heap
READMEs. [from-README] (`README.HOT`, `README.tuplock` — via
`knowledge/files/src/backend/access/heap/README.md`).

### HeapTuple
The lightweight in-memory wrapper for a heap row:
`struct HeapTupleData { uint32 t_len; ItemPointerData t_self; Oid t_tableOid;
HeapTupleHeader t_data; }` — a length, the row's self-TID, its table OID, and a
pointer to the on-page header. The bit-level layout lives in `htup_details.h`.
[verified-by-code] (`htup.h:62-69` — via
`knowledge/files/src/include/access/htup.h.md`).

### HOT (heap-only tuple)
An UPDATE optimization: when no indexed column changes and the new row version
fits on the same page, PostgreSQL chains the new tuple to the old via `t_ctid`
without inserting new index entries. The update is logged as
`XLOG_HEAP_HOT_UPDATE`, and index scans reach the live version by following the
HOT chain from the indexed root tuple. [verified-by-code] (`heapam.c:62` — via
`knowledge/files/src/backend/access/heap/heapam.c.md`).

### LSN (log sequence number)
A byte position in the continuous WAL stream, represented by the 64-bit
`XLogRecPtr` type. Every WAL record and every modified page records an LSN;
comparing LSNs orders changes in time, and `InvalidXLogRecPtr` (0) marks "no
position". [verified-by-code] (`xlogdefs.h:28` — via
`knowledge/files/src/include/access/xlogdefs.h.md`).

### LWLock (lightweight lock)
The in-memory lock used to guard shared-memory data structures, offering
exclusive and shared modes but no deadlock detection. LWLocks are cheap
relative to the heavyweight lock manager and are automatically released on
`elog(ERROR)` via `LWLockReleaseAll`. [from-comment] (`lwlock.c:6` — via
`knowledge/files/src/backend/storage/lmgr/lwlock.c.md`).

### MVCC (multiversion concurrency control)
PostgreSQL's concurrency model: each row version (tuple) carries `xmin`/`xmax`
transaction stamps, and a snapshot decides which versions a query may see, so
readers never block writers. The visibility logic lives in routines like
`HeapTupleSatisfiesMVCC`, which test a tuple's xmin/xmax against the snapshot.
[verified-by-code] (`heapam_visibility.c:938` — via
`knowledge/files/src/backend/access/heap/heapam_visibility.c.md`).

### palloc
Context-aware memory allocation. Memory returned by `palloc` belongs to the
`CurrentMemoryContext` rather than to the caller; it can be freed individually
with `pfree` but is more usually reclaimed in bulk when its context is reset or
deleted. OOM is reported via `ereport`, never a NULL return. [from-comment]
(`palloc.h:1-9,31-52` — via
`knowledge/files/src/include/utils/palloc.h.md`).

### PGPROC
The per-process shared-memory slot describing a backend to the rest of the
system. Every backend is assigned exactly one `PGPROC` from
`ProcGlobal->allProcs` at startup and returns it to a freelist at exit; it
holds the proc's wait state, LSNs, and lock links, and is how other backends
find and signal it. [verified-by-code] (`proc.h:184` — via
`knowledge/files/src/include/storage/proc.h.md`).

### planner
The optimizer stage that turns a `Query` into an executable `Plan` tree.
`planner()` / `standard_planner()` drive `subquery_planner` on the top query,
enumerate and cost candidate Paths, pick the cheapest, and hand it to
`create_plan` to materialize the final plan. [verified-by-code] (via
`knowledge/files/src/backend/optimizer/plan/planner.c.md`).

### portal
The backend-local object holding the execution state of a single query or
cursor — its plan, parameters, and memory contexts — between bind and the
fetching of results. Portals are created under `TopPortalContext` (e.g. by
`CreateNewPortal`) and torn down when the statement completes or the cursor
closes. [verified-by-code] (`portalmem.c:237` — via
`knowledge/files/src/backend/utils/mmgr/portalmem.c.md`).

### PostgresMain
The entry point of a per-connection backend: after authentication it runs the
"traffic cop" loop that reads a client message and dispatches simple-query
(`Q`) or extended-protocol (`P`/`B`/`E`) requests through parse → rewrite →
plan → execute. It runs for the life of the session in the forked backend.
[verified-by-code] (`postgres.c:4274` — via
`knowledge/files/src/backend/tcop/postgres.c.md`).

### postmaster
The supervisor process. It owns the shared-memory and semaphore pools, listens
for connections, and forks a fresh backend on each accept; it deliberately
stays *out* of shared memory so a crashing backend can never corrupt the
supervisor — a load-bearing invariant of the whole process model.
[from-comment] (`postmaster.c:14-23` — via
`knowledge/files/src/backend/postmaster/postmaster.c.md`).

### RangeTblEntry (RTE)
A range-table entry: the parse/plan-tree node describing one relation reference
in a query's FROM clause — a table, subquery, join, function, or CTE. Its
`rtekind` discriminates the variant, and other query nodes refer to RTEs by a
1-based range-table index (`varno`) rather than by pointer. [verified-by-code]
(`parsenodes.h:1137` — via
`knowledge/files/src/include/nodes/parsenodes.h.md`).

### relation
The internal name for any table-like object (table, index, sequence,
materialized view, composite type) — anything with a `pg_class` row and a
relfilenode. The in-memory `RelationData`/`Relation` handle caches a relation's
catalog metadata, tuple descriptor, and access-method routines. [from-README]
(via `knowledge/idioms/catalog-conventions.md`).

### rmgr (resource manager)
A WAL resource manager: each subsystem that emits WAL (heap, btree, transaction
commit, …) registers a record-type id and callbacks (notably `rm_redo`) in the
global `RmgrTable[RM_MAX_ID + 1]`. Recovery dispatches each WAL record to its
rmgr's redo function to replay the change. [verified-by-code] (`rmgr.c`
`RmgrTable` — via `knowledge/files/src/backend/access/transam/rmgr.c.md`).

### SLRU (simple LRU)
A small fixed-page cache for dense, sequentially-numbered on-disk state that the
main buffer pool does not manage — commit status (clog), subtransaction
parents, multixact, and similar. Clients drive it through the
`SlruCtl`/`SlruShared` interface declared in `slru.h` and implemented in
`slru.c`. [from-comment] (`slru.h:12` — via
`knowledge/files/src/include/access/slru.h.md`).

### smgr (storage manager)
The abstraction layer between the buffer manager and physical relation files.
`smgr.c` maintains a hashtable of `SMgrRelation` handles (cached open files) and
forwards reads, writes, extends, and truncates to the underlying `md.c`
magnetic-disk implementation. [from-comment] (`smgr.c:1` — via
`knowledge/files/src/backend/storage/smgr/smgr.c.md`).

### snapshot
A `SnapshotData` value that captures which tuple versions a query may see. Its
`SnapshotType` selects the visibility regime — the seven types are `MVCC`,
`SELF`, `ANY`, `TOAST`, `DIRTY`, `HISTORIC_MVCC`, and `NON_VACUUMABLE` — and a
single struct is reused across table AMs instead of a per-AM callback.
[from-comment] (`snapshot.h:19-30` — via
`knowledge/files/src/include/utils/snapshot.h.md`).

### TID (ItemPointer)
A tuple identifier: the physical address of a tuple on disk, encoded as an
`ItemPointerData` of block number plus a 1-based line-pointer offset within that
page. A heap tuple's own location is its `t_self` TID, and indexes store TIDs as
the pointers from index keys to heap rows. [verified-by-code] (`htup.h:62` — via
`knowledge/files/src/include/access/htup.h.md`).

### TOAST (The Oversized-Attribute Storage Technique)
PostgreSQL's mechanism for values too large to fit inline in a heap tuple:
oversized attributes are compressed and/or moved out-of-line into an associated
TOAST table, leaving a small pointer in the row. Reads transparently
reconstruct the value via the detoasting path. [verified-by-code]
(`detoast.c:205` — via
`knowledge/files/src/backend/access/common/detoast.c.md`).

### TransactionId (xid)
A 32-bit transaction identifier stamped into each tuple's xmin/xmax. Special
values include `InvalidTransactionId` (0); the 32-bit space wraps around, so
PostgreSQL also carries a 64-bit `FullTransactionId` to reason about age
without ambiguity. [verified-by-code] (`transam.h:3-4` — via
`knowledge/files/src/include/access/transam.h.md`).

### TupleTableSlot
The executor's universal tuple container, abstracting over how a tuple is
physically stored behind a `TupleTableSlotOps` vtable. Four built-in slot kinds
exist — Virtual, HeapTuple, MinimalTuple, and BufferHeapTuple — plus
extension-defined ones, letting every plan node pass tuples uniformly.
[verified-by-code] (via
`knowledge/files/src/include/executor/tuptable.h.md`).

### WAL (xlog)
The write-ahead log: every change is recorded as an XLOG record and flushed to
durable storage *before* the modified data pages are written back, which is
what makes crash recovery possible. `XLogInsertRecord` appends records on the
fast path; `StartupXLOG` replays them during recovery. [from-comment]
(`xlog.c:6-28` — via
`knowledge/files/src/backend/access/transam/xlog.c.md`).
