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

### AcceptInvalidationMessages
The routine that drains and applies pending shared-invalidation (sinval)
messages, flushing stale relcache/catcache entries; it runs at every lock
acquisition so a backend always sees catalog changes committed before it took
the lock. [from-comment] (`inval.c:30` — via
`knowledge/files/src/backend/utils/cache/inval.c.md`).

### AccessExclusiveLock
The strongest table-level lock mode; it conflicts with every other mode,
including itself, so only one holder exists at a time and no concurrent reader
or writer proceeds. DDL such as `DROP TABLE`, `TRUNCATE`, and most `ALTER TABLE`
forms take it, and `heap_create_with_catalog` grabs it on a new relid the
instant the OID is assigned — before any catalog row is inserted — so other
backends never observe a half-built relation. [verified-by-code]
(`heap.c:1293` — via `knowledge/files/src/backend/catalog/heap.c.md`).

### AccessShareLock
The weakest table-level lock mode, acquired by a plain `SELECT` for the
duration it reads a relation. It conflicts only with `AccessExclusiveLock`, so
ordinary reads and writes coexist freely; the conflict table lives in the lock
manager's method table. [verified-by-code]
(via `knowledge/files/src/backend/storage/lmgr/lock.c.md`).

### AcquireRewriteLocks
The rewriter routine that re-takes the same locks the parser took on every
relation in a query's range table, before rules are applied — needed because a
cached/stored query tree is re-used across invocations and the locks must be
freshly held each time. [from-comment] (`rewriteHandler.c:148` — via
`knowledge/files/src/backend/parser/parse_relation.c.md`).

### ActiveSnapshot
The top of the backend's active-snapshot stack — the snapshot that "the current
command" sees, managed by `PushActiveSnapshot` / `PopActiveSnapshot` /
`GetActiveSnapshot`. The snapshot manager tracks this stack (plus the
registered-snapshot heap) and uses the oldest of them to advance or hold back
`MyProc->xmin`. [from-comment] (`snapmgr.c:1-104` — via
`knowledge/files/src/backend/utils/time/snapmgr.c.md`).

### AllocSet
The default `MemoryContext` implementation (`AllocSetContext`). It amortizes
many small `palloc`s by carving them out of a few larger `malloc`'d blocks,
keeps a per-size free list for reuse, and frees every block at once on
`AllocSetReset`/`MemoryContextDelete`. It is the right choice unless a
specialized type (Slab, Generation, Bump) fits the allocation pattern better.
[from-comment] (`aset.c:16-43` — via
`knowledge/files/src/backend/utils/mmgr/aset.c.md`).

### ALWAYS_SECURE_SEARCH_PATH_SQL
The canonical SQL string `SELECT pg_catalog.set_config('search_path', '',
false)` that frontend tools (and `SECURITY DEFINER` code) run right after
connecting to empty the `search_path`, so later unqualified names cannot be
hijacked by attacker-controlled schemas. Defined in `common/connect.h`.
[verified-by-code] (via
`knowledge/files/src/fe_utils/connect_utils.c.md`).

### AM (access method)
The pluggable interface that lets PostgreSQL support multiple index and table
storage engines behind a uniform API. An index AM advertises its callbacks
through an `IndexAmRoutine` struct returned by its `*handler` function (e.g.
`bthandler`); core code calls `amvalidate` to check an opclass and dispatches
scans/inserts through the struct rather than hard-coding btree behavior.
[from-comment] (`amapi.c:1` — via
`knowledge/files/src/backend/access/index/amapi.c.md`).

### ArchiveHandle
The central pg_dump/pg_restore state object representing an open archive plus
its connection and format-specific method pointers (custom, directory, tar,
plain). Restore-time helpers like `ReconnectToServer(AH, dbname)` thread it
through every step. [verified-by-code] (via
`knowledge/files/src/bin/pg_dump/pg_backup_db.c.md`).

### autovacuum
The background facility that automatically issues `VACUUM` and `ANALYZE` on
tables whose dead-tuple or modification counters cross per-table thresholds. An
`autovacuum launcher` schedules work per database and forks short-lived
`autovacuum worker` backends to do it; it is also the safety net against
transaction-id wraparound. [from-comment] (via
`knowledge/files/src/backend/postmaster/autovacuum.c.md`).

### backend
A per-connection PostgreSQL server process. The postmaster forks one backend
per accepted connection; that backend runs `PostgresMain`, the "traffic cop"
read-parse-plan-execute loop, for the life of the session. Because each
session is a fresh fork, backend PIDs are not stable across connects.
[verified-by-code] (`postgres.c:4274` — via
`knowledge/files/src/backend/tcop/postgres.c.md`).

### BackgroundWorker
The registration struct an extension fills in (name, library/function entry
point, restart policy, flags for shmem/DB access) and hands to
`RegisterBackgroundWorker` (static, at load) or `RegisterDynamicBackgroundWorker`
(runtime) so the postmaster forks and manages a long-lived helper process.
[verified-by-code] (`bgworker.c:658` — via
`knowledge/files/src/backend/postmaster/bgworker.c.md`).

### BASE_BACKUP
The replication-protocol command (used by `pg_basebackup`) that asks a walsender
to stream a full copy of the data directory as a tar/plain archive, with options
for WAL inclusion, checkpoint mode, tablespace mapping, and progress reporting.
[verified-by-code] (via
`knowledge/files/src/backend/replication/repl_gram.y.md`).

### BeginInternalSubTransaction
Starts a subtransaction from C code (not from a SQL `SAVEPOINT`), giving a
PG_TRY/PG_CATCH frame that can be rolled back independently. plpgsql wraps a
block that has an `EXCEPTION` clause in one, taking care to create the
statement memory context *before* the subxact so caught error data outlives the
rollback. [verified-by-code] (`pl_exec.c:1818` — via
`knowledge/files/src/pl/plpgsql/src/pl_exec.md`).

### bgwriter (background writer)
The auxiliary process that trickles dirty shared buffers out to the storage
manager ahead of checkpoints, smoothing write spikes so backends and the
checkpointer find clean victims more often. It runs `BackgroundWriterMain`,
sleeping on a latch between rounds, and never writes WAL itself. [from-comment]
(via `knowledge/files/src/backend/postmaster/bgwriter.c.md`).

### Bitmapset
A compact variable-length set of small non-negative integers (a `Bitmapset`),
used throughout the planner and parser for things like sets of relids,
attribute numbers, and required-outer relations. Operations
(`bms_add_member`, `bms_is_member`, `bms_union`, …) treat it as an immutable-ish
value and may reallocate. [from-comment] (via
`knowledge/files/src/backend/nodes/bitmapset.c.md`).

### BKI_DEFAULT
One of the catalog header macros (alongside `BKI_BOOTSTRAP`,
`BKI_SHARED_RELATION`, `BKI_ROWTYPE_OID`, `BKI_LOOKUP`) that annotate a
`CATALOG()` column. It supplies the default value used to fill a `.dat` row that
omits the field. The macros are empty to the C compiler (defined in `genbki.h`)
and meaningful only to `genbki.pl` at build time. [verified-by-code] (via
`knowledge/files/src/backend/catalog/_generators.md`).

### BKI_FORCE_NOT_NULL
A catalog-definition macro forcing a column to be NOT NULL in the generated BKI
even though its C type or position would otherwise let bootstrap treat it as
nullable (e.g. the first variable-length or array column). [verified-by-code]
(via `knowledge/files/src/include/catalog/pg_propgraph_element.h.md`).

### BKI_LOOKUP
A catalog-column annotation declaring that an `Oid` column's `.dat` values are
written as names and resolved to OIDs against another catalog (e.g.
`BKI_LOOKUP(pg_proc)`) during bootstrap. Missing it on a column that is
semantically an OID reference is a recurring corpus issue. [from-comment] (via
`knowledge/idioms/catalog-conventions.md`).

### BKI_ROWTYPE_OID
A `CATALOG()` annotation that pins the OID of the composite (row) type
implicitly created for a system catalog, so that type OID is stable and can be
referenced from other bootstrap data. Processed by `genbki.pl`; invisible to the
C compiler. [verified-by-code] (via
`knowledge/files/src/backend/catalog/_generators.md`).

### BKI_SHARED_RELATION
A `CATALOG()` annotation marking a system catalog as cluster-wide (shared
across all databases, stored in the `global/` tablespace) rather than
per-database — e.g. `pg_database`, `pg_authid`. `genbki.pl` recognises it at
build time; it is empty to the C compiler. [verified-by-code] (via
`knowledge/files/src/backend/catalog/_generators.md`).

### BlockNumber
A `uint32` identifying a page within a single relation fork; block 0 is the
first 8 KB page. `InvalidBlockNumber` (0xFFFFFFFF) is the sentinel "no block",
which caps a fork at just under 2^32 pages. Combined with an `OffsetNumber`
it forms an `ItemPointer`/TID. [verified-by-code] (`block.h:31` — via
`knowledge/files/src/bin/pg_rewind/datapagemap.h.md`).

### buffer (shared buffer)
A `BLCKSZ`-sized page slot in the shared buffer pool, the cache between
backends and the storage manager. Each buffer has a fixed-size `BufferDesc`
header carrying its page identity (`tag`) and an atomic 64-bit `state` packing
refcount, usagecount, flags, and content-lock bits; pool and headers are
allocated in shared memory at startup. [verified-by-code]
(`buf_internals.h:326-359`, `buf_init.c:24-145` — via
`knowledge/subsystems/storage-buffer.md`).

### BUFFER_LOCK_EXCLUSIVE
The mode argument to `LockBuffer` taking a buffer's content lock for writing
(vs `BUFFER_LOCK_SHARE` for reading, `BUFFER_LOCK_UNLOCK` to release). It is the
short-lived LWLock guarding a page's bytes, distinct from the buffer pin that
keeps the page resident. [verified-by-code] (`brin_pageops.c:115` — via
`knowledge/files/src/backend/access/brin/brin.c.md`).

### BufferDesc
The shared-memory descriptor for one buffer-pool slot: it holds the buffer
tag, a packed atomic `state` word (refcount + usagecount + flag bits), and the
content/IO lock machinery. `LockBufHdr` spins on the state word to get a
consistent view; the actual page bytes live in a separate buffer-blocks array.
[verified-by-code] (`bufmgr.c:7527` — via
`knowledge/files/src/include/storage/buf_internals.h.md`).

