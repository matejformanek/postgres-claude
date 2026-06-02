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

### checkpoint
A point at which all data changes before a given WAL position are guaranteed
flushed to disk, bounding crash-recovery work to the WAL written after the
checkpoint's redo point. A singleton checkpointer aux process (since PG 9.2)
owns all checkpoints — time-driven (`checkpoint_timeout`), WAL-volume-driven,
and shutdown — while `CreateCheckPoint` writes the checkpoint record.
[from-comment] (`checkpointer.c:5-11`, `xlog.c:258` — via
`knowledge/files/src/backend/postmaster/checkpointer.c.md`).

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

### latch
PG's reliable inter-process wakeup primitive, replacing the fragile "sleep
until a signal arrives" pattern. A process blocks in `WaitLatch` /
`WaitEventSetWait` over its own latch plus sockets; another process calls
`SetLatch` to wake it, and `ResetLatch` clears the pending state. The
implementation rides epoll/kqueue/poll under a singleton `WaitEventSet`.
[from-comment] (`latch.c:3-9` — via
`knowledge/files/src/backend/storage/ipc/latch.c.md`).

### MVCC
Multi-Version Concurrency Control: readers never block writers and writers
never block readers because UPDATE/DELETE leave the prior tuple version in
place (stamped with `xmin`/`xmax`) instead of overwriting it. A query's
snapshot decides which versions are visible; superseded versions are later
reclaimed by VACUUM. [from-comment] (`heapam_visibility.c:38-57` — via
`knowledge/architecture/mvcc.md`).

### OID (object identifier)
A 4-byte unsigned integer (`Oid`) that names a catalog object — every relation,
type, function, operator, etc. has one, with `0` reserved as `InvalidOid`. OIDs
are the join key throughout the catalogs; the `ObjectAddress
{classId, objectId, objectSubId}` triple generalizes them into PG's universal
object reference. [verified-by-code] (`catalog/_README:27` — via
`knowledge/files/src/include/catalog/objectaddress.h.md`).

### palloc
Context-aware memory allocation. Memory returned by `palloc` belongs to the
`CurrentMemoryContext` rather than to the caller; it can be freed individually
with `pfree` but is more usually reclaimed in bulk when its context is reset or
deleted. OOM is reported via `ereport`, never a NULL return. [from-comment]
(`palloc.h:1-9,31-52` — via
`knowledge/files/src/include/utils/palloc.h.md`).

### PGPROC
The per-backend shared-memory anchor. Every process that takes locks or runs
transactions (every backend and most aux processes — the syslogger is the
notable exception) has exactly one `PGPROC` entry in the shmem array held by
`PROC_HDR`. It is the join point between the lock manager, the proc array,
LWLock waits, and the wait/wakeup machinery; a backend caches its own as
`MyProc`. [verified-by-code] (via `knowledge/data-structures/pgproc-fields.md`).

### planner
The optimizer stage that turns a `Query` into an executable `Plan` tree.
`planner()` / `standard_planner()` drive `subquery_planner` on the top query,
enumerate and cost candidate Paths, pick the cheapest, and hand it to
`create_plan` to materialize the final plan. [verified-by-code] (via
`knowledge/files/src/backend/optimizer/plan/planner.c.md`).

### postmaster
The supervisor process. It owns the shared-memory and semaphore pools, listens
for connections, and forks a fresh backend on each accept; it deliberately
stays *out* of shared memory so a crashing backend can never corrupt the
supervisor — a load-bearing invariant of the whole process model.
[from-comment] (`postmaster.c:14-23` — via
`knowledge/files/src/backend/postmaster/postmaster.c.md`).