### BufFile
A buffered, segmented temporary-file abstraction that transparently spans the
1 GB per-segment limit and is tracked for cleanup at transaction or query end.
The executor uses `BufFile`s to spill data that exceeds `work_mem` — e.g. the
per-batch outer/inner files of a multi-batch hash join. [from-comment] (via
`knowledge/files/src/backend/executor/nodeHashjoin.c.md`).

### CachedPlan
The executable plan produced from a `CachedPlanSource`, either generic
(parameter-independent, reused) or custom (re-planned for specific parameter
values). Its refcount is tracked through a `ResourceOwner` and released after
locks at end of the owning scope. [verified-by-code] (`plancache.c:117` — via
`knowledge/files/src/backend/utils/cache/plancache.c.md`).

### CachedPlanSource
The plancache structure representing one parsed-but-reusable query source: it
caches the raw/analyzed parse tree and produces a `CachedPlan` (generic or
custom) that survives across executions. PL/pgSQL's "simple expression"
fast-path keys off a statement compiling to exactly one `CachedPlanSource`.
[from-comment] (`pl_exec.c:8233` — via
`knowledge/files/src/pl/plpgsql/src/pl_exec.md`).

### CacheMemoryContext
The long-lived `MemoryContext` (a child of `TopMemoryContext`) that holds
relcache, catcache, and plan-cache entries for the life of the backend.
Allocations placed here are deliberately never freed per-query, so leaking into
it is a true backend-lifetime leak. [from-comment] (`memutils.h:52-67` — via
`knowledge/files/src/include/utils/memutils.h.md`).

### catalog (system catalog)
The set of on-disk tables (`pg_class`, `pg_proc`, `pg_type`, …) that hold all
database metadata — every relation, type, function, and operator is a row in a
catalog. The initial contents are bootstrapped from `.dat`/`.h` files via the
BKI mechanism; editing catalogs has strict OID and `catversion` rules.
[from-README] (via `knowledge/idioms/catalog-conventions.md`).

### CATALOG_VARLEN
The C macro that brackets the variable-length and nullable trailing columns of
a system-catalog struct in its `pg_*.h` definition. The compiled C struct omits
everything inside `#ifdef CATALOG_VARLEN`, since those fields cannot be accessed
as fixed-offset members and must go through `heap_getattr`/deform.
[verified-by-code] (`pg_largeobject.h:38` — via
`knowledge/files/src/include/catalog/pg_largeobject.h.md`).

### CATALOG_VERSION_NO
The catalog version number in `catversion.h`; a mismatch between a server and
its data directory's value makes the server refuse to start. Any change to the
on-disk catalog layout — new catalog column, changed BKI data, or a changed
`pg_node_tree` out/read format serialized into a catalog — requires bumping it.
[from-comment] (`pg_propgraph_label_property.h:42` — via
`knowledge/files/src/include/catalog/pg_propgraph_label_property.h.md`).

### catcache (catalog cache)
The per-backend cache of individual system-catalog rows keyed by lookup key
(e.g. a `pg_proc` row by OID), backing the `SearchSysCache` API. Entries are
negative-cacheable and invalidated by shared-invalidation messages when another
backend changes the underlying catalog. [from-comment] (via
`knowledge/files/src/backend/utils/cache/catcache.c.md`).

### CHECK_FOR_INTERRUPTS
The macro every long-running loop must call so a backend can act on a pending
cancel, terminate, or recovery-conflict signal at a safe point rather than
mid-critical-section. It expands to a cheap flag test that, when set, longjmps
out via `ProcessInterrupts`. Omitting it from a tight loop makes that loop
un-cancellable. [verified-by-code] (`pl_exec.c:2026` — via
`knowledge/files/src/pl/plpgsql/src/pl_exec.md`).

### CheckDeadLock
The deadlock detector entry point, invoked from `ProcSleep` after the
deadlock-timeout fires. It walks the lock wait-for graph looking for a cycle and,
if found, either rearranges wait queues to resolve a soft edge or signals the
current process to abort. [verified-by-code] (`proc.c:1856` — via
`knowledge/files/src/backend/storage/lmgr/proc.c.md`).

### checkpoint
A point at which all dirty shared buffers are flushed and a WAL record is
written so crash recovery can start replaying from there rather than the start
of the log. `CreateCheckPoint` performs the work; the redo pointer it records
bounds how much WAL recovery must scan. [from-comment] (via
`knowledge/files/src/backend/access/transam/xlog.c.md`).

### checkpointer
The dedicated auxiliary process that performs checkpoints (and restartpoints on
standbys), spreading the buffer flush over time per
`checkpoint_completion_target`. Backends request checkpoints by signalling it
rather than running `CreateCheckPoint` themselves. [from-comment] (via
`knowledge/files/src/backend/postmaster/checkpointer.c.md`).

### ClientAuthentication
The backend routine that runs the configured authentication method (matched
from `pg_hba.conf` via the parsed `HbaLine` rules) against a newly connected
client, before the session is allowed to proceed. It is the chokepoint every
connection passes through during backend startup. [verified-by-code]
(via `knowledge/files/src/backend/tcop/backend_startup.c.md`).

### clog (CLOG / pg_xact)
The commit-log SLRU that stores two status bits per transaction (in-progress /
committed / aborted / sub-committed), consulted by visibility checks to resolve
whether a tuple's xmin/xmax committed. It lives under `pg_xact/` and is driven
through `TransactionIdSetTreeStatus` / `TransactionIdGetStatus`. [from-comment]
(via `knowledge/files/src/backend/access/transam/clog.c.md`).

### CommandCounterIncrement (CCI)
Bumps the command counter within the current transaction so that changes made
by earlier commands become visible to later commands in the same transaction,
while still being invisible to other transactions. Catalog-mutating code calls
it between steps (e.g. after inserting a pg_class row, before inserting
dependent rows) so the next lookup sees the new tuple. [verified-by-code]
(`xact.c:1130` — via
`knowledge/files/src/backend/access/transam/xact.c.md`).

### CommandId
A 32-bit counter (`cid`) distinguishing commands within a single transaction so
a statement does not see rows its own later commands produced (the
`cmin`/`cmax` of a tuple). It is reset each transaction; only commands that
write advance it. [verified-by-code] (via
`knowledge/files/src/backend/utils/adt/xid.c.md`).

### commit timestamp (commit_ts)
An optional SLRU (`pg_commit_ts/`) that records the wall-clock commit time and
origin of each transaction when `track_commit_timestamp` is on, queryable via
`pg_xact_commit_timestamp`. It is primarily used by conflict detection in
logical replication. [from-comment] (via
`knowledge/files/src/backend/access/transam/commit_ts.c.md`).

### CommitTransaction
The xact.c routine that performs a top-level transaction commit: it fires
pre-commit callbacks, processes pending relation-file deletes via
`smgrDoPendingDeletes`, writes and flushes the commit WAL record
(`RecordTransactionCommit`), releases locks, and advances the proc's state. The
abort counterpart is `AbortTransaction`. [verified-by-code]
(`storage.c:673-735` — via
`knowledge/files/src/backend/catalog/storage.c.md`).

### CurrentMemoryContext
The global that names the context where a bare `palloc` allocates. Code sets
it with the inline `MemoryContextSwitchTo(new)`, which returns the previous
context so callers can restore it; forgetting to restore is a classic source of
allocations landing in the wrong context. [verified-by-code] (via
`knowledge/idioms/memory-contexts.md`).

### Datum
The generic pointer-width value type that carries any SQL datum through the
executor and fmgr layer: pass-by-value types are stored inline, pass-by-
reference types as pointers into memory. Conversion macros (`Int32GetDatum`,
`DatumGetPointer`, …) move concrete C values in and out. [inferred] (via
`knowledge/idioms/fmgr.md`).

### deadlock detector
The lock-manager component that, on `deadlock_timeout` expiring while a backend
waits for a heavyweight lock, builds the wait-for graph and looks for a cycle.
A hard cycle aborts the youngest waiter with a deadlock error; soft edges let
it re-order the wait queue instead. [from-comment] (via
`knowledge/files/src/backend/storage/lmgr/deadlock.c.md`).

### DECLARE_TOAST
A catalog-header macro that declares the TOAST table (and its index) for a
system catalog, fixing both their OIDs — e.g. `DECLARE_TOAST(pg_description,
2834, 2835)`. `genbki.pl` emits the corresponding bootstrap entries.
[verified-by-code] (via
`knowledge/files/src/include/catalog/pg_description.h.md`).

### DECLARE_UNIQUE_INDEX
The catalog-header macro declaring a unique index on a system catalog (its
name, fixed OID, and indexed columns), consumed by `genbki.pl` to emit the BKI
that bootstrap uses to build the index. `_PKEY` marks the primary key.
[verified-by-code] (`pg_auth_members.h:66` — via
`knowledge/files/src/include/catalog/pg_auth_members.h.md`).

### DECLARE_UNIQUE_INDEX_PKEY
The catalog-header macro that declares a system catalog's primary-key index
(name, OID, and the indexed columns) so `genbki.pl` can emit the bootstrap index
definition — e.g. `pg_description`'s `(objoid, classoid, objsubid)` PK. The
sibling `DECLARE_UNIQUE_INDEX` declares non-PK unique indexes. [verified-by-code]
(via `knowledge/files/src/include/catalog/pg_description.h.md`).

### DELAY_CHKPT_IN_COMMIT
A `delayChkpt` flag a backend sets on its `PGPROC` across the window where it
has written its commit WAL but not yet made the effects visible, forcing a
concurrent checkpoint to wait so it cannot capture a torn commit state. Logical
replication's conflict detection reads the oldest such xid via
`TwoPhaseGetOldestXidInCommit`. [verified-by-code] (`twophase.c:2835` — via
`knowledge/files/src/backend/access/transam/twophase.c.md`).

### DestReceiver
The abstract sink for query result tuples: a struct of `receiveSlot`/`rStartup`/
`rShutdown`/`rDestroy` callbacks chosen by command context (client wire
protocol, `SELECT INTO`/tuplestore, SPI, COPY, printtup). The executor calls
`receiveSlot` per output tuple without knowing the concrete destination.
[from-comment] (`pl_exec.c:3576` — via
`knowledge/files/src/pl/plpgsql/src/pl_exec.md`).

### DSM (dynamic shared memory)
The facility for creating shared-memory segments after postmaster startup, used
mainly to pass tuples and state to parallel workers. One backend creates a
`dsm_segment` and shares its handle; others `dsm_attach`/`dsm_detach`, and
detach callbacks run cleanup. [from-comment] (via
`knowledge/files/src/backend/storage/ipc/dsm.c.md`).

### DumpableObject
pg_dump's in-memory base "class" for every catalog object it might emit
(tables, types, functions, ACLs, …); the `getXxx()` collectors populate
subclasses, dependency edges are computed between them, and a topological sort
plus per-type `dumpXxx` routines turn them into ordered archive entries.
[verified-by-code] (via
`knowledge/files/src/bin/pg_dump/pg_dump.c.md`).

### ereport
The macro family for reporting errors and log messages, taking an elevel
(DEBUG…NOTICE…ERROR…PANIC), a SQLSTATE, and `errmsg`/`errdetail`/`errhint`
fields. `ERROR` and above do a `longjmp` to the nearest handler. Every C file
that reports errors includes `elog.h`. [verified-by-code] (via
`knowledge/files/src/include/utils/elog.h.md`).

### ErrorContext
A small `MemoryContext` reserved at backend startup so that error reporting can
allocate even when the failing operation has exhausted memory; it is reset
after each error is handled. Along with `TopMemoryContext` it is one of only two
contexts initialized directly by `MemoryContextInit`. [from-comment]
(`mcxt.c:362-398` — via
`knowledge/files/src/include/utils/memutils.h.md`).

### EState
The top-level executor run-state for one query execution: it holds the range
table, result relations, the per-query memory context, the snapshot, parameter
values, and the tuple destination, and is shared by every `PlanState` in the
tree. [verified-by-code] (via `knowledge/subsystems/executor.md`).

### EvalPlanQual
The mechanism that lets a `READ COMMITTED` UPDATE/DELETE/SELECT-FOR-UPDATE cope
with a row another transaction concurrently modified: instead of aborting, it
re-fetches the latest committed version and re-runs the qual and projection
against it (an "EPQ recheck"). The executor diverts to `EvalPlanQualNext` on a
`TM_Updated`/`TM_Deleted` result. [verified-by-code] (via
`knowledge/subsystems/executor.md`).

### EXEC_BACKEND
The build symbol selecting the "re-exec" backend-startup model (mandatory on
Windows, optional elsewhere for debugging) in which a new backend is started by
exec-ing a fresh postgres image and re-attaching shared memory, instead of
relying on `fork()` to inherit the postmaster's address space. [inferred] (via
`knowledge/architecture/process-model.md`).

### ExecEndNode
The teardown half of the executor node API: `ExecEndPlan` walks the `PlanState`
tree calling each node's `ExecEndNode` to close relations, free tuple slots, and
release per-node resources after execution finishes. [verified-by-code]
(`execMain.c:1565` — via `knowledge/subsystems/executor.md`).

### ExecInitNode
The recursive constructor of the executor's run-time tree: called from
`InitPlan`, it turns each `Plan` node into a `PlanState` (allocating slots,
expression states, and child states) and installs the node's per-tuple
`ExecProcNode` callback. [verified-by-code] (`execMain.c:847` — via
`knowledge/subsystems/executor.md`).

### ExecProcNode
The volcano-style "pull one tuple" entry point of a plan node. Rather than a
central switch, each `PlanState` stores its own `ExecProcNode` function pointer
(installed by `ExecInitNode`), so the executor advances any node uniformly by
calling `node->ExecProcNode(node)`. [verified-by-code] (via
`knowledge/files/src/backend/executor/execProcnode.c.md`).

### ExecReScan
Resets a plan node's execution state so it can be scanned again from the start —
used for the inner side of a nested loop, correlated subplans, and rewound
cursors. `execAmi.c` dispatches on `nodeTag` to the per-node `ExecReScan<Node>`
routine, which clears tuple state and rescans children. [verified-by-code] (via
`knowledge/files/src/backend/executor/execAmi.c.md`).

### executor
The engine that runs a finished plan tree. Each query passes through the
`ExecutorStart` / `ExecutorRun` / `ExecutorFinish` / `ExecutorEnd` lifecycle;
`ExecutorRun` (hookable, dispatching to `standard_ExecutorRun`) pulls tuples
through the plan node tree one node at a time. [verified-by-code]
(`execMain.c:308,318` — via
`knowledge/files/src/backend/executor/execMain.c.md`).

### ExecutorStart
The first of the four-phase executor API
(`ExecutorStart`/`ExecutorRun`/`ExecutorFinish`/`ExecutorEnd`). It builds the
`PlanState` tree from the `PlannedStmt` via `ExecInitNode`, allocates the
`EState`, and wires up result relations and the tuple destination — but runs no
tuples yet. [verified-by-code] (via
`knowledge/files/src/backend/executor/execParallel.c.md`).

### EXPOSE_TO_CLIENT_CODE
A guard macro used in catalog headers to mark a block of constant definitions
(enum-like character/OID constants) that should also be visible to client code,
so `genbki.pl` copies them into the generated client-facing header. Constants
inside such a block are frequently on-disk values, making them hard to change.
[verified-by-code] (via
`knowledge/files/src/include/catalog/pg_propgraph_element.h.md`).

### Expr
The node supertype for scalar expression trees (`Var`, `Const`, `OpExpr`,
`FuncExpr`, …) evaluated to produce a value during execution. Expression nodes
are compiled into a flat `ExprState` program by `ExecInitExpr` rather than
walked node-by-node at run time. [inferred] (via
`knowledge/files/src/include/nodes/primnodes.h.md`).

### ExprContext
The per-node evaluation scratchpad attached to a `PlanState`: it holds the
inner/outer/scan tuple slots an expression reads and the short-lived
`ecxt_per_tuple_memory` context that `ExecEvalExpr` allocates into and that is
reset once per tuple. [verified-by-code] (`pl_exec.c:8771` — via
`knowledge/files/src/pl/plpgsql/src/pl_exec.md`).

### ExprState
The compiled, flattened form of an expression tree: `ExecInitExpr` walks an
`Expr` once and emits a linear program of `ExprEvalStep`s that
`ExecInterpExpr` (or JIT-compiled code) runs per tuple, avoiding a recursive
tree walk on the hot path. [from-comment] (via
`knowledge/files/src/backend/executor/execExpr.c.md`).

### FdwRoutine
The struct of callback pointers (`GetForeignRelSize`, `GetForeignPaths`,
`GetForeignPlan`, `BeginForeignScan`, `IterateForeignScan`, the modify and
analyze hooks, …) that a foreign-data wrapper's `*_handler` function populates
and returns; core code dispatches every FDW operation through it rather than
hard-coding any wrapper. [verified-by-code]
(via `knowledge/files/contrib/postgres_fdw/postgres_fdw.h.md`).

### FLEXIBLE_ARRAY_MEMBER
The portable spelling of a trailing C99 flexible array member used pervasively
for variable-length structs (a trailing `char name[FLEXIBLE_ARRAY_MEMBER]` or
similar). It lets a struct be over-allocated so the array runs off the end
without tripping bounds checkers. [verified-by-code] (`plpgsql.h:460` — via
`knowledge/files/src/pl/plpgsql/src/plpgsql.md`).

### FlushBuffer
The bufmgr routine that writes a dirty shared buffer's page out to its
relation via `smgrwrite`, after ensuring WAL up to the page's LSN is flushed
(the WAL-before-data rule). Called by the checkpointer, the bgwriter's
`BgBufferSync`, and by any backend that has to evict a dirty victim buffer.
[verified-by-code] (`bufmgr.c:4512-4628` — via
`knowledge/files/src/backend/storage/buffer/bufmgr.c.md`).

### fmgr (function manager)
The uniform calling convention for invoking any SQL-callable C function:
arguments and result travel as `Datum`s inside a `FunctionCallInfo`, and
`PG_FUNCTION_INFO_V1` plus the `PG_GETARG_*`/`PG_RETURN_*` macros wrap the
boilerplate. The `FmgrInfo` carries the resolved function, collation, and
argument count. [from-comment] (via `knowledge/idioms/fmgr.md`).

### FmgrInfo
The cached lookup result for a callable function: it bundles the resolved
function pointer, expected argument count, strictness, and a memory context, so
repeated `FunctionCall*` invocations skip the catalog lookup. Built once by
`fmgr_info` and reused for the life of the operation. [from-comment]
(`fastpath.c:37` — via `knowledge/subsystems/tcop.md`).

### ForeignScan
The executor plan node that scans a foreign table through an FDW. For
postgres_fdw `postgresGetForeignPlan` builds it, `postgresBeginForeignScan`
opens the remote connection and declares a cursor, and `postgresIterateForeignScan`
fetches rows in batches. [verified-by-code]
(via `knowledge/files/contrib/postgres_fdw/postgres_fdw.c.md`).

### FormData
The C struct mirroring a system catalog's fixed columns, named
`FormData_pg_<catalog>` with a pointer typedef `Form_pg_<catalog>`. After
`GETSTRUCT` on a `HeapTuple`, code reads the row's fixed part by casting to this
struct; variable-length/nullable columns past it need `heap_getattr`.
[verified-by-code] (`pg_subscription.h:131` — via
`knowledge/files/src/include/catalog/pg_subscription.h.md`).

### FPI (full-page image)
A complete copy of a disk page written into the WAL the first time the page is
modified after a checkpoint, protecting against torn-page writes during
recovery. `XLogInsert` adds an FPI automatically when needed (tunable per
buffer via `REGBUF_FORCE_IMAGE` / `REGBUF_NO_IMAGE`). [from-comment] (via
`knowledge/files/src/backend/access/transam/xloginsert.c.md`).

### FSM (free space map)
The per-relation map tracking approximate free space in each page so inserts
can find room without scanning. It is itself stored as a relation fork
(`FSM_FORKNUM`) organized as a tree of `BLCKSZ` pages. [from-comment] (via
`knowledge/files/src/backend/storage/freespace/freespace.c.md`).

### FullTransactionId
A 64-bit transaction id that carries the wraparound epoch in its high 32 bits
alongside the ordinary 32-bit `TransactionId`, so it never wraps and can be
compared with plain integer ordering. Used where wraparound ambiguity would be
fatal, e.g. nextXid bookkeeping. [verified-by-code] (`transam.h:65-68` — via
`knowledge/files/src/include/access/transam.h.md`).