### redo
The replay half of WAL. Each resource manager supplies an `rm_redo` callback
(selected via a record's `xl_rmid`) that re-applies a logged change during
crash recovery; a record whose LSN ≤ the target page's LSN has already been
applied, so its redo is skipped. [from-README] (`transam/README:420-422`;
`RmgrData` in `xlog_internal.h` — via `knowledge/architecture/wal.md`).

### relation
The internal name for any table-like object (table, index, sequence,
materialized view, composite type) — anything with a `pg_class` row and a
relfilenode. The in-memory `RelationData`/`Relation` handle caches a relation's
catalog metadata, tuple descriptor, and access-method routines. [from-README]
(via `knowledge/idioms/catalog-conventions.md`).

### rmgr (resource manager)
A WAL record's owning module. `rmgr.c` builds the global
`RmgrTable[RM_MAX_ID + 1]`, mapping each `RmgrId` to an `RmgrData` struct of
callbacks (name, `rm_redo`, `rm_desc`, …); `RegisterCustomRmgr` lets extensions
add their own. A record's `xl_rmid` field selects which rmgr's redo runs at
replay. [verified-by-code] (`rmgr.c:107`; `RmgrData` in `xlog_internal.h` — via
`knowledge/files/src/backend/access/transam/rmgr.c.md`).

### snapshot
A `SnapshotData` value that captures which tuple versions a query may see. Its
`SnapshotType` selects the visibility regime — the seven types are `MVCC`,
`SELF`, `ANY`, `TOAST`, `DIRTY`, `HISTORIC_MVCC`, and `NON_VACUUMABLE` — and a
single struct is reused across table AMs instead of a per-AM callback.
[from-comment] (`snapshot.h:19-30` — via
`knowledge/files/src/include/utils/snapshot.h.md`).

### spinlock
The lightest lock tier — a bare test-and-set (`slock_t`, via the `SpinLock*`
API) protecting a few instructions' worth of shared data, with no queuing, no
deadlock detection, and a hard rule that code must never error (or block) while
holding one. Used for very short critical sections (e.g. the buffer manager's
packed state word); for anything longer, use an LWLock. [from-comment]
(`atomics.h:25-26`; tier table row 2 — via
`knowledge/idioms/locking-overview.md`).

### tablespace
A named on-disk directory where relation files may live outside the main data
directory. A per-cluster symlink `$PGDATA/pg_tblspc/<spcoid>` points at the
user-supplied location; `pg_tablespace` holds the catalog rows and
`commands/tablespace.c` is the canonical reference for the symlink/path layout.
[from-comment] (`tablespace.c:3-44` — via
`knowledge/files/src/backend/commands/tablespace.c.md`).

### TOAST
"The Oversized-Attribute Storage Technique" — the mechanism that compresses
and/or moves large varlena values out of line. Out-of-line data is split into
fixed-size chunks keyed by `(chunk_id, chunk_seq)` in a side TOAST relation;
`toast_save_datum` writes them and returns a `varatt_external` pointer, while
`toast_delete_datum` removes them. [from-comment]
(`toast_internals.c:1-12,119-375` — via
`knowledge/files/src/backend/access/common/toast_internals.c.md`).

### TransactionId (xid)
A 32-bit transaction identifier stamped into each tuple's xmin/xmax. Special
values include `InvalidTransactionId` (0); the 32-bit space wraps around, so
PostgreSQL also carries a 64-bit `FullTransactionId` to reason about age
without ambiguity. [verified-by-code] (`transam.h:3-4` — via
`knowledge/files/src/include/access/transam.h.md`).

### tuple
A row. On disk a heap tuple is a `HeapTupleHeaderData` header followed by the
user data inside a `BLCKSZ` page, reached through a line pointer (`ItemId`);
the header's `t_infomask`/`t_infomask2` bits encode null-ness, data shape, and
visibility. `htup_details.h` is the single source of truth for the bit-level
layout. [from-comment] (`htup_details.h:3-13` — via
`knowledge/files/src/include/access/htup_details.h.md`).

### TupleDesc
A tuple descriptor — the runtime schema of a row: column count and a
per-column `Form_pg_attribute` array (type/length/typmod), plus optional
constraint info and a reference count. It is ref-counted and wired into the
`ResourceOwner` machinery, so a leaked descriptor surfaces as a warning at
transaction end. [verified-by-code] (`tupdesc.c:49,560,617` — via
`knowledge/files/src/backend/access/common/tupdesc.c.md`).

### TupleTableSlot
The executor's universal tuple container, abstracting over how a tuple is
physically stored behind a `TupleTableSlotOps` vtable. Four built-in slot kinds
exist — Virtual, HeapTuple, MinimalTuple, and BufferHeapTuple — plus
extension-defined ones, letting every plan node pass tuples uniformly.
[verified-by-code] (via
`knowledge/files/src/include/executor/tuptable.h.md`).

### vacuum
The garbage collector that reclaims space from the dead tuple versions MVCC
leaves behind and advances the relation's freeze horizon to prevent xid
wraparound. Lazy (non-blocking) VACUUM runs three phases — prune/freeze the
heap into a dead-TID store, vacuum the indexes against it, then convert
`LP_DEAD` line pointers to `LP_UNUSED` — driven by `heap_vacuum_rel`.
[from-comment] (`vacuumlazy.c:1-100,624` — via
`knowledge/files/src/backend/access/heap/vacuumlazy.c.md`).

### visibility map (VM)
A per-relation fork holding two bits per heap page (`ALL_VISIBLE`,
`ALL_FROZEN`). The bits let VACUUM skip all-frozen pages and let index-only
scans skip the heap fetch when a page is all-visible. The fork is kept
crash-safe via a careful "examine page → pin VM → re-lock" protocol.
[from-comment] (`visibilitymap.c:1-95` — via
`knowledge/files/src/backend/access/heap/visibilitymap.c.md`).

### WAL (xlog)
The write-ahead log: every change is recorded as an XLOG record and flushed to
durable storage *before* the modified data pages are written back, which is
what makes crash recovery possible. `XLogInsertRecord` appends records on the
fast path; `StartupXLOG` replays them during recovery. [from-comment]
(`xlog.c:6-28` — via
`knowledge/files/src/backend/access/transam/xlog.c.md`).

### walsender
The server side of streaming replication: one walsender process per connected
standby (or logical subscriber) reads WAL and streams it over the replication
protocol. For logical replication it also drives decoding through an output
plugin. [from-comment] (`walsender.c:9` — via
`knowledge/files/src/backend/replication/walsender.c.md`).