### Gather
The executor node that collects tuples from parallel workers (and, for
`GatherMerge`, preserves sort order) back into the leader's single stream,
marking the boundary between the parallel and serial portions of a plan. Below
it the plan runs in multiple worker backends; above it execution is serial.
[inferred] (via `knowledge/files/src/backend/executor/nodeGather.c.md`).

### GetNewTransactionId
The allocator for a fresh XID: it advances the shared `nextXid` counter under
`XidGenLock`, extends CLOG/SUBTRANS as needed, fires the wraparound
warning/limit logic, and records the xid in the backend's `PGPROC`. Called
lazily on first write, so read-only transactions never consume an xid.
[verified-by-code] (`varsup.c:68` — via
`knowledge/files/src/backend/access/transam/varsup.c.md`).

### GetSnapshotData
The routine that builds an MVCC snapshot by scanning the `ProcArray` under
`ProcArrayLock` (SHARED) to record `xmin`, `xmax`, and the set of in-progress
xids. Its cost scales with the number of active backends, which is why the
snapshot-scalability work cached parts of it. [verified-by-code]
(`procarray.c:2349` — via `knowledge/subsystems/storage-ipc.md`).

### GetUserId
Returns the current *effective* user OID (the one permission checks run
against), which can differ from the session user under `SECURITY DEFINER` or
`SET ROLE`. Permission-sensitive code such as postgres_fdw picks
`OidIsValid(checkAsUser) ? checkAsUser : GetUserId()` so it acts as the
row-security-defining role, matching `ExecCheckPermissions`. [verified-by-code]
(`postgres_fdw.c:1743` — via
`knowledge/files/contrib/postgres_fdw/postgres_fdw.c.md`).

### GIN (Generalized Inverted Index)
An index access method optimized for composite values where many keys map to
one row — full-text `tsvector`, arrays, `jsonb` — built around a posting-list
structure plus a pending-list fast path for cheap inserts. Scans union/intersect
posting lists for the matched keys. [from-comment] (via
`knowledge/files/src/backend/access/gin/ginget.c.md`).

### GiST (Generalized Search Tree)
A balanced-tree index access-method *framework* parameterized by an operator
class that supplies `consistent`, `union`, `penalty`, `picksplit`, and friends,
letting one structure serve R-tree, range, nearest-neighbour, and many other
indexing schemes. Search descends subtrees whose predicate the `consistent`
function cannot rule out. [from-comment] (via
`knowledge/files/src/backend/access/gist/gistget.c.md`).

### GRAPH_TABLE
The SQL/PGQ property-graph query construct that produces a rowset from a graph
pattern match. In the parser it appears as its own range-table-entry kind
(`RTE_GRAPH_TABLE`) with a matching `ParseNamespaceItem`, alongside the other
FROM-item forms. [verified-by-code] (via
`knowledge/files/src/backend/parser/parse_relation.c.md`).

### GUC (Grand Unified Configuration)
PostgreSQL's runtime configuration-variable system. Every setting (`work_mem`,
`wal_level`, …) is a `config_generic` record with a bool/int/real/string/enum
subclass; all built-in GUCs are registered into one table by
`build_guc_variables` at startup, and extensions add their own via
`DefineCustom*Variable`. [verified-by-code] (`guc.c:871` — via
`knowledge/files/src/backend/utils/misc/guc.c.md`).

### HashAgg
The hash-based grouping executor strategy (`nodeAgg.c`): it builds an in-memory
`TupleHashTable` keyed by the grouping columns, accumulating transition values
per group, and spills batches to disk when the hash table exceeds `work_mem`
(hash-agg spill). [verified-by-code] (via
`knowledge/files/src/backend/executor/execGrouping.c.md`).

### HbaLine
The in-memory parsed form of one `pg_hba.conf` record — connection type,
address range, database/role matchers, auth method, and method options. The
authentication code matches an incoming connection to an `HbaLine` and then runs
the named method (including pluggable validators such as OAuth).
[verified-by-code] (via
`knowledge/files/src/backend/libpq/auth-oauth.c.md`).

### heap
PostgreSQL's default table access method: tuples are stored as
`HeapTupleHeader`-prefixed rows inside `BLCKSZ` pages, with old/new row
versions coexisting for MVCC. HOT (heap-only-tuple) chains and the
tuple-locking protocol — the trickier invariants — are documented in the heap
READMEs. [from-README] (`README.HOT`, `README.tuplock` — via
`knowledge/files/src/backend/access/heap/README.md`).

### HEAP_ONLY_TUPLE
An infomask2 bit (`0x8000`) marking a heap tuple that no index points at
directly because it was produced by a HOT update and is reachable only by
following a `t_ctid` chain from an indexed ancestor. It is what lets HOT updates
skip index maintenance. [verified-by-code] (`htup_details.h:293-296` — via
`knowledge/files/src/include/access/htup_details.h.md`).

### HEAP_XMIN_COMMITTED
A heap-tuple hint bit caching "this tuple's inserting xact is known committed"
(its `HEAP_XMAX_COMMITTED` sibling does the same for the deleter). A set hint
may only be written after that xact's commit WAL is flushed, so a hint never
lies even though it is not itself WAL-logged. [verified-by-code]
(`heapam_visibility.c:142` — via `knowledge/subsystems/access-heap.md`).

### HeapTuple
The lightweight in-memory wrapper for a heap row:
`struct HeapTupleData { uint32 t_len; ItemPointerData t_self; Oid t_tableOid;
HeapTupleHeader t_data; }` — a length, the row's self-TID, its table OID, and a
pointer to the on-page header. The bit-level layout lives in `htup_details.h`.
[verified-by-code] (`htup.h:62-69` — via
`knowledge/files/src/include/access/htup.h.md`).

### HeapTupleHeader
The on-page prefix of every heap tuple (`HeapTupleHeaderData`): it carries the
`xmin`/`xmax` transaction stamps, the `t_ctid` forward link, an infomask of
status bits, and the null bitmap, ahead of the user data. Its bit-level layout
and accessor macros live in `htup_details.h`. [from-comment] (via
`knowledge/files/src/include/access/htup_details.h.md`).

### hint bit
A cached commit/abort status bit (`HEAP_XMIN_COMMITTED`, `HEAP_XMAX_COMMITTED`,
…) stamped into a tuple's infomask the first time a backend resolves its
transaction's fate via clog, so later visibility checks skip the clog lookup.
Setting one only dirties the page as a *hint* (`MarkBufferDirtyHint`) and is not
WAL-logged unless checksums/`wal_log_hints` are on. [from-comment] (via
`knowledge/subsystems/access-heap.md`).

### HOT (heap-only tuple)
An UPDATE optimization: when no indexed column changes and the new row version
fits on the same page, PostgreSQL chains the new tuple to the old via `t_ctid`
without inserting new index entries. The update is logged as
`XLOG_HEAP_HOT_UPDATE`, and index scans reach the live version by following the
HOT chain from the indexed root tuple. [verified-by-code] (`heapam.c:62` — via
`knowledge/files/src/backend/access/heap/heapam.c.md`).

### IDENTIFY_SYSTEM
The first replication-protocol command a client issues: the walsender replies
with the system identifier, current timeline, current WAL flush position, and
default database, which the client uses to set up streaming. [verified-by-code]
(via `knowledge/files/src/backend/replication/repl_gram.y.md`).

### INCOMPLETE_SPLIT
A btree page flag recording that a page was split but its parent downlink has
not yet been inserted (the downlink is a separate WAL record). A later
insert/scan that encounters the flag must finish the split first; this two-step
design is what makes nbtree split crash-safe without holding parent locks during
the split. [verified-by-code] (via
`knowledge/files/src/backend/access/nbtree/nbtinsert.c.md`).

### IndexAmRoutine
The callback table an index access method returns from its `*handler`
function, advertising build/insert/scan/vacuum entry points
(`ambuild`, `aminsert`, `amgettuple`, `amgetbitmap`, `ambulkdelete`,
`amvacuumcleanup`, …) plus capability flags. Core code dispatches through this
struct rather than hard-coding any one AM. [from-comment] (`amapi.c:1` — via
`knowledge/files/src/backend/access/index/amapi.c.md`).

### InitPlan
A sub-SELECT the planner can prove is uncorrelated, so it is executed exactly
once and its result stashed for reuse rather than re-run per outer row.
`SS_process_ctes` may also turn a CTE into an initplan; `root->cte_plan_ids`
records which (-1 = none). [from-comment] (`subselect.c:883` — via
`knowledge/files/src/backend/optimizer/plan/subselect.c.md`).

### InitPostgres
The per-backend initialization routine run early in a new backend: it joins
shared memory, sets up the relcache/catcache, binds to the target database, and
performs authorization checks before the backend enters its command loop.
[verified-by-code] (`utils/init/postinit.c:716` — via
`knowledge/architecture/query-lifecycle.md`).

### InvalidOid
The sentinel OID value 0, meaning "no object" — never a valid catalog row OID.
It is used pervasively as a null/absent marker in fixed `Oid` columns and
keys, e.g. PL/Tcl uses `InvalidOid` as the hash key for the untrusted shared
interpreter. [from-comment] (`pltcl.c:112` — via
`knowledge/files/src/pl/tcl/pltcl.c.md`).

### ItemPointer
A `(BlockNumber, OffsetNumber)` pair — the TID — locating a line-pointer slot on
a page. A tuple's `t_self` is its own TID; `t_ctid` points to its successor
version (or to itself when there is none). [verified-by-code]
(`htup_details.h:86` — via `knowledge/subsystems/access-heap.md`).

### JSON_TABLE
The SQL/JSON construct `JSON_TABLE(context_item, path COLUMNS (...))` that
turns a JSON document into a relational rowset. Parse analysis in
`parse_jsontable.c` expands the COLUMNS clause into a `TableFunc` node of type
`JSTYPE_JSON_TABLE`. [verified-by-code] (via
`knowledge/files/src/backend/parser/parse_jsontable.c.md`).

### KnownAssignedXids
The standby-side array that tracks transactions seen as in-progress in the WAL
stream during hot-standby recovery, so a standby can build MVCC snapshots
without the primary's live PGPROC array. Recovery records and prunes entries as
it replays commit/abort and running-xacts records. [verified-by-code]
(`xlogrecovery.c:161` — via
`knowledge/files/src/backend/access/transam/xlogrecovery.c.md`).

### latch
The inter-process wait/wake primitive: a backend `WaitLatch`es on its own
`Latch` (often together with socket readiness and a timeout) and another process
calls `SetLatch` to wake it, replacing busy-polling for event-driven sleeps.
Latches are signal- and crash-safe and underlie almost every auxiliary process's
main loop. [from-comment] (via
`knowledge/files/src/backend/storage/ipc/latch.c.md`).

### List
PostgreSQL's ubiquitous list type — an array-backed `List` of pointers
(`T_List`), integers, or OIDs — manipulated with `lappend`, `lfirst`,
`foreach`, and friends. Almost every multi-element structure in the parser,
planner, and executor is a `List`. [from-comment] (via
`knowledge/idioms/node-types-and-lists.md`).

### LockAcquire
The heavyweight (regular) lock-manager entry point: it finds or creates the
shared `LOCK`/`PROCLOCK` for a lock tag, checks conflicts via
`LockCheckConflicts`, and either grants immediately, takes the fast path for a
weak relation lock, or queues the backend to wait. `LockRelease` /
`LockReleaseAll` undo it. [verified-by-code] (`lock.c:806` — via
`knowledge/files/src/backend/storage/lmgr/lock.c.md`).

### LockBufHdr
Acquires the per-buffer header spinlock encoded in the high bit of the
`BufferDesc` atomic state word, giving exclusive access to the buffer's tag and
flags for the brief critical section of pinning, tag reassignment, or flag
updates. `WaitBufHdrUnlocked` spins for a concurrent holder to release.
[verified-by-code] (`bufmgr.c:7527-7593` — via
`knowledge/files/src/backend/storage/buffer/bufmgr.c.md`).

### LOCKTAG_TUPLE
A heavyweight-lock tag identifying a specific tuple (relation + block +
offset), used where buffer content locks are too short-lived — e.g.
`systable_inplace_update` takes one so a concurrent reader of a
`pg_class.relfrozenxid` in-place update sees a torn write only if it explicitly
re-reads. [verified-by-code] (via
`knowledge/files/src/backend/access/index/genam.c.md`).

### logical decoding
The mechanism that turns the physical WAL stream back into a logical sequence
of row-level INSERT/UPDATE/DELETE changes, driven by a replication slot and an
output plugin. It underpins logical replication and CDC tooling without those
consumers parsing WAL themselves. [from-README] (via
`knowledge/subsystems/replication.md`).

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

### MAKE_SYSCACHE
The macro that declares one syscache: it ties a `SysCacheIdentifier` enum value
to the backing catalog and the unique index used as the lookup key, feeding the
generated `cacheinfo[]` table that `InitCatalogCache` builds from.
[verified-by-code] (`syscache.c:13` — via
`knowledge/files/src/backend/utils/cache/syscache.c.md`).

### MarkBufferDirty
The call that flags a pinned, exclusively-locked buffer as modified so the
background writer/checkpointer will eventually write it; it must run inside the
WAL critical section so the dirty mark and the WAL record are atomic with
respect to crashes. Contrast `MarkBufferDirtyHint`, which is for
non-WAL-critical hint-bit changes. [verified-by-code] (`bufmgr.c:3156` — via
`knowledge/files/src/backend/storage/buffer/bufmgr.c.md`).

### MaxAllocSize
The 1 GB − 1 (`0x3fffffff`) soft ceiling that ordinary `palloc` enforces;
requests above it raise an error. Chosen so allocation sizes always fit safely
in arithmetic; allocations that genuinely need more must use the `*Huge`
variants (`MemoryContextAllocHuge`, `palloc_extended` with `MCXT_ALLOC_HUGE`),
which raise the bound to `SIZE_MAX/2`. [from-comment] (`memutils.h:40` — via
`knowledge/idioms/memory-contexts.md`).

### MCXT_ALLOC_NO_OOM
A flag to `palloc_extended`/`MemoryContextAllocExtended` that makes an
allocation return `NULL` on failure instead of the usual
`ereport(ERROR)`-on-OOM behavior, for the rare caller that wants to handle
out-of-memory itself. [verified-by-code] (`mcxt.c:1200-1214` — via
`knowledge/subsystems/utils-mmgr.md`).

### MEMORY_CONTEXT_CHECKING
A cassert-only build option (implied by `USE_ASSERT_CHECKING`) that makes the
allocators write sentinel bytes (`0x7E`) just past each chunk's requested size
and check them on free, catching small buffer overruns. It also enables
`randomize` fills of freed memory. [from-comment] (via
`knowledge/files/src/backend/utils/mmgr/memdebug.c.md`).

### MemoryChunk
The per-allocation header an allocator prepends to each `palloc`'d block,
encoding the owning context (or an offset to it) and the chunk size in a packed
word so that `pfree`/`repalloc` can recover the context from just the user
pointer. [verified-by-code] (`aset.c:128` — via
`knowledge/files/src/backend/utils/mmgr/aset.c.md`).

### MemoryContext
A node in the hierarchical allocator: every `palloc` charges the
`CurrentMemoryContext`, and resetting or deleting a context frees all its
chunks at once — how PostgreSQL avoids per-allocation leak tracking. Contexts
nest (TopMemoryContext → per-query → per-tuple) so cleanup scopes to the right
lifetime. [from-comment] (via `knowledge/idioms/memory-contexts.md`).

### MemoryContextDelete
Frees a memory context and all its children in one shot, releasing every
allocation made in them without per-chunk `pfree`s — the workhorse of PG's
region-based memory discipline. Tearing down a per-function or per-query context
(e.g. plpgsql's `func->fn_cxt`) reclaims all its palloc'd state at once.
[verified-by-code] (via
`knowledge/files/src/pl/plpgsql/src/pl_funcs.md`).

### MemoryContextSwitchTo
The inline that sets `CurrentMemoryContext` to a given context and returns the
previous one. The idiom is "switch, allocate, switch back" using the saved
return value; it is the single discipline that keeps allocations in the right
lifetime bucket. [verified-by-code] (via
`knowledge/idioms/memory-contexts.md`).

### MergeAppend
The order-preserving sibling of `Append`: it merges the already-sorted outputs
of its child subplans (e.g. partitions each with a matching index order) into
one sorted stream, avoiding a top-level Sort. [verified-by-code] (via
`knowledge/files/src/backend/executor/execProcnode.c.md`).

### MessageContext
The per-client-message memory context: it is reset at the top of each
protocol message in `PostgresMain`, so parse/analyze/plan allocations for one
command are reclaimed before the next, without per-allocation `pfree`.
[verified-by-code] (`mcxt.c:161` — via `knowledge/subsystems/utils-mmgr.md`).

### MinimalTuple
A stripped heap-tuple form used for executor-internal tuples (sorts, hashes,
tuplestores) that drops the system columns a stored row needs. Its layout
deliberately overlaps `HeapTupleHeaderData` below `t_infomask2` so the two can
be cast to share accessor code. [from-comment] (`htup_details.h:3-13` — via
`knowledge/files/src/include/access/htup_details.h.md`).

### ModifyTable
The executor plan node that performs `INSERT` / `UPDATE` / `DELETE` / `MERGE`,
driving the per-row table-AM and trigger machinery via
`ExecForeignInsert/Update/Delete` for foreign targets. postgres_fdw can bypass
it entirely with "direct modify", emitting the remote UPDATE/DELETE straight
from a single ForeignScan when all SET clauses are shippable and there are no
local quals. [verified-by-code]
(via `knowledge/files/contrib/postgres_fdw/postgres_fdw.c.md`).

### MultiXact
A "multiple transaction" id used as a tuple's `xmax` when several transactions
hold a shared lock (or a mix of share/update locks) on the same row at once. The
visibility code resolves the real updater lazily via `HeapTupleGetUpdateXid`,
which may force MultiXact SLRU I/O, so it only does so after the cheaper
infomask-only checks fail. [verified-by-code]
(`heapam_visibility.c:1173-1176` — via
`knowledge/files/src/backend/access/heap/heapam_visibility.c.md`).

### MultiXactId (multixact)
An identifier standing in for a *set* of transactions that simultaneously hold
a row lock (e.g. several `SELECT ... FOR SHARE`), stored in a tuple's xmax when
more than one locker is involved. Members and offsets live in dedicated SLRUs
under `pg_multixact/`. [from-comment] (via
`knowledge/files/src/backend/access/transam/multixact.c.md`).

### MVCC (multiversion concurrency control)
PostgreSQL's concurrency model: each row version (tuple) carries `xmin`/`xmax`
transaction stamps, and a snapshot decides which versions a query may see, so
readers never block writers. The visibility logic lives in routines like
`HeapTupleSatisfiesMVCC`, which test a tuple's xmin/xmax against the snapshot.
[verified-by-code] (`heapam_visibility.c:938` — via
`knowledge/files/src/backend/access/heap/heapam_visibility.c.md`).

### MyLatch
The current process's own latch — the one it sleeps on in
`WaitLatch(MyLatch, ...)`. Condition variables wake a waiter via
`SetLatch(waiter->procLatch)` rather than a semaphore, which is exactly what
makes CV waits interruptible (they honour `WL_TIMEOUT` and integrate with
`CHECK_FOR_INTERRUPTS()`), unlike LWLock waits. [verified-by-code] (via
`knowledge/files/src/backend/storage/lmgr/condition_variable.c.md`).

### MyProc
The global pointer to the current backend's own `PGPROC` slot in shared
memory, valid for the life of the process. Through it a backend exposes its
`xid`/`xmin`, wait state, and latch to the rest of the system (snapshots, lock
manager, `pg_stat_activity`). [verified-by-code] (via
`knowledge/data-structures/pgproc-fields.md`).

### NameData
The fixed-width catalog name type: a struct wrapping `char data[NAMEDATALEN]`
(64 bytes), used for identifier columns like `relname`/`proname` so they sit at
fixed offsets in a catalog row rather than as variable-length text.
[inferred] (via `knowledge/idioms/catalog-conventions.md`).

### NestLoop
The nested-loop join plan node: for each outer-side row it scans (or re-scans)
the inner side, optionally passing the outer row's values down as
`NestLoopParam`s to drive a parameterized inner index scan. [verified-by-code]
(`plannodes.h:1006` — via
`knowledge/files/src/include/nodes/plannodes.h.md`).

### Node
The tagged-union base of nearly every PostgreSQL tree structure: each node
begins with a `NodeTag` so generic code can dispatch on type via `IsA()` and
the auto-generated copy/equal/out/read functions. Parse trees, plan trees, and
most internal structures are Node trees. [from-comment] (via
`knowledge/files/src/include/nodes/nodes.h.md`).

### NodeTag
The integer enum stamped as the first field of every `Node` so the copy/equal/
out/read machinery and `IsA()` can recognize a node's concrete type at runtime.
Tags are generated for core nodes; extensions reuse `T_ExtensibleNode` plus a
registered name. [verified-by-code] (`extensible.h:32` — via
`knowledge/files/src/backend/nodes/extensible.c.md`).

### NUM_LOCK_PARTITIONS
The fixed number (16) of partitions the heavyweight-lock shared hash table is
split into, each with its own LWLock, to spread contention. A backend needing
more than one partition lock must take them in partition-number order — a
deadlock-avoidance rule enforced in `CheckDeadLock`. [from-README] (via
`knowledge/files/src/backend/storage/lmgr/README.md`).

### OffsetNumber
The 1-based index of a line pointer within a page (the second half of an
`ItemPointer`/TID). `FirstOffsetNumber` is 1; `InvalidOffsetNumber` is 0.
[verified-by-code] (`htup_details.h:86` — via
`knowledge/subsystems/access-heap.md`).

### Oid (object identifier)
The unsigned 32-bit type that names every catalog object (relations, types,
functions, operators, …); a value of `InvalidOid` (0) means "none". OIDs are
assigned from a global counter, with a reserved low range hand-assigned to
built-in objects. [inferred] (via `knowledge/idioms/catalog-conventions.md`).

### opclass (operator class)
A catalog object (`pg_opclass`) binding a data type to an index access method
by naming the operators and support functions an index needs (e.g. btree's
`<`,`<=`,`=`,`>=`,`>` plus the comparison support function). It is how
`CREATE INDEX` knows how to compare a column's values. [inferred] (via
`knowledge/files/src/backend/access/index/amapi.c.md`).

### OpExpr
The expression node for a binary (or unary) operator invocation, carrying the
operator OID, result type, input collation, and argument list. The executor
evaluates it through the operator's underlying function; deparsers like
postgres_fdw only ship it remotely when `is_shippable(opno, OperatorRelationId)`
holds. [verified-by-code] (via
`knowledge/files/contrib/postgres_fdw/deparse.c.md`).

### opfamily (operator family)
A grouping of related operator classes (`pg_opfamily`) that lets cross-type
operators participate in the same index strategy — e.g. int2/int4/int8 share
one btree family so a mixed-type predicate can still use an index. [inferred]
(via `knowledge/files/src/backend/access/index/amapi.c.md`).

### palloc
Context-aware memory allocation. Memory returned by `palloc` belongs to the
`CurrentMemoryContext` rather than to the caller; it can be freed individually
with `pfree` but is more usually reclaimed in bulk when its context is reset or
deleted. OOM is reported via `ereport`, never a NULL return. [from-comment]
(`palloc.h:1-9,31-52` — via
`knowledge/files/src/include/utils/palloc.h.md`).

### parallel query
The execution mode in which the leader backend launches parallel worker
backends (via `dsm` + a `ParallelContext`) to run a parallel-aware portion of a
plan beneath a `Gather`. Functions are labelled parallel-safe / -restricted /
-unsafe to decide what may run in a worker. [from-comment] (via
`knowledge/files/src/backend/access/transam/parallel.c.md`).

### PARAM_EXEC
The parameter kind for values passed internally within a plan at run time —
correlated-subquery references, recursive-CTE working state, and similar — as
opposed to `PARAM_EXTERN` client bind parameters. The planner assigns each a
slot id held in `PlannerInfo`. [verified-by-code] (via
`knowledge/files/src/backend/optimizer/plan/subselect.c.md`).

### ParseState
The working context threaded through parse analysis: it carries the range
table being built, the source query text (for error positions), parameter-type
hooks, and flags controlling what expression kinds are allowed in the current
clause. [verified-by-code] (`parse_node.h:91` — via
`knowledge/files/src/backend/parser/parse_node.c.md`).

### Path
The planner's representation of one candidate way to produce a relation's rows
(seqscan, indexscan, a particular join order), annotated with estimated startup
and total cost. The optimizer enumerates Paths into each `RelOptInfo`, keeps
the cheapest non-dominated ones, and turns the winner into a `Plan`.
[from-comment] (via `knowledge/subsystems/optimizer.md`).

### PGC_SUSET
The GUC context level for settings that only a superuser (or a role granted
`SET` on them) may change at run time within a session — e.g. pgcrypto's
`pgcrypto.builtin_crypto_enabled`. It sits between `PGC_SIGHUP` (config-file
only) and `PGC_USERSET` (any user) in the privilege ladder. [verified-by-code]
(via `knowledge/files/contrib/pgcrypto/pgcrypto.md`).

### PGPROC
The per-process shared-memory slot describing a backend to the rest of the
system. Every backend is assigned exactly one `PGPROC` from
`ProcGlobal->allProcs` at startup and returns it to a freelist at exit; it
holds the proc's wait state, LSNs, and lock links, and is how other backends
find and signal it. [verified-by-code] (`proc.h:184` — via
`knowledge/files/src/include/storage/proc.h.md`).

### Plan
The finished, executable tree produced by `create_plan` from the chosen Path —
a tree of plan nodes (`SeqScan`, `HashJoin`, `Agg`, …) carrying target lists,
qualifications, and cost estimates but no live execution state. The executor
instantiates it into a parallel `PlanState` tree at `ExecutorStart`. [inferred]
(via `knowledge/files/src/include/nodes/plannodes.h.md`).

### PlannedStmt
The top node of a finished plan handed from planner to executor: it wraps the
plan tree plus the range table, result-relation list, command type, and
`hasReturning`/`canSetTag` flags. `ProcessUtility` vs the executor branch on
whether a statement produces a `PlannedStmt`. [verified-by-code] (`utility.c:96`
— via `knowledge/subsystems/tcop.md`).

### planner
The optimizer stage that turns a `Query` into an executable `Plan` tree.
`planner()` / `standard_planner()` drive `subquery_planner` on the top query,
enumerate and cost candidate Paths, pick the cheapest, and hand it to
`create_plan` to materialize the final plan. [verified-by-code] (via
`knowledge/files/src/backend/optimizer/plan/planner.c.md`).

### PlannerInfo
The central planner working struct (the "query level"): it holds the join-tree,
the `RelOptInfo` array, equivalence classes, and accumulated paths for one query
or subquery level. Almost every optimizer routine takes a `PlannerInfo *root`.
[verified-by-code] (`analyzejoins.c:1869` — via
`knowledge/subsystems/optimizer.md`).

### PlanState
The per-execution mutable mirror of a `Plan` node: `ExecInitNode` builds a
`PlanState` tree shadowing the `Plan` tree, holding tuple slots, expression
states, and instrumentation, and `ExecProcNode` pulls tuples through it. Plan
is read-only and shareable; PlanState is per-execution. [inferred] (via
`knowledge/files/src/include/nodes/execnodes.h.md`).

### portal
The backend-local object holding the execution state of a single query or
cursor — its plan, parameters, and memory contexts — between bind and the
fetching of results. Portals are created under `TopPortalContext` (e.g. by
`CreateNewPortal`) and torn down when the statement completes or the cursor
closes. [verified-by-code] (`portalmem.c:237` — via
`knowledge/files/src/backend/utils/mmgr/portalmem.c.md`).

### PortalRun
The tcop entry point that executes a portal (a named, runnable query container)
and routes its result tuples to a `DestReceiver`. The extended-query and simple-
query paths both funnel through it; `PortalRun(FETCH_ALL, dest)` drains a portal
to completion. [verified-by-code]
(via `knowledge/files/src/backend/tcop/postgres.c.md`).

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

### ProcArray
The shared-memory array of pointers to active backends' `PGPROC`s, used to take
snapshots (which xids are in-progress), compute the oldest visible xid, and
find backends to signal. `GetSnapshotData` walks it under `ProcArrayLock`.
[from-comment] (via `knowledge/files/src/backend/storage/ipc/procarray.c.md`).

### ProcArrayLock
The LWLock guarding the `ProcArray` (the set of live `PGPROC`s). Snapshot
building takes it SHARED (`GetSnapshotData`); transaction commit/abort and
backend exit take it EXCLUSIVE to update visibility. Its contention is a known
scalability pressure point. [verified-by-code] (`procarray.c:2170` — via
`knowledge/subsystems/storage-ipc.md`).

### ProcessUtility
The dispatch point for non-optimizable statements — DDL, transaction control,
COPY, VACUUM, and the like — that bypass the planner/executor. It is the
canonical hook target (`ProcessUtility_hook`) for extensions wanting to
intercept commands. [verified-by-code] (`utility.c:504` — via
`knowledge/subsystems/tcop.md`).

### ProcGlobal
The shared `PROC_HDR` structure anchoring all `PGPROC`s: the `allProcs` array
plus the per-class free lists (regular, autovacuum, bgworker, walsender) and
cache-friendly mirrored arrays of xids/status flags scanned during snapshot
building. [verified-by-code] (`proc.h:444` — via
`knowledge/files/src/backend/storage/lmgr/proc.c.md`).

### ProcSleep
The lock-manager primitive that puts a backend to sleep on its PGPROC
semaphore while it waits for a heavyweight lock, after `JoinWaitQueue` has
inserted it into the lock's wait queue. It wakes on the deadlock-timeout
SIGALRM (re-checking `got_deadlock_timeout`) or when `ProcWakeup` grants the
lock. [verified-by-code] (`proc.c:1348` — via
`knowledge/files/src/backend/storage/lmgr/proc.c.md`).

### PushFilter / PullFilter
pgcrypto's streaming I/O abstraction: a `PushFilter` chain transforms bytes on
the way out (encrypt, compress) and a `PullFilter` chain transforms them on the
way in (decrypt, decompress), each stage wrapping the next. The PGP compression
code adapts zlib `deflate`/`inflate` as filter stages this way. [from-comment]
(via `knowledge/files/contrib/pgcrypto/pgp-compress.md`).

### PyObject
CPython's universal reference-counted object handle; in PL/Python every SQL
value, plan, cursor, and the `plpy` module itself is exchanged as a `PyObject *`
across the embedding boundary. PL/Python maps each SQLSTATE to a `PyObject *`
exception class so SQL errors surface as catchable Python exceptions.
[verified-by-code] (via
`knowledge/files/src/pl/plpython/plpy_plpymodule.md`).

### Query
The parse-analysis output: a normalized tree describing one SQL statement's
semantics — its range table, target list, join tree, and qualifications —
after names and types are resolved but before planning. The rewriter transforms
Querys (applying rules/views); the planner consumes them. [from-comment] (via
`knowledge/files/src/include/nodes/parsenodes.h.md`).

### QueryRewrite
The top entry of the rule-rewriter: it takes a single parse-analysed `Query`
and returns a list of Querys after applying ON SELECT (view expansion) and
non-SELECT rules, re-acquiring locks on rewritten range-table entries. It is the
stage between parse-analysis and planning. [verified-by-code]
(`rewriteHandler.c:4780-4870` — via
`knowledge/files/src/backend/rewrite/rewriteHandler.c.md`).

### RangeTblEntry (RTE)
A range-table entry: the parse/plan-tree node describing one relation reference
in a query's FROM clause — a table, subquery, join, function, or CTE. Its
`rtekind` discriminates the variant, and other query nodes refer to RTEs by a
1-based range-table index (`varno`) rather than by pointer. [verified-by-code]
(`parsenodes.h:1137` — via
`knowledge/files/src/include/nodes/parsenodes.h.md`).

### RawStmt
The grammar-output wrapper around one raw (un-analyzed) parse-tree statement,
carrying its byte offsets within the query string. The rewriter/analyzer
consumes a list of `RawStmt`s, one per statement in a multi-command string.
[verified-by-code] (`nodes/parsenodes.h:2187` — via
`knowledge/subsystems/parser-and-rewrite.md`).

### RecordTransactionCommit
The routine that makes a transaction durable: it snapshots pending invalidation
messages, writes (and flushes, per `synchronous_commit`) the commit WAL record,
and marks the xid committed in CLOG — strictly before sinval broadcast so other
backends never see the commit before its catalog effects. [from-comment]
(`inval.c:30` — via `knowledge/files/src/backend/utils/cache/inval.c.md`).

### relation
The internal name for any table-like object (table, index, sequence,
materialized view, composite type) — anything with a `pg_class` row and a
relfilenode. The in-memory `RelationData`/`Relation` handle caches a relation's
catalog metadata, tuple descriptor, and access-method routines. [from-README]
(via `knowledge/idioms/catalog-conventions.md`).

### RelationGetBufferForTuple
The heap-insertion helper that picks (or extends to) a page with room for a new
tuple: it tries the relation's cached target block, consults the FSM, and may
extend the relation, returning a pinned, exclusively-locked buffer. It also
encodes the two-buffer lock-ordering rule used by cross-page UPDATE.
[from-comment] (`hio.c:500` — via
`knowledge/files/src/include/access/hio.h.md`).

### relcache (relation cache)
The per-backend cache of `RelationData` entries, so opening a frequently-used
table doesn't re-read its `pg_class`/`pg_attribute`/index metadata each time. It
is kept coherent by shared-invalidation messages and can be rebuilt in place to
preserve pointer identity. [from-comment] (via
`knowledge/files/src/backend/utils/cache/relcache.c.md`).

### RelFileLocator
The physical identity of a relation's storage: the
`(spcOid, dbOid, relNumber)` triple that names the on-disk file set, distinct
from the relation's catalog OID. `smgropen`/`smgrcreate` and WAL records use it
so storage survives catalog OID reuse. [verified-by-code] (`storage.c:122` — via
`knowledge/files/src/backend/catalog/storage.c.md`).

### relfilenode (RelFileLocator)
The on-disk identity of a relation's storage — the (tablespace, database,
relfilenode-number) triple expressed as a `RelFileLocator` — distinct from the
catalog OID so operations like `TRUNCATE`/`CLUSTER` can swap storage without
changing the OID. The path on disk is derived from it by `relpathbackend`.
[from-comment] (via `knowledge/files/src/common/relpath.c.md`).

### RelOptInfo
The planner's per-relation bookkeeping node: for each base or join relation it
accumulates candidate `Path`s, row/width estimates, and available columns. Join
planning combines smaller `RelOptInfo`s into larger ones until the whole join
tree has a cheapest Path. [from-comment] (via
`knowledge/subsystems/optimizer.md`).

### reorder buffer
The logical-decoding component that buffers each in-progress transaction's
change stream and replays it, in commit order, to the output plugin only once
the transaction commits — turning the interleaved physical WAL back into
per-transaction logical change sets. Large transactions can spill to disk.
[from-comment] (via
`knowledge/files/src/backend/replication/logical/reorderbuffer.c.md`).

### replication slot
A named, persistent server-side marker that records how far a consumer
(physical standby or logical subscriber) has confirmed receiving WAL, so the
primary retains the WAL (and, for logical, the catalog xmin) that consumer still
needs. Slots prevent premature WAL removal at the cost of unbounded retention if
a consumer disappears. [from-comment] (via
`knowledge/files/src/backend/replication/slot.c.md`).

### ResourceOwner
The per-scope bookkeeper that records the buffers, relcache pins, catcache
references, locks, and files a (sub)transaction or portal acquired, so they can
all be released deterministically at commit/abort even on error. New owners nest
under a parent. [from-comment] (`pl_handler.c:223` — via
`knowledge/files/src/pl/plpgsql/src/pl_handler.md`).

### rmgr (resource manager)
A WAL resource manager: each subsystem that emits WAL (heap, btree, transaction
commit, …) registers a record-type id and callbacks (notably `rm_redo`) in the
global `RmgrTable[RM_MAX_ID + 1]`. Recovery dispatches each WAL record to its
rmgr's redo function to replay the change. [verified-by-code] (`rmgr.c`
`RmgrTable` — via `knowledge/files/src/backend/access/transam/rmgr.c.md`).

### RTE_SUBQUERY
The range-table-entry kind for a sub-SELECT appearing in a query's FROM clause;
its `subquery` field holds the nested `Query`. It is one of the RTEKind values
(`RTE_RELATION`, `RTE_SUBQUERY`, `RTE_FUNCTION`, `RTE_VALUES`, …) that classify
every entry in a query's range table. [verified-by-code] (via
`knowledge/files/src/backend/parser/parse_relation.c.md`).

### ScanKey
One element of the comparison-predicate array an index scan is opened with: a
(attribute, strategy/operator, comparison value) triple, optionally flagged for
NULL handling or `ScalarArrayOp`. AMs preprocess the `ScanKey[]` to drop
redundant or contradictory clauses before scanning. [from-comment] (via
`knowledge/files/src/backend/access/nbtree/nbtpreprocesskeys.c.md`).

### SearchSysCache
The primary entry point for a syscache lookup by key, returning a reference-
counted `HeapTuple` (or a cached negative entry meaning "no such row" so the
miss is not re-scanned). Callers must `ReleaseSysCache` the result.
[verified-by-code] (`catcache.c:1621` — via
`knowledge/subsystems/utils-cache.md`).

### SearchSysCacheExists
The existence-test family of syscache lookups (`SearchSysCacheExists1`…) that
returns a boolean without materializing or pinning the tuple — cheaper than
`SearchSysCache` + `ReleaseSysCache` when only "does a row exist" matters.
[verified-by-code] (`syscache.c:13` — via
`knowledge/files/src/backend/utils/cache/syscache.c.md`).

### SetLatch
Sets a process's latch, waking it from a `WaitLatch` sleep; it is the
edge-triggered "you have work / wake up" signal between backends and is
async-signal-safe, so signal handlers (e.g. the postmaster's
`handle_pm_*_signal`) set a flag and call `SetLatch` to break the main loop out
of its wait. [verified-by-code] (via
`knowledge/files/src/backend/postmaster/postmaster.c.md`).

### shm_mq (shared-memory message queue)
A single-reader/single-writer ring buffer living in a DSM segment, the standard
way a parallel leader and worker stream bytes (tuples, errors, tuple counts) to
each other. `shm_mq_send`/`shm_mq_receive` block on the peer's latch and report
`SHM_MQ_DETACHED` when the other end goes away. [from-comment] (via
`knowledge/files/src/backend/storage/ipc/shm_mq.c.md`).

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

### SMgrRelation
The storage-manager handle for a relation's physical files, obtained from
`smgropen` on a `RelFileLocator`. It is the layer `md.c` implements and through
which buffer reads/writes, extends, and truncates reach the filesystem.
[verified-by-code] (`storage.c:122` — via
`knowledge/files/src/backend/catalog/storage.c.md`).

### snapshot
A `SnapshotData` value that captures which tuple versions a query may see. Its
`SnapshotType` selects the visibility regime — the seven types are `MVCC`,
`SELF`, `ANY`, `TOAST`, `DIRTY`, `HISTORIC_MVCC`, and `NON_VACUUMABLE` — and a
single struct is reused across table AMs instead of a per-AM callback.
[from-comment] (`snapshot.h:19-30` — via
`knowledge/files/src/include/utils/snapshot.h.md`).

### snapshot builder (snapbuild)
The logical-decoding machinery that reconstructs, from the WAL stream alone, a
historical catalog snapshot valid enough to decode each transaction's row
changes with the right relation/type metadata. It must reach a consistent
starting point (tracking running xacts) before decoding can emit changes.
[from-comment] (via
`knowledge/files/src/backend/replication/logical/snapbuild.c.md`).

### SPI (Server Programming Interface)
The in-backend API (`SPI_connect`, `SPI_execute`, `SPI_prepare`, …) that lets C
code and PL handlers run SQL through the regular parser/planner/executor while
managing their own memory and snapshot nesting. It is how triggers, PL/pgSQL,
and many extensions issue queries. [from-comment] (via
`knowledge/idioms/spi.md`).

### spinlock
The lowest-level mutual-exclusion primitive — a busy-wait lock held for only a
handful of instructions, with no deadlock detection and no wait queue. Used to
protect tiny shared structures (and to bootstrap LWLocks); long or blocking
work must never happen under one. [from-comment] (via
`knowledge/files/src/backend/storage/lmgr/s_lock.c.md`).

### SSI (serializable snapshot isolation)
PostgreSQL's implementation of `SERIALIZABLE` via predicate locks (SIREAD
locks) that track read/write dependencies between concurrent transactions; when
a dangerous structure of rw-conflicts forms, one transaction is aborted with a
serialization failure. The bookkeeping lives in `predicate.c`. [from-comment]
(via `knowledge/files/src/backend/storage/lmgr/predicate.c.md`).

### START_CRIT_SECTION
Opens a critical section in which any `ereport(ERROR)` is promoted to PANIC,
used to bracket the buffer-modify + WAL-emit sequence so a backend can never
abort with the page changed but the WAL unwritten. No palloc-failure or
interrupt may escape until `END_CRIT_SECTION`. [from-comment] (`hio.c:35-38` —
via `knowledge/subsystems/access-heap.md`).

### START_REPLICATION
The replication-protocol command a standby or logical client sends to begin
streaming WAL from a position: `START_REPLICATION [SLOT s] PHYSICAL X/X
[TIMELINE n]` for physical, or `... SLOT s LOGICAL X/X (options)` for logical
decoding. Parsed by the replication grammar `repl_gram.y`. [verified-by-code]
(via `knowledge/files/src/backend/replication/repl_gram.y.md`).

### StaticAssertDecl
The compile-time assertion macro (a declaration-context `_Static_assert`
wrapper) used to enforce invariants the compiler can check — struct field
ordering, size relationships, enum bounds — turning a silent miscompile into a
build error. Several load-bearing catalog/PL conventions lack one (a recurring
corpus issue). [from-comment] (via
`knowledge/files/src/pl/plpgsql/src/plpgsql.md`).

### StringInfo
The resizable string/byte buffer (`StringInfoData`: data, len, maxlen, cursor)
used everywhere PostgreSQL builds up text or binary output — error messages,
wire-protocol messages, COPY data. `appendStringInfo*` grow it via `repalloc`;
`cursor` tracks read position when it backs an incoming message. [from-comment]
(via `knowledge/files/src/common/stringinfo.c.md`).

### SubPlan
A planner/executor representation of a sub-SELECT that is evaluated per outer
row (or per comparison) — `SS_process_sublinks` turns a correlated SubLink into
a SubPlan attached to the parent expression tree, with ALL/ANY/EXISTS getting
specialised SubPlan subtypes. Contrast with InitPlan, which runs once.
[from-comment] (via
`knowledge/files/src/backend/optimizer/plan/subselect.c.md`).

### subtransaction (subtrans)
A nested transaction created by a `SAVEPOINT` (or PL exception block) that can
roll back independently of its parent; each gets its own `TransactionId`. The
`pg_subtrans/` SLRU maps a subxid to its parent so visibility checks can walk up
to the top-level xid. [from-comment] (via
`knowledge/files/src/backend/access/transam/subtrans.c.md`).

### SubTransactionId
A backend-local counter identifying a savepoint/subtransaction within the
current top-level transaction (distinct from the XID a subxact may or may not
acquire). Used to scope resource ownership and rollback-to-savepoint.
[from-README] (via
`knowledge/files/src/backend/access/transam/README.md`).

### syscache (system cache)
The indexed front end over catcache: a fixed table of well-known catalog
lookups (`RELOID`, `PROCOID`, `TYPEOID`, …) addressed by an enum, accessed
through `SearchSysCache1..4` and `GetSysCacheOid`. It is the normal way backend
C code reads a single catalog row. [from-comment] (via
`knowledge/files/src/backend/utils/cache/syscache.c.md`).

### TargetEntry
A node in a query or plan's target list: an expression paired with its output
resno, column name, and `resjunk` flag. The plpgsql simple-expression fast path,
for example, peels a plan down to a single `Result` and caches that node's lone
TargetEntry expression. [verified-by-code]
(via `knowledge/files/src/pl/plpgsql/src/pl_exec.md`).

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

### TopMemoryContext
The root of a backend's memory-context tree, living for the whole process
lifetime; it is effectively `malloc`. Almost nothing should allocate here
directly — doing so is a backend-lifetime leak — but it parents the long-lived
caches (`CacheMemoryContext`, etc.). [from-comment] (`memutils.h:52-67` — via
`knowledge/files/src/include/utils/memutils.h.md`).

### TopTransactionContext
The memory context whose lifetime is the current top-level transaction; it is
reset/deleted at commit or abort, making it the natural home for state that must
survive across statements but not across the transaction (e.g. PL subtransaction
bookkeeping lists). [from-comment] (`memutils.h:52-67` — via
`knowledge/files/src/include/utils/memutils.h.md`).

### TransactionId (xid)
A 32-bit transaction identifier stamped into each tuple's xmin/xmax. Special
values include `InvalidTransactionId` (0); the 32-bit space wraps around, so
PostgreSQL also carries a 64-bit `FullTransactionId` to reason about age
without ambiguity. [verified-by-code] (`transam.h:3-4` — via
`knowledge/files/src/include/access/transam.h.md`).

### TransactionIdDidCommit
The transam routine that consults `pg_xact` (CLOG) to decide whether a given
xid committed. Visibility code must call `TransactionIdIsInProgress` (or
`XidInMVCCSnapshot`) *first*: `xact.c` records the commit in CLOG before
clearing `MyProc->xid`, so consulting CLOG too early could make a just-committed
xact look crashed. [from-comment] (`heapam_visibility.c:13-35` — via
`knowledge/files/src/backend/access/heap/heapam_visibility.c.md`).

### TransactionIdIsInProgress
The check (scanning the PGPROC array) for whether an xid is still running.
Visibility code must call it before `TransactionIdDidCommit` (which reads
pg_xact); reversing the order can let a just-committed xact momentarily look
aborted — a documented race-ordering invariant. [from-comment]
(`heapam_visibility.c:13` — via `knowledge/subsystems/access-heap.md`).

### TupleDesc
A tuple descriptor: the runtime description of a row shape — an array of
`Form_pg_attribute` entries (name, type, length, alignment, …) plus optional
constraint/default info — that tells code how to form and deform tuples. It is
reference-counted when cached against a relation. [from-comment] (via
`knowledge/files/src/backend/access/common/tupdesc.c.md`).

### TupleTableSlot
The executor's universal tuple container, abstracting over how a tuple is
physically stored behind a `TupleTableSlotOps` vtable. Four built-in slot kinds
exist — Virtual, HeapTuple, MinimalTuple, and BufferHeapTuple — plus
extension-defined ones, letting every plan node pass tuples uniformly.
[verified-by-code] (via
`knowledge/files/src/include/executor/tuptable.h.md`).

### two-phase commit (2PC)
The protocol behind `PREPARE TRANSACTION` / `COMMIT PREPARED`: a transaction's
state is persisted (in `pg_twophase/` and WAL) so it survives a restart and can
be committed or rolled back later by any backend, enabling external transaction
managers. `twophase.c` manages the GXACT state in shared memory. [from-comment]
(via `knowledge/files/src/backend/access/transam/twophase.c.md`).

### USE_ASSERT_CHECKING
The compile-time symbol enabled by a `--enable-cassert` / cassert build; it
turns on every `Assert()` plus extra invariant checks (node-tag checks, memory
sentinel bytes via `MEMORY_CONTEXT_CHECKING`, randomized free fills). Off in
production builds, so asserts must never have side effects. [verified-by-code]
(`nodes.h:173-183` — via
`knowledge/files/src/backend/nodes/value.c.md`).

### vacuum
The maintenance operation that reclaims space from dead tuples, updates the
free-space and visibility maps, and advances `relfrozenxid` to hold off
transaction-id wraparound. Lazy `VACUUM` runs concurrently with normal access;
`VACUUM FULL` rewrites the table to compact it under an exclusive lock.
[from-comment] (via
`knowledge/files/src/backend/access/heap/vacuumlazy.c.md`).

### Var
The expression node representing a reference to a column: it carries the
range-table index (`varno`) and attribute number (`varattno`) identifying which
relation's which column, resolved during parse analysis. Plan-time rewriting
renumbers Vars (e.g. to `OUTER_VAR`/`INNER_VAR`) as columns flow up the plan
tree. [inferred] (via `knowledge/files/src/include/nodes/primnodes.h.md`).

### visibility map (VM)
A two-bits-per-page relation fork (`VISIBILITYMAP_FORKNUM`) marking pages whose
tuples are all-visible (and optionally all-frozen) to every transaction. It lets
index-only scans skip heap fetches and lets `VACUUM` skip clean pages; the bits
are cleared whenever a page is modified. [from-comment] (via
`knowledge/files/src/backend/access/heap/visibilitymap.c.md`).

### WaitEventSet
A reusable set of wait conditions (sockets, latches, postmaster-death) a
backend blocks on in one `epoll`/`kqueue`/`poll` call, multiplexing client I/O,
inter-process latches, and shutdown detection. Long-lived sets avoid rebuilding
the kernel structure each wait. [verified-by-code] (via
`knowledge/files/src/backend/storage/ipc/waiteventset.c.md`).

### WaitLatch
The convenience wrapper that waits on a single latch (plus optional timeout and
postmaster-death) by building a one-shot `WaitEventSet`. Latches are the
backend's edge-triggered "you have work / wake up" primitive, set with
`SetLatch` from another process or a signal handler. [verified-by-code]
(`waiteventset.c:88` — via `knowledge/subsystems/storage-ipc.md`).

### WAL (xlog)
The write-ahead log: every change is recorded as an XLOG record and flushed to
durable storage *before* the modified data pages are written back, which is
what makes crash recovery possible. `XLogInsertRecord` appends records on the
fast path; `StartupXLOG` replays them during recovery. [from-comment]
(`xlog.c:6-28` — via
`knowledge/files/src/backend/access/transam/xlog.c.md`).

### walreceiver
The standby-side process that connects to a primary's walsender, receives the
streamed WAL, writes and flushes it locally, and reports flush/apply positions
back for synchronous replication. It runs `WalReceiverMain` and hands received
WAL to the startup process for replay. [from-comment] (via
`knowledge/files/src/backend/replication/walreceiver.c.md`).

### walsender
The primary-side backend that streams WAL to a connected standby or
logical-replication client, speaking the replication sub-protocol over a normal
libpq connection. Each connected standby has its own walsender running
`WalSndLoop`; for logical replication it drives the decoding output plugin.
[from-comment] (via `knowledge/files/src/backend/replication/walsender.c.md`).

### XidGenLock
The LWLock that serialises transaction-id assignment and protects the shared
`nextXid` / epoch counters in `ShmemVariableCache`. `GetNewTransactionId`
holds it while bumping the counter and advancing the CLOG/subtrans page
boundaries. [verified-by-code]
(via `knowledge/files/src/backend/access/transam/varsup.c.md`).
