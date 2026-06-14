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
### AbortTransaction
The transaction-manager routine that rolls back the current top-level
transaction — releasing locks and buffer pins via resource owners, running
abort callbacks, and discarding the transaction's memory — reached on any
`ERROR` longjmp. [verified-by-code] (via
`knowledge/subsystems/access-transam.md`).



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



### add_path
The optimizer routine that submits a candidate `Path` to a `RelOptInfo`'s
pathlist, immediately pruning it by cost/pathkey/parameterization dominance: a
new path is kept only if nothing already there dominates it, and it evicts any
existing path it dominates. This add-and-prune discipline is what keeps the
path space from exploding during join enumeration. [verified-by-code] (via
`knowledge/files/src/backend/optimizer/util/pathnode.c.md`).



### ALL_FROZEN
The second visibility-map bit: set when every tuple on a heap page is also
frozen, so anti-wraparound VACUUM can skip the page entirely; it implies
`ALL_VISIBLE`. [from-comment] (`visibilitymap.c:1-95` — via
`knowledge/files/src/backend/access/heap/visibilitymap.c.md`).



### ALL_VISIBLE
One of the two visibility-map bits (2 bits per heap page): set when every
tuple on the page is visible to all transactions, letting scans skip
visibility checks and index-only scans avoid heap fetches. [from-comment]
(`visibilitymap.c:1-95` — via
`knowledge/files/src/backend/access/heap/visibilitymap.c.md`).



### AllocateFile
The fd.c stdio wrapper (fopen-style) that registers an open file with the virtual-file-descriptor machinery so the kernel fd can be transiently evicted under pressure; backend code that calls `fopen(3)` directly is buggy because it bypasses VFD eviction. [from-comment] (via `knowledge/files/src/backend/storage/file/fd.c.md`).



### AllocSet
The default `MemoryContext` implementation (`AllocSetContext`). It amortizes
many small `palloc`s by carving them out of a few larger `malloc`'d blocks,
keeps a per-size free list for reuse, and frees every block at once on
`AllocSetReset`/`MemoryContextDelete`. It is the right choice unless a
specialized type (Slab, Generation, Bump) fits the allocation pattern better.
[from-comment] (`aset.c:16-43` — via
`knowledge/files/src/backend/utils/mmgr/aset.c.md`).



### AllocSetContext
The default general-purpose memory-context allocator (the "aset") that manages
power-of-two free lists and grows by malloc'd blocks; it extends
`MemoryContextData` with block and freelist bookkeeping. [verified-by-code]
(`aset.c:158-171` — via `knowledge/files/src/backend/utils/mmgr/aset.c.md`).



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



### appendConnStrVal
Escapes and appends a value into a libpq connection string (wrapping in single
quotes and backslash-escaping as needed); used when generating
`primary_conninfo` and similar conninfo strings. [verified-by-code]
(`recovery_gen.c:68-99` — via
`knowledge/files/src/fe_utils/recovery_gen.c.md`).



### appendShellString
The fe_utils helper that single-quotes a string for safe inclusion in a shell
command line; its hard-coded "safe set" of characters is the security boundary
against shell injection in tools that shell out. [verified-by-code]
(`string_utils.c:600-605` — via
`knowledge/files/src/fe_utils/string_utils.c.md`).



### appendStringInfo
The `printf`-style append to a `StringInfo`: formats its arguments and appends them, growing the buffer as needed; the most common way to build SQL text, deparsed queries, or log lines incrementally. [verified-by-code] (via `knowledge/files/src/common/stringinfo.c.md`).



### appendStringInfoChar
Appends a single character to a `StringInfo`, growing the buffer if full; the cheap per-character primitive used by quoting and escaping loops. [verified-by-code] (via `knowledge/files/src/common/stringinfo.c.md`).



### appendStringInfoString
Appends a NUL-terminated C string to a `StringInfo`, growing the buffer via `enlargeStringInfo` as needed; the workhorse for assembling query text, EXPLAIN output, and format strings without the caller pre-sizing anything. [verified-by-code] (via `knowledge/files/src/backend/libpq/pqformat.c.md`).



### appendStringLiteralConn
Appends a properly escaped SQL string literal to a buffer, choosing the
escaping from a live `PGconn`'s server settings (standard_conforming_strings,
server encoding) so the literal is safe for that exact server. [from-comment]
(`string_utils.c:451-463` — via
`knowledge/files/src/fe_utils/string_utils.c.md`).



### application_name
A session GUC carrying a free-text label identifying the connecting application; it surfaces in `pg_stat_activity`, the `%a` log-line-prefix escape, and CSV logs. Because it is client-settable it can carry user-controlled text into monitoring views — postgres_fdw additionally exposes `postgres_fdw.application_name` with `%a/%u/%d`-style expansion for remote connections. [verified-by-code] (via `knowledge/files/contrib/postgres_fdw/option.c.md`).



### ApplyWalRecord
The xlogrecovery.c routine that, inside the `ReadRecord → ApplyWalRecord` redo loop, dispatches one WAL record to its rmgr's `rm_redo` callback during crash/archive/standby recovery. [verified-by-code] (via `knowledge/subsystems/access-transam.md`).



### archive_command
The GUC holding a shell command the archiver runs to copy each completed WAL
segment to long-term storage; it must return zero only on durable success, and
PostgreSQL retries the same segment until it does. It is the classic (pre-archive-library)
mechanism behind continuous archiving / PITR. [verified-by-code] (via
`knowledge/files/contrib/basic_archive/basic_archive.c.md`).



### ArchiveHandle
The central pg_dump/pg_restore state object representing an open archive plus
its connection and format-specific method pointers (custom, directory, tar,
plain). Restore-time helpers like `ReconnectToServer(AH, dbname)` thread it
through every step. [verified-by-code] (via
`knowledge/files/src/bin/pg_dump/pg_backup_db.c.md`).



### ArrayType
The varlena header struct for a PostgreSQL array value, recording the number of dimensions, a null-bitmap-present flag, the element type OID, and the per-dimension bounds, followed by the packed element data. Array code must round element offsets to the element type's alignment, and in-place mutation (e.g. `intarray`'s element delete) compacts within the existing allocation. [verified-by-code] (via `knowledge/files/contrib/intarray/_int_op.md`).



### AsyncRequest
The per-subplan request/response struct the executor's asynchronous-execution
machinery passes between a parent (e.g. Append) and an async-capable child such
as a foreign scan: it carries the requestor, requestee, a callback slot, and a
`request_complete` flag. `ExecAsyncRequest`/`ExecAsyncNotify`/`ExecAsyncResponse`
drive it so multiple foreign scans can have I/O in flight at once.
[verified-by-code] (via `knowledge/files/src/include/executor/execAsync.md`).



### AttrNumber
The 16-bit signed integer type naming a column position within a relation
(1-based for user columns; system columns like `ctid` use negative numbers, and
0/`InvalidAttrNumber` means "no column"). It appears throughout the parser and
executor, e.g. `get_rte_attribute_name(RangeTblEntry *, AttrNumber)`.
[verified-by-code] (via `knowledge/files/src/include/parser/parsetree.h.md`).



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



### backend_startup
The early connection-establishment phase in a freshly forked backend that reads
the startup packet, negotiates protocol version and SSL/GSS encryption, applies
startup GUCs, and authenticates before `InitPostgres` runs. The `ProcessStartupPacket`
path here is exposed to unauthenticated input, so it is a hardened trust
boundary. [verified-by-code] (via
`knowledge/files/src/include/tcop/backend_startup.h.md`).



### BackendInitialize
The early phase of a forked backend's startup (within `BackendMain`) that
reads the client's startup packet and performs authentication before the
backend enters its command loop. [verified-by-code] (`backend_startup.c:76` —
via `knowledge/files/src/backend/postmaster/postmaster.c.md`).



### BackendMain
The entry point of a freshly forked client backend; it runs
`BackendInitialize` (read the startup packet, set up signals) and then enters
the `PostgresMain` command loop. [verified-by-code] (`backend_startup.c:76` —
via `knowledge/files/src/backend/tcop/postgres.c.md`).



### BackendStartup
The postmaster routine that handles a newly arrived connection by forking a
child process to become the client backend. [verified-by-code]
(`postmaster.c:3576` — via `knowledge/architecture/query-lifecycle.md`).



### BackendType
The enum classifying each PostgreSQL process (client backend, autovacuum
worker, walwriter, checkpointer, background worker, …); it drives
process-title and statistics reporting. [verified-by-code]
(`miscadmin.h:340-381` — via `knowledge/architecture/process-model.md`).



### BackgroundWorker
The registration struct an extension fills in (name, library/function entry
point, restart policy, flags for shmem/DB access) and hands to
`RegisterBackgroundWorker` (static, at load) or `RegisterDynamicBackgroundWorker`
(runtime) so the postmaster forks and manages a long-lived helper process.
[verified-by-code] (`bgworker.c:658` — via
`knowledge/files/src/backend/postmaster/bgworker.c.md`).



### BackgroundWorkerInitializeConnection
The bgworker.c entry that attaches a registered background worker to a specific database and role, running the same `InitPostgres` path a normal backend uses (so `MyProc` must already exist). [verified-by-code] (via `knowledge/files/src/backend/utils/init/postinit.c.md`).



### backup_label
A small text file written into the data directory at the start of a non-exclusive base backup; it records the start WAL location, the checkpoint redo point, and the backup method so recovery knows where to begin replaying WAL. Its contents are produced by `build_backup_content`. [verified-by-code] (via `knowledge/files/src/backend/access/transam/xlogfuncs.c.md`).



### backup_manifest
A JSON file emitted alongside a base backup listing every file with its size, modification time, and checksum, plus the WAL range needed to restore; `pg_verifybackup` later replays it to detect corruption, truncation, or missing files. [from-comment] (via `knowledge/files/contrib/basebackup_to_shell/basebackup_to_shell.c.md`).



### BAS_BULKREAD
The BufferAccessStrategy ring type used for large sequential reads
(seqscans, ANALYZE, `COPY ... TO`): a small fixed ring of shared buffers is
reused so one big scan can't evict the entire buffer pool.
[verified-by-code] (via `knowledge/subsystems/storage-buffer.md`).



### BASE_BACKUP
The replication-protocol command (used by `pg_basebackup`) that asks a walsender
to stream a full copy of the data directory as a tar/plain archive, with options
for WAL inclusion, checkpoint mode, tablespace mapping, and progress reporting.
[verified-by-code] (via
`knowledge/files/src/backend/replication/repl_gram.y.md`).



### be_fsstubs
The backend SQL-callable wrappers (`lo_import`, `lo_export`, `lo_open`,
`loread`, `lowrite`, …) implementing the large-object interface over the
inversion-FS routines; `lo_import`/`lo_export` read and write server-side files
and are therefore restricted to superusers / `pg_read_server_files` roles.
[verified-by-code] (via
`knowledge/files/src/backend/libpq/be-fsstubs.c.md`).



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



### BitmapAnd
The executor node (`nodeBitmapAnd.c`) that intersects the TID bitmaps produced by several BitmapIndexScan children before a single BitmapHeapScan fetches the surviving heap tuples. [verified-by-code] (via `knowledge/files/src/backend/executor/nodeBitmapAnd.c.md`).



### BitmapHeapScan
The plan/executor node that consumes a TID bitmap built by one or more
BitmapIndexScan children and fetches the matching heap tuples in physical block
order, which turns scattered index hits into mostly-sequential heap I/O.
`ExecInitBitmapHeapScan` wires it up; it supports lossy bitmap pages by
rechecking the qual on every tuple of a lossy block.
[verified-by-code] (via `knowledge/files/src/include/executor/nodeBitmapHeapscan.md`).



### BitmapIndexScan
The executor node by which an index AM returns a bitmap of matching TIDs
rather than tuples one at a time; a `BitmapHeapScan` above it then fetches
the heap pages in physical order, and several such bitmaps can be AND/ORed.
[verified-by-code] (via `knowledge/subsystems/executor.md`).



### Bitmapset
A compact variable-length set of small non-negative integers (a `Bitmapset`),
used throughout the planner and parser for things like sets of relids,
attribute numbers, and required-outer relations. Operations
(`bms_add_member`, `bms_is_member`, `bms_union`, …) treat it as an immutable-ish
value and may reallocate. [from-comment] (via
`knowledge/files/src/backend/nodes/bitmapset.c.md`).



### BKI_ARRAY_DEFAULT
A `genbki` annotation in a catalog header that supplies the default value
for an array-typed column in bootstrap (`.bki`) data, so hand-written `.dat`
rows can omit it. [from-comment] (via
`knowledge/files/src/include/catalog/pg_type.h.md`).



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



### BKI_LOOKUP_OPT
A BKI annotation macro on a catalog column declaring that the column holds an OID referencing another catalog, so genbki.pl resolves symbolic names to OIDs at bootstrap-emit time; the `_OPT` variant additionally allows the column to be zero (no reference). [from-comment] (via `knowledge/files/src/backend/catalog/_generators.md`).



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



### BLCKSZ
The compile-time database block (page) size, 8192 bytes by default; nearly every on-disk structure — heap and index pages, free-space sizing, TOAST chunking, WAL page alignment — is expressed in multiples or fractions of it. [verified-by-code] (via `knowledge/subsystems/storage-buffer.md`).



### BlessTupleDesc
Registers a transient (non-catalog) `TupleDesc` with the typcache so its row type gains a valid composite-type identity; required before returning composite/record Datums or building tuples in a set-returning function. [verified-by-code] (via `knowledge/files/contrib/sslinfo/sslinfo.c.md`).



### blkreftable
The block-reference table used by incremental backup: it records, per relation
fork, which blocks changed since a prior backup (derived from WAL summaries) so
`pg_basebackup --incremental` and `pg_combinebackup` can copy only modified
blocks. Serialized into the backup manifest. [verified-by-code] (via
`knowledge/files/src/include/common/blkreftable.h.md`).



### BlockIdSet
Inline helper that packs a 32-bit `BlockNumber` into the split hi/lo 16-bit `BlockIdData` representation stored inside an `ItemPointer`; paired with `BlockIdGetBlockNumber` for the reverse. [verified-by-code] (via `knowledge/files/src/include/storage/block.h.md`).



### BlockNumber
A `uint32` identifying a page within a single relation fork; block 0 is the
first 8 KB page. `InvalidBlockNumber` (0xFFFFFFFF) is the sentinel "no block",
which caps a fork at just under 2^32 pages. Combined with an `OffsetNumber`
it forms an `ItemPointer`/TID. [verified-by-code] (`block.h:31` — via
`knowledge/files/src/bin/pg_rewind/datapagemap.h.md`).



### BM_DIRTY
The buffer state flag marking that the page has been modified since it was
read in and must be written back before the buffer can be reused.
[verified-by-code] (`buf_internals.h:106-127` — via
`knowledge/subsystems/storage-buffer.md`).



### BM_IO_ERROR
The buffer state flag set when an in-progress I/O failed; it is cleared
together with `BM_IO_IN_PROGRESS` when the I/O completes
(`TerminateBufferIO`), signalling waiters that the operation did not succeed.
[verified-by-code] (`bufmgr.c:7366-7413` — via
`knowledge/files/src/backend/storage/buffer/bufmgr.c.md`).



### BM_IO_IN_PROGRESS
The buffer state flag indicating a read or write I/O is underway on the
buffer; other backends wanting the page wait on the buffer's I/O condition
variable until the flag clears. [verified-by-code] (`bufmgr.c:7366-7413` — via
`knowledge/files/src/backend/storage/buffer/bufmgr.c.md`).



### BM_LOCKED
The buffer-descriptor state-word flag bit that spinlock-protects the rest of
the packed atomic state; `LockBufHdr`/`UnlockBufHdr` set and clear it around
any non-atomic update of the refcount/usagecount/flags word.
[verified-by-code] (via `knowledge/subsystems/storage-buffer.md`).



### BM_PIN_COUNT_WAITER
The buffer state flag recording that a backend is waiting for the buffer's pin
count to drop to one (a "superexclusive" lock used e.g. by VACUUM); only one
such waiter is allowed at a time. [verified-by-code] (via
`knowledge/subsystems/storage-buffer.md`).



### bms_add_member
Adds an integer to a `Bitmapset`, reallocating the word array if the bit index exceeds the current allocation and returning the (possibly moved) set; the canonical way to accumulate a set of attnums, relids, or param ids. [verified-by-code] (via `knowledge/files/src/backend/nodes/multibitmapset.c.md`).



### bms_is_member
Tests whether an integer is present in a `Bitmapset` — the "is this attribute/relid in the set?" primitive. Attribute callers offset by `FirstLowInvalidHeapAttributeNumber` so system columns map to non-negative bit positions. [verified-by-code] (via `knowledge/files/contrib/lo/lo.c.md`).



### BRIN
Block Range INdex — an index access method that stores a compact summary (typically min/max) per range of consecutive heap blocks instead of one entry per tuple, trading precision for tiny size on naturally-clustered columns. A scan consults each range's summary and re-checks only the blocks whose range cannot be ruled out. [from-README] (`brin.c:300` — via `knowledge/files/src/backend/access/brin/README.md`).



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



### BUFFER_LOCK_SHARE
The mode argument to `LockBuffer` for taking a shared content lock on a
buffer — multiple readers may hold it concurrently but no writer can — as
opposed to `BUFFER_LOCK_EXCLUSIVE`. [from-comment] (via
`knowledge/subsystems/contrib-pgrowlocks.md`).



### BufferAlloc
The buffer-manager core that, given a page identity, either returns the
already-resident buffer or selects a victim via the clock-sweep, evicting and
remapping it; the heart of `ReadBuffer`'s lookup path. [verified-by-code]
(`bufmgr.c:2197-2351` — via
`knowledge/files/src/backend/storage/buffer/bufmgr.c.md`).



### BufferDesc
The shared-memory descriptor for one buffer-pool slot: it holds the buffer
tag, a packed atomic `state` word (refcount + usagecount + flag bits), and the
content/IO lock machinery. `LockBufHdr` spins on the state word to get a
consistent view; the actual page bytes live in a separate buffer-blocks array.
[verified-by-code] (`bufmgr.c:7527` — via
`knowledge/files/src/include/storage/buf_internals.h.md`).



### BufferGetPage
Inline accessor returning the `Page` (8 KB block image) backing a pinned buffer; the bridge from the buffer-manager handle to the page-layout API (`PageGetItem`, `PageGetMaxOffsetNumber`, …). [verified-by-code] (via `knowledge/files/src/include/storage/bufmgr.h.md`).



### BufferIsLocal
The macro that tests whether a `Buffer` handle refers to a backend-local
buffer (temp-table buffer, negative buffer number) rather than a shared-buffer-
pool buffer. Shared-pool routines such as `MarkBufferDirty` assert
`!BufferIsLocal(buffer)` so local buffers take the separate `localbuf.c` path.
[verified-by-code] (`bufmgr.c:7533-7565` — via
`knowledge/files/src/backend/storage/buffer/bufmgr.c.md`).



### BufferTag
The `(relfilelocator, forknum, blocknum)` key identifying which on-disk
block a shared buffer currently holds; it is hashed through the partitioned
buffer-mapping table to locate the owning buffer. [verified-by-code] (via
`knowledge/subsystems/storage-buffer.md`).



### BufferUsage
The instrumentation counter struct (`instrument.c`) accumulating shared/local buffer hits, reads, dirtied and written during execution (and optionally planning); surfaced by `EXPLAIN (BUFFERS)` and accumulated per-statement by pg_stat_statements. [verified-by-code] (via `knowledge/files/contrib/pg_stat_statements/pg_stat_statements.c.md`).



### BufFile
A buffered, segmented temporary-file abstraction that transparently spans the
1 GB per-segment limit and is tracked for cleanup at transaction or query end.
The executor uses `BufFile`s to spill data that exceeds `work_mem` — e.g. the
per-batch outer/inner files of a multi-batch hash join. [from-comment] (via
`knowledge/files/src/backend/executor/nodeHashjoin.c.md`).



### buildACLCommands
The pg_dump/dumputils helper that, given an object's current and baseline
ACLs, emits the GRANT/REVOKE statement sequence needed to recreate its
privileges. [verified-by-code] (via
`knowledge/files/src/bin/pg_dump/dumputils.h.md`).



### BuildTupleFromCStrings
Constructs a `HeapTuple` from an array of C strings by running each column's type input function against an `AttInMetadata`; the convenient (if allocation-heavy) row builder for set-returning functions returning text-shaped data. [verified-by-code] (via `knowledge/files/contrib/pgrowlocks/pgrowlocks.c.md`).



### bulk_write
The smgr-level facility for populating a brand-new relation fork in bulk (CREATE INDEX, REINDEX, CLUSTER, table rewrites) while bypassing the shared buffer manager, avoiding buffer-lock and partition-lock contention. It buffers pages and writes them out in batches, WAL-logging as needed, then fsyncs the fork at the end. [verified-by-code] (via `knowledge/files/src/backend/storage/smgr/bulk_write.c.md`).



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



### CacheInvalidateHeapTuple
The catalog-DML entry point that registers the invalidation messages implied
by inserting/updating/deleting a catalog tuple, so that dependent relcache and
syscache entries get flushed at commit. [verified-by-code] (`inval.c:1568` —
via `knowledge/files/src/backend/utils/cache/inval.c.md`).



### CacheMemoryContext
The long-lived `MemoryContext` (a child of `TopMemoryContext`) that holds
relcache, catcache, and plan-cache entries for the life of the backend.
Allocations placed here are deliberately never freed per-query, so leaking into
it is a true backend-lifetime leak. [from-comment] (`memutils.h:52-67` — via
`knowledge/files/src/include/utils/memutils.h.md`).



### canonicalize_path
Normalises a filesystem path in place, collapsing `.`/`..` segments and redundant separators; used by frontend tools and by server functions such as `genfile.c` before path-safety checks. [verified-by-code] (via `knowledge/files/src/backend/utils/adt/genfile.c.md`).



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



### catalog_xmin
The oldest transaction id whose catalog rows a logical replication slot still
needs; the `ProcArray`/`GetOldestSafeDecodingTransactionId` machinery holds the
global catalog horizon back to it so vacuum does not remove catalog tuples a
slot might still decode. Distinct from a slot's data `xmin`. [verified-by-code]
(via `knowledge/files/src/backend/storage/ipc/procarray.c.md`).



### CatalogSnapshot
A cached MVCC snapshot used specifically for catalog scans, pseudo-registered by snapmgr.c and refreshed when invalidation messages arrive, so catalog reads see the latest committed catalog state without taking a fresh snapshot on every lookup. [verified-by-code] (via `knowledge/data-structures/snapshot-lifecycle.md`).



### CatalogTupleDelete
Deletes one catalog row by TID via `simple_heap_delete`; no index maintenance is needed because the dead heap line pointer makes the matching index entries unreachable. The delete counterpart of `CatalogTupleInsert`. [verified-by-code] (via `knowledge/files/src/backend/catalog/indexing.c.md`).



### CatalogTupleInsert
The universal "write one new row into a system catalog" helper: opens the relation's indexes, does `simple_heap_insert`, runs `CatalogIndexInsert` to add matching index entries, then closes the indexes. [verified-by-code] (via `knowledge/files/src/backend/catalog/indexing.c.md`).



### CatalogTupleUpdate
Updates a catalog row via `simple_heap_update` and inserts fresh index entries through `CatalogIndexInsert`; the old index entry is reclaimed with the dead tuple, since at the heap level an update is a delete+insert. [verified-by-code] (via `knowledge/files/src/backend/catalog/indexing.c.md`).



### CatCache
A single catalog cache: it indexes one system catalog by one specific N-tuple of key columns (1 ≤ N ≤ `CATCACHE_MAXKEYS = 4`), holding `HeapTuple` copies in hash buckets and supporting negative entries that mark "no row matches this key". It is the substrate beneath syscache and lsyscache. [verified-by-code] (`catcache.h:35` — via `knowledge/subsystems/utils-cache.md`).



### catcache (catalog cache)
The per-backend cache of individual system-catalog rows keyed by lookup key
(e.g. a `pg_proc` row by OID), backing the `SearchSysCache` API. Entries are
negative-cacheable and invalidated by shared-invalidation messages when another
backend changes the underlying catalog. [from-comment] (via
`knowledge/files/src/backend/utils/cache/catcache.c.md`).



### CatCacheInvalidate
The catcache.c routine (callable only from inval.c) that flushes the cached entries matching an invalidated tuple's keys; part of the catalog-cache coherence machinery driven by shared-invalidation messages. [verified-by-code] (`catcache.c:643` — via `knowledge/files/src/backend/utils/cache/catcache.c.md`).



### CatCList
A cached *list* of `CatCTup`s answering a non-unique-key catcache query (e.g. all pg_amop rows for an opfamily); it transitively pins its member tuples for the list's lifetime. [verified-by-code] (via `knowledge/subsystems/utils-cache.md`).



### CatCTup
One cached catalog row inside a `CatCache`: a positive entry wrapping a `HeapTuple` copy, or a key-only negative entry marking "row absent". Allocated as a single chunk so the tuple body is contiguous with its header. [verified-by-code] (via `knowledge/files/src/backend/utils/cache/catcache.c.md`).



### CHECK_FOR_INTERRUPTS
The macro every long-running loop must call so a backend can act on a pending
cancel, terminate, or recovery-conflict signal at a safe point rather than
mid-critical-section. It expands to a cheap flag test that, when set, longjmps
out via `ProcessInterrupts`. Omitting it from a tight loop makes that loop
un-cancellable. [verified-by-code] (`pl_exec.c:2026` — via
`knowledge/files/src/pl/plpgsql/src/pl_exec.md`).



### check_stack_depth
The recursion guard called at the top of every deeply-recursive backend routine; it compares the current stack pointer against `max_stack_depth` and `ereport(ERROR)`s before a runaway recursion can overflow the C stack and crash the backend. Recursive expression/parse-tree walkers and user-facing recursive functions (e.g. ltree, intarray bool-expression parsers) must call it on each level. [verified-by-code] (via `knowledge/files/contrib/intarray/_int_bool.md`).



### CheckDeadLock
The deadlock detector entry point, invoked from `ProcSleep` after the
deadlock-timeout fires. It walks the lock wait-for graph looking for a cycle and,
if found, either rearranges wait queues to resolve a soft edge or signals the
current process to abort. [verified-by-code] (`proc.c:1856` — via
`knowledge/files/src/backend/storage/lmgr/proc.c.md`).



### CheckFunctionValidatorAccess
The permission gate a PL validator (`plpgsql_validator`, `plperl_validator`,
…) calls before inspecting a function body: it confirms the current user may
validate the target function/language, and the validator returns `VOID`
silently if access is denied. This keeps `CREATE FUNCTION`-time body checks from
leaking information to unprivileged callers. [verified-by-code]
(`pl_handler.c:441` — via `knowledge/files/src/pl/plpgsql/src/pl_handler.md`).



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



### client_encoding
The session GUC naming the character-set encoding of data exchanged with the client; the backend transcodes between it and the database (server) encoding on input and output. Functions that synthesize text (e.g. pgcrypto decrypt) must produce bytes valid in the client encoding or risk encoding-violation errors at send time. [verified-by-code] (via `knowledge/files/contrib/pgcrypto/pgp-pgsql.md`).



### ClientAuthentication
The backend routine that runs the configured authentication method (matched
from `pg_hba.conf` via the parsed `HbaLine` rules) against a newly connected
client, before the session is allowed to proceed. It is the chokepoint every
connection passes through during backend startup. [verified-by-code]
(via `knowledge/files/src/backend/tcop/backend_startup.c.md`).



### ClientSignature
In SCRAM authentication, the HMAC of the stored key over the auth message
(`HMAC(StoredKey, AuthMessage)`); XOR-ing it with the `ClientProof` the client
sent recovers a candidate `ClientKey`, whose hash the server compares to the
stored key. This is how the server verifies the client knew the password without
ever storing it. [verified-by-code] (`auth-scram.c:1147` — via
`knowledge/files/src/backend/libpq/auth-scram.c.md`).



### clog (CLOG / pg_xact)
The commit-log SLRU that stores two status bits per transaction (in-progress /
committed / aborted / sub-committed), consulted by visibility checks to resolve
whether a tuple's xmin/xmax committed. It lives under `pg_xact/` and is driven
through `TransactionIdSetTreeStatus` / `TransactionIdGetStatus`. [from-comment]
(via `knowledge/files/src/backend/access/transam/clog.c.md`).



### CommandComplete
The wire-protocol message the backend sends after a SQL command finishes,
carrying the command tag (e.g. `INSERT 0 5`, `SELECT 12`). The tag and its
optional row count come from `cmdtaglist.h`; the row-count flag is wire-
significant, so flipping it for an existing tag breaks libpq clients that parse
the tag. [verified-by-code] (via
`knowledge/files/src/include/tcop/cmdtaglist.h.md`).



### CommandCounterIncrement
Advances the backend's command counter within a transaction so rows written by an earlier command become visible to later commands in the same transaction; it also flushes pending invalidation messages. Routinely called between the catalog-modifying steps of DDL. [verified-by-code] (`inval.c:1` — via `knowledge/files/src/backend/utils/cache/inval.c.md`).



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



### CommandTag
The enum identifying each SQL command kind (SELECT, INSERT, CREATE TABLE, …);
`cmdtag.c` holds its static metadata table and `GetCommandTagName` maps it to
the user-visible command-completion string. [verified-by-code] (`cmdtag.c:9` —
via `knowledge/files/src/backend/tcop/cmdtag.c.md`).



### commit timestamp (commit_ts)
An optional SLRU (`pg_commit_ts/`) that records the wall-clock commit time and
origin of each transaction when `track_commit_timestamp` is on, queryable via
`pg_xact_commit_timestamp`. It is primarily used by conflict detection in
logical replication. [from-comment] (via
`knowledge/files/src/backend/access/transam/commit_ts.c.md`).



### commit_ts
The SLRU-backed subsystem that stores, per committed transaction, its commit timestamp and originating `ReplOriginId`; active only when `track_commit_timestamp` is on. It is the backing store for `pg_xact_commit_timestamp()` and feeds last-update-wins conflict resolution in logical replication. [verified-by-code] (`commit_ts.c` — via `knowledge/files/src/backend/access/transam/commit_ts.c.md`).



### CommitTransaction
The xact.c routine that performs a top-level transaction commit: it fires
pre-commit callbacks, processes pending relation-file deletes via
`smgrDoPendingDeletes`, writes and flushes the commit WAL record
(`RecordTransactionCommit`), releases locks, and advances the proc's state. The
abort counterpart is `AbortTransaction`. [verified-by-code]
(`storage.c:673-735` — via
`knowledge/files/src/backend/catalog/storage.c.md`).



### CompactAttribute
The slimmed-down, cache-hot per-column descriptor cached in parallel with each `Form_pg_attribute` inside a `TupleDesc`; it is repopulated by `TupleDescFinalize` after manual descriptor edits so the deform hot path avoids touching the full catalog form. [verified-by-code] (via `knowledge/files/src/backend/access/common/tupdesc.c.md`).



### CompareType
A small backend-wide enum of named comparison semantics
(`COMPARE_LT`/`LE`/`EQ`/`GE`/`GT`/`NE`) decoupled from any one access method's
strategy numbers. It lets generic code request "the less-than operator" without
hardcoding btree strategy 1, and AMs translate `CompareType` to and from their
own strategy numbers. [verified-by-code] (via
`knowledge/files/src/include/access/cmptype.h.md`).



### CompressFileHandle
pg_dump's abstraction over a possibly-compressed output file — a vtable of read/write/getc/gets/close ops so the archiver code is agnostic to whether the underlying stream is plain, gzip, lz4, or zstd. [verified-by-code] (via `knowledge/files/src/bin/pg_dump/pg_backup_directory.c.md`).



### ComputeXidHorizons
The procarray routine that scans live backends to compute the cluster's xid horizons (oldest xmin etc.) used to decide which dead tuples are removable; corrupting the xid order would break it. [from-README] (`transam/README:272-285` — via `knowledge/files/src/backend/access/transam/README.md`).



### condition_variable
A PostgreSQL synchronization primitive letting one process sleep until another signals a condition, without busy-waiting; built on the process latch with a wait-queue of `proclist` entries. The idiom is `ConditionVariablePrepareToSleep` / loop-checking the condition / `ConditionVariableSleep` / `ConditionVariableCancelSleep`, woken by `ConditionVariableSignal` or `Broadcast`. [from-comment] (via `knowledge/files/src/backend/storage/lmgr/condition_variable.c.md`).



### ConditionalLockBuffer
The non-blocking variant of `LockBuffer`: it tries to take the buffer content
lock and returns false immediately if it can't, instead of waiting. Used where a
backend must not block on a busy page — e.g. opportunistic pruning or a scan
that prefers to skip a contended page. [verified-by-code]
(`bufmgr.c:6567-6910` — via
`knowledge/files/src/backend/storage/buffer/bufmgr.c.md`).



### ConditionVariable
A sleep/wake primitive: a spinlock-protected `proclist` of waiting PGPROCs where one backend sleeps until another `Signal`s or `Broadcast`s it, each waiter being woken via `SetLatch(MyLatch)`. `ConditionVariablePrepareToSleep` enqueues before the condition re-test to avoid a lost wakeup. [verified-by-code] (`condition_variable.c:37` — via `knowledge/files/src/backend/storage/lmgr/condition_variable.c.md`).



### ConditionVariableBroadcast
Wakes every backend sleeping on a condition variable; the broadcast counterpart of `ConditionVariableSignal`, used after a state change that all waiters need to re-check (e.g. a slot becoming available). [verified-by-code] (`condition_variable.c:284` — via `knowledge/files/src/backend/storage/lmgr/condition_variable.c.md`).



### ConditionVariableSleep
The blocking primitive of the condition-variable API: after
`ConditionVariablePrepareToSleep`, a backend calls `ConditionVariableSleep(cv,
wait_event)` to sleep until another backend `ConditionVariableSignal`/`Broadcast`s
the variable. It is the latch-backed, interruptible way to wait on a shared-state
predicate without a busy spin. [verified-by-code] (`condition_variable.c:98` —
via `knowledge/files/src/backend/storage/lmgr/condition_variable.c.md`).



### construct_array
Builds a one-dimensional PostgreSQL array Datum from a C array of element Datums plus the element type's length/byval/alignment; the standard array constructor, with `construct_md_array` for multi-dim. [verified-by-code] (`arrayfuncs.c:3367` — via `knowledge/files/src/backend/utils/adt/arrayfuncs.c.md`).



### ControlFileData
The fixed-layout struct serialised into `pg_control` describing cluster-wide
state (system identifier, latest checkpoint location, catalog/control
versions); it is read and written as a single ~8 KiB block guarded by a CRC.
[verified-by-code] (`controldata_utils.c:68-178` — via
`knowledge/files/src/common/controldata_utils.c.md`).



### CopyData
The protocol message that carries a chunk of COPY payload in either direction
during COPY IN/OUT. It is one of the few message types libpq lets exceed the
30 KB "huge message" guard (`VALID_LONG_MESSAGE_TYPE`), because bulk data
legitimately runs large. [verified-by-code] (via
`knowledge/files/src/interfaces/libpq/fe-protocol3.c.md`).



### copyObject
Deep-copies an arbitrary `Node` tree by dispatching on `nodeTag`; the generated `copyfuncs.c` supplies a per-node-type copier so parser/planner trees can be cloned without manual field walking. [verified-by-code] (via `knowledge/files/src/backend/nodes/copyfuncs.c.md`).



### CreateCheckPoint
The function (driven by the checkpointer) that performs a checkpoint —
flushing dirty buffers, writing a checkpoint WAL record, and updating
`pg_control`'s redo pointer so recovery can restart from there.
[verified-by-code] (via
`knowledge/files/src/backend/access/transam/xlog.c.md`).



### CreateSharedMemoryAndSemaphores
The ipci.c routine run at postmaster startup that sizes and lays out the main shared-memory segment by calling each subsystem's `XxxShmemInit`, then creates the semaphores. [verified-by-code] (via `knowledge/subsystems/storage-ipc.md`).



### CritSectionCount
The per-backend critical-section nesting depth; while it is `> 0`, `errstart` promotes any ERROR to PANIC, because failing partway through a WAL-logged shared-memory mutation must take down the server rather than leave it inconsistent. [verified-by-code] (`elog.c:372` — via `knowledge/files/src/backend/utils/error/elog.c.md`).



### cryptohash
The unified cryptographic-hash abstraction (`pg_cryptohash_create`/`_update`/
`_final`) that dispatches to OpenSSL when built `--with-ssl`, or to in-tree
fallback implementations otherwise, giving the same MD5/SHA-1/SHA-2 API to both
backend and frontend code. [verified-by-code] (via
`knowledge/files/src/include/common/cryptohash.h.md`).



### CStringGetTextDatum
Macro that turns a NUL-terminated C string into a `text` Datum (palloc'ing a varlena copy); the usual way to hand a C string back to SQL as `text`. Its inverse is `text_to_cstring`. [verified-by-code] (via `knowledge/files/contrib/spi/autoinc.c.md`).



### CurrentMemoryContext
The global that names the context where a bare `palloc` allocates. Code sets
it with the inline `MemoryContextSwitchTo(new)`, which returns the previous
context so callers can restore it; forgetting to restore is a classic source of
allocations landing in the wrong context. [verified-by-code] (via
`knowledge/idioms/memory-contexts.md`).



### CurrentResourceOwner
The global pointing at the resource owner that newly-acquired resources
(buffer pins, locks, tuplestore handles, catcache refs) are charged to, so
they can be released en masse when the owner ends. [verified-by-code] (via
`knowledge/files/src/pl/plpgsql/src/pl_exec.md`).



### CurTransactionContext
The per-transaction memory context whose lifetime matches the current
(sub)transaction; allocations there live until that transaction commits or
aborts, distinct from the per-query and per-tuple contexts. [from-comment]
(via `knowledge/files/src/pl/plpgsql/src/pl_exec.md`).



### CustomScan
A plan-node type that lets an extension inject its own executor node into a plan tree via registered callback method tables (CustomScanMethods / CustomExecMethods), enabling custom scan or join strategies without patching the core executor. [verified-by-code] (`nodes/plannodes.h:932` — via `knowledge/files/src/backend/nodes/extensible.c.md`).



### data_directory_mode
The permission mask (`PG_DIR_MODE_OWNER`, 0700) the server applies to the data directory, relaxed to group-read when group access is enabled at initdb; part of the cluster's single file-permission boundary. [verified-by-code] (via `knowledge/files/src/backend/utils/init/globals.c.md`).



### DataDir
The global C string holding the absolute path of the running cluster's data
directory (`PGDATA`), set during postmaster startup. Security-sensitive
SQL-callable file functions like `pg_read_file` confine their argument to paths
under `DataDir`, `Log_directory`, and a few allowed roots.
[verified-by-code] (via `knowledge/files/src/backend/utils/adt/genfile.c.md`).



### DataRow
The wire-protocol message carrying one result row's column values, emitted by
the `printtup` DestReceiver after a `RowDescription`. Both the networked backend
and the `--single` standalone backend funnel result tuples through `printtup`,
which formats each as a `DataRow`. [verified-by-code] (via
`knowledge/files/src/backend/access/common/printtup.c.md`).



### Datum
The generic pointer-width value type that carries any SQL datum through the
executor and fmgr layer: pass-by-value types are stored inline, pass-by-
reference types as pointers into memory. Conversion macros (`Int32GetDatum`,
`DatumGetPointer`, …) move concrete C values in and out. [inferred] (via
`knowledge/idioms/fmgr.md`).



### DatumGetInt32
Macro extracting a 32-bit signed integer from a `Datum`; one of the `DatumGet*`/`*GetDatum` conversion family in `postgres.h` that mediates between the generic Datum representation and concrete C types. [verified-by-code] (via `knowledge/files/src/include/postgres.h.md`).



### DatumGetPointer
The inverse of `PointerGetDatum`: it reinterprets a `Datum` that carries a
by-reference value as a `char *` so the callee can dereference it. By-reference
types (text, arrays, composites) are always passed as a pointer disguised in a
`Datum`, so fmgr-level code unwraps them with `DatumGetPointer` (or a
type-specific `DatumGet*` wrapper). [verified-by-code] (via
`knowledge/files/src/include/postgres.h.md`).



### deadlock detector
The lock-manager component that, on `deadlock_timeout` expiring while a backend
waits for a heavyweight lock, builds the wait-for graph and looks for a cycle.
A hard cycle aborts the youngest waiter with a deadlock error; soft edges let
it re-order the wait queue instead. [from-comment] (via
`knowledge/files/src/backend/storage/lmgr/deadlock.c.md`).



### DeadLockCheck
The deadlock-detector entry (`deadlock.c:220`, called from `CheckDeadLock` in proc.c with all lock-partition LWLocks held) that walks the wait-for graph and returns a `DeadLockState`, optionally rearranging wait queues to break a soft deadlock. [verified-by-code] (`deadlock.c:220` — via `knowledge/files/src/backend/storage/lmgr/deadlock.c.md`).



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



### deconstruct_array
Explodes an array Datum into a C array of element Datums and null flags given the element type's properties; the read-side counterpart of `construct_array`. [verified-by-code] (via `knowledge/files/src/backend/utils/adt/array_userfuncs.c.md`).



### DEFAULT_COLLATION_OID
The OID of the database's default collation, passed to collation-aware routines (`str_tolower`, comparisons) when no explicit collation applies. Several corpus findings flag asymmetry hazards when one operator uses `DEFAULT_COLLATION_OID` while a sibling uses the input collation (e.g. citext `=` vs `<`, pg_trgm). [verified-by-code] (via `knowledge/files/contrib/dict_xsyn/dict_xsyn.c.md`).



### DefElem
The generic "defined element" parse node — a `defname`/`arg` name-value pair
the grammar produces for open-ended option lists (`WITH (...)`, `CREATE
EXTENSION` options, utility-statement knobs). Utility code walks a `List` of
`DefElem`s and interprets each by name, which keeps the grammar from needing a
dedicated production per option. [verified-by-code] (via
`knowledge/files/contrib/pg_plan_advice/pg_plan_advice.c.md`).



### DefineCustomBoolVariable
The GUC-registration entry point an extension calls (typically from `_PG_init`) to add a custom boolean parameter, supplying name, help text, storage pointer, default, context, flags, and optional check/assign/show hooks. [from-comment] (via `knowledge/files/contrib/sepgsql/hooks.c.md`).



### DefineQueryRewrite
The implementation of CREATE RULE: it validates and installs a rewrite rule
into `pg_rewrite`, including the special handling that converts a relation
into a view when an `ON SELECT DO INSTEAD` rule is added. [verified-by-code]
(`rewriteDefine.c:224` — via `knowledge/subsystems/parser-and-rewrite.md`).



### DELAY_CHKPT_IN_COMMIT
A `delayChkpt` flag a backend sets on its `PGPROC` across the window where it
has written its commit WAL but not yet made the effects visible, forcing a
concurrent checkpoint to wait so it cannot capture a torn commit state. Logical
replication's conflict detection reads the oldest such xid via
`TwoPhaseGetOldestXidInCommit`. [verified-by-code] (`twophase.c:2835` — via
`knowledge/files/src/backend/access/transam/twophase.c.md`).



### deleteDependencyRecordsFor
Removes every `pg_depend` row whose dependent object is the given (classid, objid); called during DROP and ALTER to tear down an object's outgoing dependency edges before the object itself is removed. [verified-by-code] (via `knowledge/files/src/backend/catalog/pg_depend.c.md`).



### DestReceiver
The abstract sink for query result tuples: a struct of `receiveSlot`/`rStartup`/
`rShutdown`/`rDestroy` callbacks chosen by command context (client wire
protocol, `SELECT INTO`/tuplestore, SPI, COPY, printtup). The executor calls
`receiveSlot` per output tuple without knowing the concrete destination.
[from-comment] (`pl_exec.c:3576` — via
`knowledge/files/src/pl/plpgsql/src/pl_exec.md`).



### DirectFunctionCall1
Calls a built-in function by its C symbol with one argument, bypassing the fmgr catalog lookup; the fast path for invoking a known function like `nextval` or a type input function from C. `DirectFunctionCall2`/`3`/… take more args. [verified-by-code] (via `knowledge/files/contrib/spi/autoinc.c.md`).



### DirectFunctionCall2
An fmgr convenience macro that calls a built-in C function by its C symbol
with two `Datum` arguments, skipping catalog lookup; it errors if the callee
returns NULL (use `FunctionCall2` when NULL is possible). [verified-by-code]
(via `knowledge/files/contrib/intarray/_int_op.md`).



### disabled_nodes
A count field on `Path`/`Plan` (PG17+) recording how many plan nodes were built
from a disabled operation (e.g. under `enable_seqscan = off`); the planner now
prefers the path with the fewest disabled nodes before comparing cost, instead
of the old "add a huge `disable_cost` penalty" hack. [verified-by-code] (via
`knowledge/subsystems/optimizer.md`).



### DropRelationBuffers
The bufmgr bulk routine that discards all shared-buffer pages belonging to a relation's forks (e.g. on truncate/drop) so stale data is not flushed back to a relfile that is going away. [verified-by-code] (via `knowledge/files/src/backend/storage/buffer/bufmgr.c.md`).



### dsa_area
The per-backend handle to a dynamic shared-memory area — an allocator that
hands out `dsa_pointer`s usable across cooperating backends (parallel workers),
backed by one or more DSM segments that grow on demand. Code attaches to a shared
area, `dsa_allocate`s from it, and translates pointers with `dsa_get_address`.
[verified-by-code] (`dsa.c:347-373` — via
`knowledge/files/src/backend/utils/mmgr/dsa.c.md`).



### dsa_pointer
A relative offset into a dynamic shared memory area (DSA), used instead of a raw
pointer because the same DSA segment can be mapped at different addresses in
different backends. `dsa_get_address` converts it to a usable local pointer;
`InvalidDsaPointer` is the null sentinel. [verified-by-code] (via
`knowledge/files/src/backend/utils/mmgr/dsa.c.md`).



### dshash
The dynamic shared-memory hash table built on `dsa` — a concurrent,
partition-locked hash map whose entries live in a `dsa_area` so multiple
backends (e.g. parallel workers, the shared typmod registry, stats collector
tables) can read and write it. [verified-by-code] (`dshash.c:1-30` — via
`knowledge/files/src/backend/lib/dshash.c.md`).



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



### durable_rename
The fsync-aware wrapper around `rename(2)` that renames a file and then fsyncs
both the file and the containing directory so the new name survives a crash.
Used wherever a rename must be crash-safe, such as installing an archived WAL
segment or finalizing a control file. [verified-by-code] (via
`knowledge/files/contrib/basic_archive/basic_archive.c.md`).



### elog
The terse error/log macro for internal "can't happen" conditions: `elog(ERROR, "…")` takes only a level and a format string (no SQLSTATE or detail), longjmp'ing on ERROR like `ereport`. Reserved for programming errors, not user-facing messages. [verified-by-code] (via `knowledge/files/contrib/spi/moddatetime.c.md`).



### EmitWarningsOnPlaceholders
The former name of `MarkGUCPrefixReserved` — the call an extension makes after defining its GUCs to claim its `prefix.*` namespace, so unknown `prefix.foo` settings warn instead of silently persisting. [verified-by-code] (`guc.h:418-421` — via `knowledge/files/src/include/utils/guc.h.md`).



### EndCommand
The tcop routine that sends the `CommandComplete` message (carrying the statement's `CommandTag` and any row count) to the client after a command finishes; the bookend to `BeginCommand`. [verified-by-code] (via `knowledge/subsystems/tcop.md`).



### EnsurePortalSnapshotExists
Makes sure an active snapshot is pushed for the current portal before running
a query that needs one — notably after a `COMMIT` inside a procedure has torn
down the previous snapshot. [verified-by-code] (`pl_exec.c:6119` — via
`knowledge/files/src/pl/plpgsql/src/pl_exec.md`).



### ereport
The macro family for reporting errors and log messages, taking an elevel
(DEBUG…NOTICE…ERROR…PANIC), a SQLSTATE, and `errmsg`/`errdetail`/`errhint`
fields. `ERROR` and above do a `longjmp` to the nearest handler. Every C file
that reports errors includes `elog.h`. [verified-by-code] (via
`knowledge/files/src/include/utils/elog.h.md`).



### errcode
The `ereport` auxiliary that sets the five-character SQLSTATE for an error, e.g. `errcode(ERRCODE_UNDEFINED_COLUMN)`; codes come from `errcodes.txt`. Omitting it defaults to `ERRCODE_INTERNAL_ERROR`. [verified-by-code] (via `knowledge/files/contrib/spi/refint.c.md`).



### ERRCODE_FEATURE_NOT_SUPPORTED
The SQLSTATE (class 0A) raised when a code path is deliberately unimplemented or an internal-only type/operation is invoked from SQL; e.g. internal GiST key types raise it from their in/out functions. [verified-by-code] (via `knowledge/files/contrib/intarray/_intbig_gist.md`).



### ERRCODE_INVALID_PARAMETER_VALUE
The SQLSTATE `22023` reported when a function argument or option is given a
value that is out of range or otherwise unacceptable for the operation.
[from-comment] (via `knowledge/files/contrib/pgcrypto/crypt-sha.md`).



### errdetail
The `ereport` auxiliary supplying a secondary detail line (a full sentence, capitalised) elaborating the primary `errmsg`; `errdetail_internal` skips translation for fixed text. [verified-by-code] (via `knowledge/files/contrib/postgres_fdw/connection.c.md`).



### errhint
The `ereport` auxiliary supplying a hint line suggesting how to fix the error; phrased as advice, may be a sentence fragment, and is the lowest-priority of the message components. [verified-by-code] (via `knowledge/files/contrib/postgres_fdw/connection.c.md`).



### errmsg
The `ereport` auxiliary carrying the primary, translatable error message; convention is lower-case start, no trailing period, no embedded newlines. The one component every error must have. [verified-by-code] (via `knowledge/files/contrib/spi/autoinc.c.md`).



### errmsg_internal
The `ereport` message helper for messages that should NOT be translated or
shown to ordinary users — internal "can't happen" conditions and developer
diagnostics. It behaves like `errmsg` but skips gettext, signalling that the
text is for hackers, not for end users. [verified-by-code] (via
`knowledge/idioms/error-handling.md`).



### error_context_stack
The backend-global linked list of `ErrorContextCallback`s; each pushed entry contributes an errcontext line (the "while ... " annotations) when an error is reported, and is popped on normal exit or unwound by the `PG_TRY`/setjmp machinery on longjmp. Callbacks must restore the previous head, and care is needed so a mid-operation longjmp doesn't skip a pop. [verified-by-code] (via `knowledge/files/contrib/file_fdw/file_fdw.c.md`).



### ErrorContext
A small `MemoryContext` reserved at backend startup so that error reporting can
allocate even when the failing operation has exhausted memory; it is reset
after each error is handled. Along with `TopMemoryContext` it is one of only two
contexts initialized directly by `MemoryContextInit`. [from-comment]
(`mcxt.c:362-398` — via
`knowledge/files/src/include/utils/memutils.h.md`).



### ErrorContextCallback
A node on a per-backend linked stack of "add context to the next error" callbacks; ereport() walks the stack so each layer (e.g. plpgsql line, COPY row) can append an errcontext() line describing where the error arose. [verified-by-code] (via `knowledge/files/src/include/utils/elog.h.md`).



### ErrorData
The struct that accumulates one in-flight error/log report — SQLSTATE, severity, message/detail/hint, source file/line/function, and context — built up by ereport()/errmsg() and consumed by the error-context callbacks and the log/client emitters. [verified-by-code] (`elog.c:12` — via `knowledge/files/src/backend/utils/error/elog.c.md`).



### ErrorResponse
The protocol message the backend sends to report an error to the client,
composed of typed fields (severity, SQLSTATE, message, detail, hint, position…)
mirroring an `ereport`. libpq parses it into a `PGresult`; it is one of the
message types allowed to exceed the normal length cap. [verified-by-code] (via
`knowledge/files/src/interfaces/libpq/fe-trace.c.md`).



### ErrorSaveContext
A node passed into "soft" input functions so a conversion failure is reported by setting a flag in the context instead of throwing via ereport; callers that supply it (COPY ... ON_ERROR, the SQL/JSON functions) can skip or default a bad value rather than abort the statement. [verified-by-code] (via `knowledge/idioms/fmgr.md`).



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



### ExclusiveLock
A heavyweight table-level lock mode that conflicts with every mode except
`AccessShareLock` (so plain `SELECT` still proceeds, but any writer or
weaker lock blocks); taken e.g. by `REFRESH MATERIALIZED VIEW CONCURRENTLY`.
[from-comment] (via `knowledge/subsystems/contrib-pgrowlocks.md`).



### EXEC_BACKEND
The build symbol selecting the "re-exec" backend-startup model (mandatory on
Windows, optional elsewhere for debugging) in which a new backend is started by
exec-ing a fresh postgres image and re-attaching shared memory, instead of
relying on `fork()` to inherit the postmaster's address space. [inferred] (via
`knowledge/architecture/process-model.md`).



### ExecClearTuple
Resets a `TupleTableSlot` to empty — releasing any buffer pin or palloc'd tuple it held and marking it `TTS_EMPTY`; called between tuples in an executor node's per-tuple loop to avoid leaking pins. [verified-by-code] (via `knowledge/files/src/backend/executor/execTuples.c.md`).



### ExecEndNode
The teardown half of the executor node API: `ExecEndPlan` walks the `PlanState`
tree calling each node's `ExecEndNode` to close relations, free tuple slots, and
release per-node resources after execution finishes. [verified-by-code]
(`execMain.c:1565` — via `knowledge/subsystems/executor.md`).



### ExecEvalExpr
Runs a compiled `ExprState` against the current tuple/econtext, returning the result Datum and null flag; the per-tuple expression evaluator that `ExecInitExpr` prepares. [verified-by-code] (via `knowledge/files/src/pl/plpgsql/src/pl_exec.md`).



### ExecInitExpr
Compiles an expression tree (`Expr`) into an executable `ExprState` for a given plan node, resolving function lookups and building the step program once so per-tuple evaluation is cheap. plpgsql hooks here to install its param-eval callbacks. [verified-by-code] (via `knowledge/files/src/pl/plpgsql/src/pl_exec.md`).



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



### ExecProcNodeFirst
The wrapper installed as a plan node's `ExecProcNode` on first execution; it performs the one-time `check_stack_depth` and then swaps itself out for the node's real per-tuple routine to avoid the check on every subsequent call. [verified-by-code] (via `knowledge/files/src/backend/executor/execProcnode.c.md`).



### ExecReScan
Resets a plan node's execution state so it can be scanned again from the start —
used for the inner side of a nested loop, correlated subplans, and rewound
cursors. `execAmi.c` dispatches on `nodeTag` to the per-node `ExecReScan<Node>`
routine, which clears tuple state and rescans children. [verified-by-code] (via
`knowledge/files/src/backend/executor/execAmi.c.md`).



### ExecScan
The shared executor helper that drives a scan node's main loop — fetch the next tuple via an access-method callback, apply the node's qual, project, and return the slot — reused by SeqScan, IndexScan, ForeignScan and friends. [verified-by-code] (via `knowledge/subsystems/executor.md`).



### ExecStoreHeapTuple
Places a physical `HeapTuple` into a `TupleTableSlot`, optionally taking ownership for pfree; one of the `ExecStore*` family that populates a slot from a particular tuple representation before the executor reads it. [verified-by-code] (via `knowledge/files/src/backend/executor/execTuples.c.md`).



### ExecStoreVirtualTuple
Marks a slot's already-filled `tts_values`/`tts_isnull` arrays as the slot's valid contents (a "virtual" tuple with no physical backing); used after a node computes column values directly. [verified-by-code] (via `knowledge/files/src/backend/executor/execTuples.c.md`).



### executor
The engine that runs a finished plan tree. Each query passes through the
`ExecutorStart` / `ExecutorRun` / `ExecutorFinish` / `ExecutorEnd` lifecycle;
`ExecutorRun` (hookable, dispatching to `standard_ExecutorRun`) pulls tuples
through the plan node tree one node at a time. [verified-by-code]
(`execMain.c:308,318` — via
`knowledge/files/src/backend/executor/execMain.c.md`).



### ExecutorEnd
The final phase of executor lifecycle: it shuts down the plan tree
(`ExecEndNode` recursing through every node), releasing per-node resources
after `ExecutorStart`/`ExecutorRun`/`ExecutorFinish`. `standard_ExecutorEnd`
is the default, hookable implementation. [verified-by-code] (`execMain.c:486`
— via `knowledge/architecture/executor.md`).



### ExecutorFinish
The executor phase between `ExecutorRun` and `ExecutorEnd` that fires any
deferred after-triggers and runs `AfterTriggerEndQuery`, so all row processing
is complete before teardown; `standard_ExecutorFinish` is the hookable
default. [verified-by-code] (`execMain.c:417` — via
`knowledge/files/src/backend/executor/execMain.c.md`).



### ExecutorRun
The middle phase of executor lifecycle (after `ExecutorStart`, before
`ExecutorEnd`) that pulls tuples through the plan tree for a given row count
and direction; `standard_ExecutorRun` is the default, hookable implementation.
[verified-by-code] (`execMain.c:318` — via
`knowledge/architecture/executor.md`).



### ExecutorStart
The first of the four-phase executor API
(`ExecutorStart`/`ExecutorRun`/`ExecutorFinish`/`ExecutorEnd`). It builds the
`PlanState` tree from the `PlannedStmt` via `ExecInitNode`, allocates the
`EState`, and wires up result relations and the tuple destination — but runs no
tuples yet. [verified-by-code] (via
`knowledge/files/src/backend/executor/execParallel.c.md`).



### ExplainPropertyText
One of the format-neutral EXPLAIN output helpers (`ExplainPropertyText`,
`ExplainPropertyInteger`, `ExplainPropertyFloat`, …) that emit a labelled value
into the current `ExplainState`, letting the same node code render correctly as
TEXT, JSON, XML, or YAML. Node-specific EXPLAIN code calls these rather than
printf-ing, so all output formats stay in sync. [verified-by-code] (via
`knowledge/files/src/include/commands/explain_format.h.md`).



### ExplainState
The mutable accumulator threaded through EXPLAIN: it holds the output
`StringInfo`, the chosen format, indentation/grouping stack, and the option
flags (ANALYZE, BUFFERS, VERBOSE…). It is an opaque forward-declared struct
(INV-EXPLAIN-FORMAT) so extensions add output through the property API rather
than poking its fields. [verified-by-code] (via
`knowledge/files/src/include/commands/explain_format.h.md`).



### explicit_bzero
A memory-zeroing call the compiler is forbidden to elide as a dead store, used to scrub secrets (passwords, keys, SCRAM material) from stack/heap buffers before they go out of scope. Plain `memset(p,0,n)` right before a free is a classic dead-store-elimination target, so security-sensitive paths must use this instead. [verified-by-code] (via `knowledge/files/src/port/explicit_bzero.c.md`).



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



### FastPathStrongRelationLocks
The shared-memory array of per-hashcode counters that lets the lock manager's fast path work: a weak (relation) locker may take the fast path only while the matching strong-lock counter is zero, and a strong locker bumps it under a spinlock before forcing weak holders to the main table. [verified-by-code] (`lock.c:1832` — via `knowledge/files/src/backend/storage/lmgr/lock.c.md`).



### FastPathTransferRelationLocks
Moves a relation's weak locks out of backends' per-backend fast-path arrays
into the shared heavyweight lock table when a conflicting strong lock is
requested; it must take each backend's `fpInfoLock`. [from-comment]
(`lock.c:2885-2954` — via
`knowledge/files/src/backend/storage/lmgr/README.md`).



### FdwRoutine
The struct of callback pointers (`GetForeignRelSize`, `GetForeignPaths`,
`GetForeignPlan`, `BeginForeignScan`, `IterateForeignScan`, the modify and
analyze hooks, …) that a foreign-data wrapper's `*_handler` function populates
and returns; core code dispatches every FDW operation through it rather than
hard-coding any wrapper. [verified-by-code]
(via `knowledge/files/contrib/postgres_fdw/postgres_fdw.h.md`).



### FileSet
A named set of temporary files shared among cooperating backends (e.g. parallel hash join), built on the SharedFileSet machinery so any participant can open files created by another and the whole set is cleaned up together. [verified-by-code] (via `knowledge/files/src/backend/storage/file/fileset.c.md`).



### fireRIRrules
The rewriter routine that recursively applies relation-level instead/also
rules — most importantly expanding views into their underlying queries and
applying row-level-security qualifications. [from-comment]
(`rewriteHandler.c:2049-2063` — via
`knowledge/files/src/backend/parser/parse_cte.c.md`).



### FirstGenbkiObjectId
The OID boundary (currently 10000) separating hand-assigned catalog OIDs from those auto-assigned by genbki.pl to bootstrap objects that lack an explicit `oid` in the .dat files, so the build can fill OIDs unattended without colliding with manual ones. [from-README] (via `knowledge/files/src/include/catalog/_README.md`).



### FirstNormalObjectId
The OID (16384) at which normal runtime object creation begins; everything below is reserved for catalog and bootstrap objects, so an OID ≥ this value identifies a user-created object. [from-README] (via `knowledge/files/src/include/catalog/_README.md`).



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



### FlushErrorState
The elog.c routine that resets the error-data stack depth to -1 after an error has been handled; a `PG_CATCH` block must call it (or `PG_RE_THROW()`), or leftover stack depth makes future `errstart` calls misbehave. [verified-by-code] (`elog.c:2063` — via `knowledge/files/src/backend/utils/error/elog.c.md`).



### fmgr (function manager)
The uniform calling convention for invoking any SQL-callable C function:
arguments and result travel as `Datum`s inside a `FunctionCallInfo`, and
`PG_FUNCTION_INFO_V1` plus the `PG_GETARG_*`/`PG_RETURN_*` macros wrap the
boilerplate. The `FmgrInfo` carries the resolved function, collation, and
argument count. [from-comment] (via `knowledge/idioms/fmgr.md`).



### fmgr_info
Fills an `FmgrInfo` lookup cache for a function OID — resolving the C entry point, argument count, and strictness — so subsequent `FunctionCall*` invocations skip the catalog lookup; the setup step before repeatedly calling a dynamically-chosen function. [verified-by-code] (via `knowledge/files/src/backend/access/common/scankey.c.md`).



### FmgrInfo
The cached lookup result for a callable function: it bundles the resolved
function pointer, expected argument count, strictness, and a memory context, so
repeated `FunctionCall*` invocations skip the catalog lookup. Built once by
`fmgr_info` and reused for the life of the operation. [from-comment]
(`fastpath.c:37` — via `knowledge/subsystems/tcop.md`).



### fmtId
The fe_utils helper that double-quotes a SQL identifier only when necessary —
the single identifier-quoting chokepoint shared by psql, pg_dump and friends.
It writes into a small set of rotating static buffers, so callers must consume
the result before the next `fmtId` call. [verified-by-code]
(`string_utils.c:44` — via `knowledge/files/src/fe_utils/string_utils.c.md`).



### fmtIdEnc
The encoding-aware variant of `fmtId` that quotes an identifier while
validating it against a specified client encoding; like `fmtId` it shares the
rotating static buffer that callers must consume before the next call.
[verified-by-code] (`string_utils.c:44` — via
`knowledge/files/src/fe_utils/string_utils.c.md`).



### fn_extra
The per-call scratch pointer in `FmgrInfo`/`FunctionCallInfo` that a C function
uses to cache state (compiled regexps, lookup tables, SRF context) across
invocations within one query. It must point into a memory context that lives
long enough — typically `fn_mcxt` — and starts NULL on first call. [verified-by-code]
(via `knowledge/idioms/fmgr.md`).



### ForeignScan
The executor plan node that scans a foreign table through an FDW. For
postgres_fdw `postgresGetForeignPlan` builds it, `postgresBeginForeignScan`
opens the remote connection and declares a cursor, and `postgresIterateForeignScan`
fetches rows in batches. [verified-by-code]
(via `knowledge/files/contrib/postgres_fdw/postgres_fdw.c.md`).



### ForkNumber
The enum selecting which physical fork of a relation (main, fsm, vm, init) an smgr/buffer operation targets; passed to `smgr_bulk_start_rel` and the smgr read/write APIs. [verified-by-code] (via `knowledge/files/src/backend/storage/smgr/bulk_write.c.md`).



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



### fpInfoLock
The per-backend LWLock in `PGPROC` that guards that backend's fast-path lock
array; `FastPathTransferRelationLocks` must take it, and its ordering against
the heavyweight partition LWLock is a documented subtlety. [from-comment]
(`lock.c:2885-2954` — via
`knowledge/files/src/backend/storage/lmgr/README.md`).



### FreePageManager
The buddy-style allocator that tracks runs of free pages inside a DSA/DSM segment, backing dsa.c's sub-allocation; it keeps free ranges in a balanced btree plus size-class freelists so it can satisfy and coalesce variable-length page requests. [verified-by-code] (via `knowledge/files/src/backend/utils/mmgr/freepage.c.md`).



### FrozenTransactionId
The special transaction id 2 that marks a tuple as unconditionally visible to
everyone ("frozen"), removing it from any wraparound danger. Modern code keeps
the real xmin on the tuple and sets `HEAP_XMIN_FROZEN`, so
`HeapTupleHeaderGetXmin` returns `FrozenTransactionId` for frozen tuples; pre-9.4
heaps may still physically store xmin=2 on disk. [from-comment] (via
`knowledge/files/src/include/access/htup_details.h.md`).



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



### FuncExpr
The `primnodes.h` runtime node for an ordinary function call after parse analysis; `transformFuncCall` produces a `FuncExpr` (or `Aggref`/`WindowFunc`) from a raw `FuncCall`. [from-comment] (via `knowledge/files/src/backend/parser/parse_expr.c.md`).



### FunctionCall2Coll
Invokes a function (via its prepared `FmgrInfo`) with two arguments and an explicit collation OID; the collation-aware member of the `FunctionCallNColl` family used by comparison and pattern operators. [verified-by-code] (via `knowledge/files/src/backend/utils/sort/sortsupport.c.md`).



### FunctionCallInfo
The per-call argument bundle passed to every fmgr-callable C function — flinfo, collation, context/resultinfo, nargs, and the args[] array of (Datum, isnull) pairs; the PG_GETARG_* / PG_RETURN_* macros read and write through it. [verified-by-code] (via `knowledge/subsystems/executor.md`).



### FunctionCallInfoBaseData
The fmgr per-call argument block (`fmgr.h:85-96`): it carries the
`FmgrInfo *flinfo`, the call context node, collation, argument count, a result
NULL flag, and a trailing flexible array of `NullableDatum` args. Every
`PG_FUNCTION_ARGS` function receives a pointer to one, and `PG_GETARG_*` macros
read out of its `args[]`. [verified-by-code] (`fmgr.h:85-96` — via
`knowledge/files/src/include/fmgr.h.md`).



### Gather
The executor node that collects tuples from parallel workers (and, for
`GatherMerge`, preserves sort order) back into the leader's single stream,
marking the boundary between the parallel and serial portions of a plan. Below
it the plan runs in multiple worker backends; above it execution is serial.
[inferred] (via `knowledge/files/src/backend/executor/nodeGather.c.md`).



### GatherMerge
The parallel-query executor node that collects tuples from multiple worker backends while preserving their common sort order via a binary heap — the order-preserving counterpart to the plain Gather node. [verified-by-code] (via `knowledge/subsystems/executor.md`).



### gen_node_support
The Perl generator (`gen_node_support.pl`) that reads the node struct
definitions and emits the `copy`/`equal`/`out`/`read` support functions for
every `Node` type, driven by `pg_node_attr` annotations in the headers. Adding a
node field without re-running it leaves copy/equal silently incomplete.
[verified-by-code] (via `knowledge/files/src/backend/nodes/copyfuncs.c.md`).



### gen_salt
The pgcrypto SQL function that produces a random salt string for `crypt()`, encoding the algorithm (`des`, `md5`, `xdes`, `bf`) and, for adaptive hashes, a work-factor. The corpus flags weak defaults — e.g. `gen_salt('bf')` defaulting to cost 5, below modern guidance. [verified-by-code] (via `knowledge/files/contrib/pgcrypto/pgcrypto.md`).



### generic_xlog
The Generic WAL facility that lets extensions (and some core AMs) WAL-log arbitrary page modifications without writing a custom resource manager; the producer registers buffers, edits page images, and `GenericXLogFinish` computes per-page deltas and emits the record. Redo is generic byte-delta replay, so no extension-specific redo routine is needed. [verified-by-code] (`generic_xlog.c` — via `knowledge/files/src/backend/access/transam/generic_xlog.c.md`).



### GEQO
The Genetic Query Optimizer — the fallback join-order search used when a query's FROM-list size reaches `geqo_threshold`, replacing the exhaustive dynamic-programming search with a randomized genetic algorithm to keep planning time bounded. It registers its own RelOptInfo-building path under the name `"geqo"`. [verified-by-code] (via `knowledge/files/src/backend/optimizer/util/extendplan.c.md`; see `knowledge/subsystems/optimizer.md`).



### get_attname
An `lsyscache.c` helper returning the name of a column given its relation OID and attribute number; one of the `get_att*` family wrapping `SearchSysCache` over `pg_attribute`. [verified-by-code] (via `knowledge/files/src/backend/utils/cache/lsyscache.c.md`).



### get_call_result_type
Determines a function's result tuple descriptor at run time from the call context (handling polymorphic and RECORD return types), returning a `TypeFuncClass`; the SRF setup helper that resolves what columns to return. [verified-by-code] (via `knowledge/files/contrib/pg_walinspect/pg_walinspect.c.md`).



### get_raw_page
The pageinspect SQL function that returns one 8 kB relation block as a raw
`bytea`, the entry point for the rest of the module's page-decoding functions
(`heap_page_items`, `page_header`, `bt_page_stats`). It reads through the buffer
manager, so it sees the in-memory copy of the page. [verified-by-code] (via
`knowledge/files/contrib/pageinspect/pageinspect.md`).



### get_rel_name
Returns the relation name for an OID via the relcache/syscache, or NULL if the OID no longer resolves; callers that print it must guard against the NULL, which signals a stale-OID race. [from-comment] (via `knowledge/files/contrib/pg_plan_advice/pgpa_output.c.md`).



### GetActiveSnapshot
Returns the snapshot at the top of the active-snapshot stack — the one the
currently executing query should use for visibility. Operations that run "as of
now within this command" (e.g. large-object reads) call it rather than acquiring
a fresh transaction snapshot. [verified-by-code] (via
`knowledge/files/src/backend/utils/time/snapmgr.c.md`).



### GetCurrentTransactionId
Returns the current subtransaction's XID, assigning one on first call (which makes the transaction "real" and visible in the proc array); read-only transactions never call it and so never burn an XID. [verified-by-code] (via `knowledge/files/src/backend/access/transam/xact.c.md`).



### GetMemoryChunkContext
Returns the MemoryContext that owns a given palloc'd chunk by reading the owning-context reference stored in the chunk's header; underpins pfree/repalloc and context-aware utilities. [verified-by-code] (via `knowledge/subsystems/utils-mmgr.md`).



### GetMemoryChunkSpace
Returns the total bytes (including header and padding) a given palloc'd chunk
occupies, by dispatching on the chunk's `MemoryContextMethodID`; used by
memory accounting in tuplesort/tuplestore and similar. [verified-by-code]
(`mcxt.c:773` — via
`knowledge/files/src/include/utils/memutils_memorychunk.h.md`).



### GetMultiXactIdMembers
Returns the array of `MultiXactMember` (each an xid plus its lock/update
status) packed into a given MultiXactId, used to resolve exactly who holds
row locks on a tuple whose `xmax` is a multixact. [verified-by-code] (via
`knowledge/subsystems/contrib-pgrowlocks.md`).



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



### GetTransactionSnapshot
Returns the transaction's MVCC snapshot — a new one in READ COMMITTED (per
statement), or the single serializable snapshot taken once under
REPEATABLE READ/SERIALIZABLE. It hands back a reference to a statically allocated
snapshot that callers must `RegisterSnapshot` if they need it to outlive the
command. [from-comment] (via
`knowledge/files/src/backend/utils/time/snapmgr.c.md`).



### getTypeOutputInfo
Looks up a type's output function OID and its typisvarlena flag from `pg_type`; the prelude to `OidOutputFunctionCall` when converting an arbitrary Datum to its text representation. [verified-by-code] (via `knowledge/files/contrib/pageinspect/gistfuncs.c.md`).



### GetUserId
Returns the current *effective* user OID (the one permission checks run
against), which can differ from the session user under `SECURITY DEFINER` or
`SET ROLE`. Permission-sensitive code such as postgres_fdw picks
`OidIsValid(checkAsUser) ? checkAsUser : GetUserId()` so it acts as the
row-security-defining role, matching `ExecCheckPermissions`. [verified-by-code]
(`postgres_fdw.c:1743` — via
`knowledge/files/contrib/postgres_fdw/postgres_fdw.c.md`).



### GetUserMapping
The catalog lookup (`foreign.c`) returning the `UserMapping` for a (role, server) pair; postgres_fdw calls it during scan/modify setup to find the credentials keying its connection cache. [verified-by-code] (via `knowledge/files/contrib/postgres_fdw/postgres_fdw.c.md`).



### GIN (Generalized Inverted Index)
An index access method optimized for composite values where many keys map to
one row — full-text `tsvector`, arrays, `jsonb` — built around a posting-list
structure plus a pending-list fast path for cheap inserts. Scans union/intersect
posting lists for the matched keys. [from-comment] (via
`knowledge/files/src/backend/access/gin/ginget.c.md`).



### GiST
Generalized Search Tree — an extensible *template* index AM for tree-structured indexes (R-tree, RD-tree, B-tree-like, …). The opclass author supplies the consistent/union/penalty/picksplit support functions while the core handles page layout, WAL, and concurrency. [from-docs] (via `knowledge/docs-distilled/gist.md`).



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



### grouping_planner
The planner stage that takes a single (sub)query's flattened join tree and adds the upper-rel processing — grouping/aggregation, window functions, DISTINCT, ORDER BY, and LIMIT — on top of the cheapest scan/join path, producing the final Path for that query level. It is invoked per subquery_planner level. [from-comment] (via `knowledge/files/src/backend/optimizer/prep/prepunion.c.md`; see `knowledge/subsystems/optimizer.md`).



### GUC (Grand Unified Configuration)
PostgreSQL's runtime configuration-variable system. Every setting (`work_mem`,
`wal_level`, …) is a `config_generic` record with a bool/int/real/string/enum
subclass; all built-in GUCs are registered into one table by
`build_guc_variables` at startup, and extensions add their own via
`DefineCustom*Variable`. [verified-by-code] (`guc.c:871` — via
`knowledge/files/src/backend/utils/misc/guc.c.md`).



### HandleFunctionRequest
The fastpath.c server-side handler for the legacy `PQfn()` fast-path protocol message, which invokes a function by OID directly without going through the parser/planner. [from-comment] (via `knowledge/subsystems/tcop.md`).



### has_privs_of_role
The ACL routine that tests whether one role has the privileges of another,
following role membership transitively but honoring the `INHERIT` attribute (as
opposed to `is_member_of_role`, which ignores inheritance). It backs most
permission checks on SQL objects. [verified-by-code] (via
`knowledge/files/src/backend/utils/adt/acl.c.md`).



### HASH_BLOBS
The `HASHCTL` flag passed to `hash_create` declaring that keys are
fixed-length binary blobs hashed with `tag_hash`, rather than
null-terminated C strings (the default `string_hash`). [verified-by-code]
(via `knowledge/data-structures/dynahash-hashctl.md`).



### HASH_ELEM
The `HASHCTL` flag telling `hash_create` that `keysize` and `entrysize` are
provided in the control struct; it is set for essentially every dynahash
table. [verified-by-code] (via
`knowledge/data-structures/dynahash-hashctl.md`).



### HashAgg
The hash-based grouping executor strategy (`nodeAgg.c`): it builds an in-memory
`TupleHashTable` keyed by the grouping columns, accumulating transition values
per group, and spills batches to disk when the hash table exceeds `work_mem`
(hash-agg spill). [verified-by-code] (via
`knowledge/files/src/backend/executor/execGrouping.c.md`).



### HashJoin
The executor node that joins two inputs by building an in-memory (or batched, spill-to-disk) hash table on the inner relation's join key and probing it with each outer row; chosen by the planner for equijoins on large unsorted inputs. [verified-by-code] (via `knowledge/files/src/backend/executor/nodeHash.c.md`).



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



### HEAP_COMBOCID
The `t_infomask` bit marking that a tuple's `cmin`/`cmax` field actually
stores a "combo command id" — needed because the same transaction both
inserted and later deleted the tuple in different commands, so both a real
cmin and cmax must be recoverable. [verified-by-code] (via
`knowledge/subsystems/access-heap.md`).



### heap_delete
The table-AM-level heap delete: marks a tuple deleted by stamping xmax and the command id, WAL-logs it, and returns a `TM_Result` (TM_Ok / TM_Updated / TM_BeingModified …) so the caller can handle concurrent update races. [verified-by-code] (via `knowledge/files/src/backend/access/heap/heapam_visibility.c.md`).



### heap_form_tuple
Builds a `HeapTuple` from an array of Datums and null flags against a `TupleDesc`: it computes the null-bitmap and data sizes, MAXALIGNs the data offset, palloc's the tuple, and fills the header. The standard constructor for a new heap row. [verified-by-code] (`heaptuple.c:1025` — via `knowledge/files/src/backend/access/common/heaptuple.c.md`).



### heap_freetuple
`pfree`s a `HeapTuple` produced by `heap_form_tuple`/`heap_copytuple` in a single free, since the header and data live in one palloc chunk. [verified-by-code] (`heaptuple.c:1372` — via `knowledge/files/src/backend/access/common/heaptuple.c.md`).



### heap_getattr
Extracts one attribute as a Datum from a `HeapTuple` given its attnum and `TupleDesc`, handling nulls and the cached-offset fast path; hot enough that tuplesort caches the sort key out-of-tuple to avoid calling it per comparison. [verified-by-code] (via `knowledge/files/src/backend/access/common/heaptuple.c.md`).



### HEAP_HOT_UPDATED
The `t_infomask2` bit set on the OLD tuple of a HOT update, signalling that
its `t_ctid` points to a same-page successor that continues the HOT chain
(so index entries need not be added for the new version). [verified-by-code]
(via `knowledge/subsystems/access-heap.md`).



### heap_insert
The heap access-method routine that inserts one tuple into a relation: it finds a page with free space (RelationGetBufferForTuple), writes the tuple, sets its xmin, marks the buffer dirty, and emits a WAL record. The catalog wrapper `simple_heap_insert`/`CatalogTupleInsert` is the universal "write one system-catalog row" path built on it. [verified-by-code] (via `knowledge/files/src/backend/catalog/indexing.c.md`).



### heap_modify_tuple
Builds a new `HeapTuple` from an existing one plus a sparse set of replacement values/nulls, copying unmodified columns through unchanged so they avoid recomputation; the basis for trigger "modify the NEW row" idioms. [verified-by-code] (via `knowledge/files/contrib/spi/autoinc.c.md`).



### HEAP_ONLY_TUPLE
An infomask2 bit (`0x8000`) marking a heap tuple that no index points at
directly because it was produced by a HOT update and is reachable only by
following a `t_ctid` chain from an indexed ancestor. It is what lets HOT updates
skip index maintenance. [verified-by-code] (`htup_details.h:293-296` — via
`knowledge/files/src/include/access/htup_details.h.md`).



### heap_update
The heap access-method routine that replaces a tuple with a new version: it sets the old tuple's xmax and `t_ctid` to point at the new tuple (forming the update chain), inserts the new version (HOT-updating on the same page when no indexed column changed), and WAL-logs the change. System-catalog updates go through `simple_heap_update`/`CatalogTupleUpdate`. [verified-by-code] (via `knowledge/files/contrib/sepgsql/relation.c.md`).



### HEAP_XMIN_COMMITTED
A heap-tuple hint bit caching "this tuple's inserting xact is known committed"
(its `HEAP_XMAX_COMMITTED` sibling does the same for the deleter). A set hint
may only be written after that xact's commit WAL is flushed, so a hint never
lies even though it is not itself WAL-logged. [verified-by-code]
(`heapam_visibility.c:142` — via `knowledge/subsystems/access-heap.md`).



### HeapKeyTest
The inline function (in `access/valid.h`) that applies an array of
`ScanKey`s to a heap tuple, returning whether it satisfies all of them — the
qual-check heap scans use after fetching a candidate tuple. `systable_beginscan`
falls back to it when it does a sequential scan instead of an index scan.
[verified-by-code] (via `knowledge/files/src/include/access/valid.h.md`).



### HeapTuple
The lightweight in-memory wrapper for a heap row:
`struct HeapTupleData { uint32 t_len; ItemPointerData t_self; Oid t_tableOid;
HeapTupleHeader t_data; }` — a length, the row's self-TID, its table OID, and a
pointer to the on-page header. The bit-level layout lives in `htup_details.h`.
[verified-by-code] (`htup.h:62-69` — via
`knowledge/files/src/include/access/htup.h.md`).



### HeapTupleData
The in-memory heap-tuple wrapper struct: `t_len`, `t_self` (the self-TID), `t_tableOid`, and `t_data` pointing at the on-disk `HeapTupleHeader`; `HEAPTUPLESIZE` is `MAXALIGN(sizeof(HeapTupleData))`. [verified-by-code] (`htup.h:62-69` — via `knowledge/files/src/include/access/htup.h.md`).



### HeapTupleGetDatum
Static inline that wraps a `HeapTuple` as a composite (row) `Datum` by exposing its `t_data` header; the return idiom for a function producing a composite/record result. [verified-by-code] (`funcapi.h:229-233` — via `knowledge/files/src/include/funcapi.h.md`).



### HeapTupleHeader
The on-page prefix of every heap tuple (`HeapTupleHeaderData`): it carries the
`xmin`/`xmax` transaction stamps, the `t_ctid` forward link, an infomask of
status bits, and the null bitmap, ahead of the user data. Its bit-level layout
and accessor macros live in `htup_details.h`. [from-comment] (via
`knowledge/files/src/include/access/htup_details.h.md`).



### HeapTupleHeaderData
The on-disk header prefixed to every heap tuple, holding the xmin/xmax
transaction stamps, infomask flags, the tuple's TID (`t_ctid`), and the null
bitmap; since 8.3 cmin and cmax share one field, disambiguated via the
combo-CID machinery. [from-comment] (via
`knowledge/files/src/backend/utils/time/combocid.c.md`).



### HeapTupleHeaderGetXmin
The accessor returning a tuple's inserting transaction id, honouring the
frozen bit: it yields `FrozenTransactionId` when `HEAP_XMIN_FROZEN` is set,
otherwise the raw stored xmin (`htup_details.h:328`). MVCC visibility and freeze
logic read xmin exclusively through it so frozen tuples are handled uniformly.
[from-comment] (`htup_details.h:314-321` — via
`knowledge/files/src/include/access/htup_details.h.md`).



### hint bit
A cached commit/abort status bit (`HEAP_XMIN_COMMITTED`, `HEAP_XMAX_COMMITTED`,
…) stamped into a tuple's infomask the first time a backend resolves its
transaction's fate via clog, so later visibility checks skip the clog lookup.
Setting one only dirties the page as a *hint* (`MarkBufferDirtyHint`) and is not
WAL-logged unless checksums/`wal_log_hints` are on. [from-comment] (via
`knowledge/subsystems/access-heap.md`).



### HMAC
Hash-based Message Authentication Code — a keyed hash (RFC 2104) PostgreSQL uses for SCRAM and in pgcrypto; the backend wraps OpenSSL's implementation (or an in-tree fallback) behind a px_hmac / pg_hmac vtable. [verified-by-code] (via `knowledge/files/contrib/pgcrypto/px-hmac.md`).



### HOLD_INTERRUPTS
The macro that increments `InterruptHoldoffCount` to defer processing of
cancel/die interrupts inside a sensitive region; it is paired with a
matching `RESUME_INTERRUPTS` and is weaker than a full critical section.
[verified-by-code] (via `knowledge/subsystems/storage-lmgr.md`).



### HOT (heap-only tuple)
An UPDATE optimization: when no indexed column changes and the new row version
fits on the same page, PostgreSQL chains the new tuple to the old via `t_ctid`
without inserting new index entries. The update is logged as
`XLOG_HEAP_HOT_UPDATE`, and index scans reach the live version by following the
HOT chain from the indexed root tuple. [verified-by-code] (`heapam.c:62` — via
`knowledge/files/src/backend/access/heap/heapam.c.md`).



### HTAB
The handle type for PostgreSQL's built-in dynamic hash table (`dynahash`), created by `hash_create` and used pervasively for in-memory and shared-memory hash tables (lock tables, catcache, plan caches, FDW shippability caches). Shared-memory HTABs are fixed-size and partitioned; backend-local ones can grow. [verified-by-code] (via `knowledge/files/contrib/postgres_fdw/shippable.c.md`).



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



### index_beginscan
The genam-level entry point that opens an index scan: it allocates the
`IndexScanDesc`, binds the index and heap relations and snapshot, and calls the
AM's `ambeginscan`. It is one of the "INTERFACE ROUTINES" in `indexam.c`
(`index_open`/`index_beginscan`/`index_getnext_tid`/…) that wrap the AM
callbacks. [from-comment] (`indexam.c:13-40` — via
`knowledge/files/src/backend/access/index/indexam.c.md`).



### index_close
Releases an index relation opened with `index_open`, optionally dropping the lock; one of the `indexam.c` INTERFACE ROUTINES. [verified-by-code] (`indexam.c:178` — via `knowledge/files/src/backend/access/index/indexam.c.md`).



### index_open
Opens an index relation by OID, taking the requested lock and validating that the relation really is an index; the index-specific sibling of `relation_open`/`table_open`. [verified-by-code] (`indexam.c:134` — via `knowledge/files/src/backend/access/index/indexam.c.md`).



### IndexAmRoutine
The callback table an index access method returns from its `*handler`
function, advertising build/insert/scan/vacuum entry points
(`ambuild`, `aminsert`, `amgettuple`, `amgetbitmap`, `ambulkdelete`,
`amvacuumcleanup`, …) plus capability flags. Core code dispatches through this
struct rather than hard-coding any one AM. [from-comment] (`amapi.c:1` — via
`knowledge/files/src/backend/access/index/amapi.c.md`).



### IndexScan
The plan/executor node that walks an index to find matching TIDs and fetches the corresponding heap tuples, applying any remaining qual; the ordered, selective alternative to a SeqScan. [verified-by-code] (via `knowledge/subsystems/executor.md`).



### IndexScanDesc
The runtime descriptor for an in-progress index scan, created by
`index_beginscan` and handed to every index-AM scan callback
(`amgettuple`/`amgetbitmap`). It holds the scan keys, the current/marked
positions, the heap and index `Relation`s, and the AM's private `opaque` state;
e.g. nbtree's `_bt_readpage(IndexScanDesc scan, ScanDirection dir, …)` advances
it. [verified-by-code] (via
`knowledge/files/src/backend/access/nbtree/nbtreadpage.c.md`).



### IndexTuple
The on-disk index entry layout — a header (TID pointing at the heap tuple, info bits, size) followed by the indexed key values; index AMs build and interpret it via the index_form_tuple / index_getattr helpers. [verified-by-code] (via `knowledge/files/src/backend/utils/sort/tuplesortvariants.c.md`).



### InitMaterializedSRF
Sets up a set-returning function in materialize mode: it builds the result `Tuplestore` and tuple descriptor and wires them into the `ReturnSetInfo`, so the function can emit all rows up front rather than value-per-call. [verified-by-code] (`verify_heapam.c:325` — via `knowledge/files/contrib/amcheck/verify_heapam.md`).



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



### InitProcess
The startup routine that claims a PGPROC slot from the shared ProcArray for the current backend and initializes its latch, lock-wait, and semaphore state; it runs early in backend startup, before the process can take heavyweight locks. [verified-by-code] (via `knowledge/subsystems/tcop.md`).



### initStringInfo
Initialises a `StringInfo`, allocating a small starting buffer in the current memory context so subsequent `appendStringInfo*` calls can grow it; the start of every dynamic-string build. [verified-by-code] (via `knowledge/files/src/fe_utils/astreamer_zstd.c.md`).



### injection_point
A named hook compiled in only when `--enable-injection-points` is set, letting
tests attach a callback at a precise spot in backend C code to force a race,
error, or wait. The header defers `dlopen` until first hit; the build-time gate
is the sole defense against this being an arbitrary-code surface in production.
[verified-by-code] (via
`knowledge/files/src/include/utils/injection_point.h.md`).



### InputFunctionCall
The fmgr wrapper that invokes a type's text-input function (cstring → Datum), handling the three-argument convention (value, typioparam, typmod) and NULL semantics; the entry point for parsing literals and COPY-in fields. [verified-by-code] (via `knowledge/files/contrib/postgres_fdw/postgres_fdw.c.md`).



### instr_time
PostgreSQL's portable high-precision interval-timing type and `INSTR_TIME_*` macro family, used for EXPLAIN ANALYZE timings, pg_stat_statements, and other instrumentation. The non-inline part sets a global ticks-per-nanosecond factor; the clock source is `clock_gettime(CLOCK_MONOTONIC)` (or a platform equivalent). [verified-by-code] (via `knowledge/files/src/common/instr_time.c.md`).



### Int32GetDatum
Macro packing a 32-bit signed integer into a `Datum`; the `*GetDatum` counterpart of `DatumGetInt32`, used when handing an int to fmgr or a `PG_RETURN_INT32`. [verified-by-code] (via `knowledge/files/contrib/spi/moddatetime.c.md`).



### INVALID_PROC_NUMBER
The sentinel `ProcNumber` (-1) meaning "no backend", used wherever a PGPROC
slot index may be absent — e.g. a relation with no associated temp-table
backend. [from-comment] (via `knowledge/data-structures/relfilelocator.md`).



### InvalidateCatalogSnapshot
Discards the backend's cached catalog snapshot so the next catalog read takes
a fresh one — invoked when invalidation messages indicate catalog state changed.
It is part of the `LocalExecuteInvalidationMessage` machinery that keeps relcache
and catcache coherent with committed DDL. [verified-by-code] (via
`knowledge/files/src/backend/utils/cache/inval.c.md`).



### InvalidBlockNumber
The all-ones `BlockNumber` (0xFFFFFFFF) sentinel meaning "no such block",
returned for an empty relation or an uninitialized scan position.
[verified-by-code] (via `knowledge/subsystems/storage-lmgr.md`).



### InvalidOid
The sentinel OID value 0, meaning "no object" — never a valid catalog row OID.
It is used pervasively as a null/absent marker in fixed `Oid` columns and
keys, e.g. PL/Tcl uses `InvalidOid` as the hash key for the untrusted shared
interpreter. [from-comment] (`pltcl.c:112` — via
`knowledge/files/src/pl/tcl/pltcl.c.md`).



### InvalidXLogRecPtr
The sentinel `XLogRecPtr` value 0, meaning "no valid WAL position". Because a
real record never starts at LSN 0, code uses it as a not-set marker — e.g. a
buffer's "WAL position that must be flushed before write-out" may be
`InvalidXLogRecPtr` when the page has no pending WAL dependency.
[verified-by-code] (`xlog.c:273-278` — via
`knowledge/files/src/backend/access/transam/xlog.c.md`).



### io_method
The GUC selecting how the AIO subsystem issues disk I/O — `sync` (no async),
`worker` (dedicated I/O worker processes), or `io_uring` (Linux kernel
submission rings). It is the user-facing switch over the pluggable
`IoMethodOps` callback tables. [verified-by-code] (via
`knowledge/files/src/backend/storage/aio/aio.c.md`).



### io_uring
A Linux kernel asynchronous-I/O interface that PostgreSQL's AIO subsystem can use as an I/O method (alongside worker-based and synchronous methods) to submit and reap disk reads without blocking the backend. The io_uring method keeps the ring FD open across operations, which constrains FD-close ordering. [verified-by-code] (via `knowledge/files/src/backend/storage/aio/aio.c.md`).



### IsA
The node-tag test macro that checks a `Node *` carries a given `NodeTag`; it
is the standard idiom for runtime dispatch over PostgreSQL's tagged node
hierarchy. [verified-by-code] (via `knowledge/subsystems/foreign.md`).



### ItemIdIsValid
The line-pointer validity macro: given an `ItemId` from `PageGetItemId`, it
checks the entry isn't out of range before the bytes are dereferenced. Page
inspectors reading possibly-corrupt pages must call it (and `ItemIdIsNormal`)
before `PageGetItem` to avoid reading off the page. [verified-by-code] (via
`knowledge/files/contrib/pageinspect/gistfuncs.c.md`).



### ItemPointer
A `(BlockNumber, OffsetNumber)` pair — the TID — locating a line-pointer slot on
a page. A tuple's `t_self` is its own TID; `t_ctid` points to its successor
version (or to itself when there is none). [verified-by-code]
(`htup_details.h:86` — via `knowledge/subsystems/access-heap.md`).



### ItemPointerData
The 6-byte on-disk tuple identifier (TID): a BlockIdData (block number) plus an OffsetNumber (1-based line-pointer slot). ItemPointer is a pointer to it, and the system CTID column exposes it at SQL level. [verified-by-code] (via `knowledge/files/src/include/storage/itemptr.h.md`).



### ItemPointerGetBlockNumber
Inline accessor extracting the `BlockNumber` from a TID's split `BlockIdData`; paired with `ItemPointerGetOffsetNumber` to decode a tuple pointer into (block, offset). A `NoCheck` variant skips the validity assert. [verified-by-code] (via `knowledge/files/src/include/storage/itemptr.h.md`).



### ItemPointerGetOffsetNumber
Inline accessor returning the line-pointer offset within a page from a TID; the second half of decoding an `ItemPointer`, complementing `ItemPointerGetBlockNumber`. [verified-by-code] (via `knowledge/files/src/backend/storage/page/itemptr.c.md`).



### ItemPointerSet
Inline macro that sets an `ItemPointerData` (TID) from a block number and item offset; the canonical way to construct a tuple pointer, paired with `ItemPointerSetInvalid` for the empty case. [verified-by-code] (via `knowledge/files/src/include/storage/itemptr.h.md`).



### IterateForeignScan
The `FdwRoutine` callback that returns the next tuple of a foreign scan into
the supplied slot, or an empty slot at end-of-scan; called once per row by
the executor. [verified-by-code] (via
`knowledge/subsystems/contrib-file_fdw.md`).



### JoinWaitQueue
The proc.c primitive (`proc.c:1179`) that inserts the current backend into a heavyweight lock's wait queue before it sleeps in `ProcSleep`; part of the lock-wait protocol invoked from lock.c. [verified-by-code] (`proc.c:1179` — via `knowledge/files/src/backend/storage/lmgr/proc.c.md`).



### JSON_TABLE
The SQL/JSON construct `JSON_TABLE(context_item, path COLUMNS (...))` that
turns a JSON document into a relational rowset. Parse analysis in
`parse_jsontable.c` expands the COLUMNS clause into a `TableFunc` node of type
`JSTYPE_JSON_TABLE`. [verified-by-code] (via
`knowledge/files/src/backend/parser/parse_jsontable.c.md`).



### JsonbValue
The in-memory, expanded representation of a jsonb value — a tagged union
over scalars, arrays, and objects — used while building or iterating jsonb
before it is serialized to the compact on-disk `JEntry` form. [from-comment]
(via `knowledge/subsystems/contrib-jsonb_plperl.md`).



### JsonLexContext
The jsonapi.c lexer state (input pointer, current token, optional incremental-parse buffer) threaded through the SAX-style JSON parser shared by backend and frontend; a static `failed_oom` instance handles allocation failure in the frontend. [verified-by-code] (via `knowledge/files/src/common/jsonapi.c.md`).



### JunkFilter
The executor helper (`execJunk.c`) that strips junk attributes (ctid, tableoid, resjunk sort/group columns) from a tuple before it is returned to the client, and extracts the system columns row-modifying nodes need. [verified-by-code] (via `knowledge/files/src/backend/executor/execJunk.c.md`).



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



### launch_backend
The postmaster path (`postmaster_child_launch`) that forks/execs every child process — backends, autovacuum workers, background workers — passing the inherited state each needs to re-attach to shared memory. [from-comment] (via `knowledge/files/src/backend/postmaster/postmaster.c.md`).



### lcons
Prepends an element to the head of a `List` (the counterpart of `lappend`); used where newest-first ordering matters, such as inserting at the head of a cache bucket. [verified-by-code] (via `knowledge/files/contrib/sepgsql/uavc.c.md`).



### List
PostgreSQL's ubiquitous list type — an array-backed `List` of pointers
(`T_List`), integers, or OIDs — manipulated with `lappend`, `lfirst`,
`foreach`, and friends. Almost every multi-element structure in the parser,
planner, and executor is a `List`. [from-comment] (via
`knowledge/idioms/node-types-and-lists.md`).



### list_make1
Macro family (`list_make1` … `list_make5`) that builds a fixed-size `List` literal from its arguments in one call; the idiomatic way to construct short lists inline. [verified-by-code] (via `knowledge/files/src/include/nodes/pg_list.h.md`).



### ListCell
One element of PostgreSQL's List. Since the v13 rewrite a List is a flat array of ListCells, so foreach() indexes the array; a cell holds a pointer, int, or oid payload depending on the list's NodeTag. [verified-by-code] (via `knowledge/files/src/include/nodes/pg_list.h.md`).



### load_external_function
Loads a shared library (if not already loaded) and resolves a named symbol from it, returning the function pointer; the mechanism behind C-language function lookup and `$libdir`-qualified references. [verified-by-code] (via `knowledge/files/src/backend/utils/fmgr/dfmgr.c.md`).



### load_file
Loads a shared library and runs its `_PG_init` without resolving any particular symbol; used by `LOAD` and `shared_preload_libraries` to pull in a module for its hook side-effects. [verified-by-code] (via `knowledge/files/src/backend/utils/fmgr/dfmgr.c.md`).



### LocalExecuteInvalidationMessage
Applies a single shared-invalidation message to this backend's caches —
evicting the named relcache/catcache entry — the per-message worker behind
`AcceptInvalidationMessages`. [verified-by-code] (`inval.c:823` — via
`knowledge/files/src/backend/utils/cache/inval.c.md`).



### LockAcquire
The heavyweight (regular) lock-manager entry point: it finds or creates the
shared `LOCK`/`PROCLOCK` for a lock tag, checks conflicts via
`LockCheckConflicts`, and either grants immediately, takes the fast path for a
weak relation lock, or queues the backend to wait. `LockRelease` /
`LockReleaseAll` undo it. [verified-by-code] (`lock.c:806` — via
`knowledge/files/src/backend/storage/lmgr/lock.c.md`).



### LockAcquireExtended
The heavyweight-lock acquisition core that handles fast-path eligibility, the
shared lock table, and wait-queue insertion; it calls `JoinWaitQueue` while
holding the lock-partition LWLock exclusively. [verified-by-code]
(`proc.c:1193` — via `knowledge/files/src/backend/storage/lmgr/proc.c.md`).



### LockBuffer
The macro (wrapping `LockBufferInternal`) that takes or releases a buffer's
content lock in `BUFFER_LOCK_SHARE`/`BUFFER_LOCK_EXCLUSIVE`/`BUFFER_LOCK_UNLOCK`
mode — distinct from the pin that keeps the buffer resident. Readers take SHARE,
page-modifiers take EXCLUSIVE, and `LockBufferForCleanup` waits for the pin
count to drop to one for destructive operations like VACUUM pruning.
[verified-by-code] (`bufmgr.c:6567-6910` — via
`knowledge/files/src/backend/storage/buffer/bufmgr.c.md`).



### LockBufferForCleanup
Acquires a "cleanup" (superexclusive) lock on a buffer — an exclusive content
lock plus the guarantee of being the only pinner — required by operations like
VACUUM that must rearrange a page's line pointers. [verified-by-code] (via
`knowledge/files/src/backend/storage/buffer/bufmgr.c.md`).



### LockBufHdr
Acquires the per-buffer header spinlock encoded in the high bit of the
`BufferDesc` atomic state word, giving exclusive access to the buffer's tag and
flags for the brief critical section of pinning, tag reassignment, or flag
updates. `WaitBufHdrUnlocked` spins for a concurrent holder to release.
[verified-by-code] (`bufmgr.c:7527-7593` — via
`knowledge/files/src/backend/storage/buffer/bufmgr.c.md`).



### LOCKMODE
The integer type naming a heavyweight lock strength (e.g. `AccessShareLock` .. `AccessExclusiveLock`), used as the argument to `LockRelation`/`table_open` and checked against the per-method conflict table to decide whether a request must wait. amcheck and many AMs take a relation under a specific LOCKMODE before reading. [verified-by-code] (via `knowledge/files/contrib/amcheck/verify_common.md`).



### LockRelationForExtension
The relation-extension lock taken before adding a new block to a heap or
index, serialising concurrent extenders so two backends don't both think they
created the same block number. It is a short-duration lock released as soon as
the page is added; read-only inspectors like `pgstatindex` deliberately do NOT
take it. [verified-by-code] (via
`knowledge/files/contrib/pgstattuple/pgstatindex.c.md`).



### LockRelationOid
Acquires a heavyweight relation lock by OID in a given mode, registering it with the lock manager so it is released at transaction end; the low-level lock under `table_open`/`relation_open`, also called directly when locking a relation without opening it. [verified-by-code] (via `knowledge/files/contrib/pg_prewarm/pg_prewarm.c.md`).



### LockRelease
The heavyweight lock-manager routine that releases one held lock on a `LOCKTAG` for a given mode, decrementing the `LOCK`/`PROCLOCK` and waking waiters if the lock becomes grantable. [verified-by-code] (`lock.c:806` — via `knowledge/files/src/backend/storage/lmgr/lock.c.md`).



### LOCKTAG
The struct uniquely identifying the object a heavyweight lock protects — a tag of (locktag fields + lock method) covering relations, tuples, transactions, pages, advisory locks, etc. `LOCKTAG_TUPLE` is used, for example, by `systable_inplace_update_begin` to serialize inplace catalog updates against concurrent readers. [verified-by-code] (via `knowledge/files/src/backend/access/index/genam.c.md`).



### LOCKTAG_TUPLE
A heavyweight-lock tag identifying a specific tuple (relation + block +
offset), used where buffer content locks are too short-lived — e.g.
`systable_inplace_update` takes one so a concurrent reader of a
`pg_class.relfrozenxid` in-place update sees a torn write only if it explicitly
re-reads. [verified-by-code] (via
`knowledge/files/src/backend/access/index/genam.c.md`).



### LockTuple
The heavyweight tuple-lock API (`LockTuple`/`ConditionalLockTuple`/`UnlockTuple`) used as the *arbiter* that serializes concurrent row-lockers; the actual row-lock state still lives in the tuple's xmax/infomask, not in this lock. [verified-by-code] (`lmgr.c:562` — via `knowledge/files/src/backend/storage/lmgr/lmgr.c.md`).



### LockTupleMode
The enum naming the strength of a row-level lock
(`LockTupleKeyShare`/`Share`/`NoKeyExclusive`/`Exclusive`), as requested by
`SELECT ... FOR [KEY] SHARE/UPDATE` and by the executor's
`table_tuple_lock`. Logical-replication apply and EvalPlanQual re-find the live
tuple and re-lock it in the requested `LockTupleMode`. [verified-by-code] (via
`knowledge/files/src/backend/executor/execReplication.c.md`).



### logical decoding
The mechanism that turns the physical WAL stream back into a logical sequence
of row-level INSERT/UPDATE/DELETE changes, driven by a replication slot and an
output plugin. It underpins logical replication and CDC tooling without those
consumers parsing WAL themselves. [from-README] (via
`knowledge/subsystems/replication.md`).



### LogicalDecodingContext
The per-slot heap-allocated state of a logical decoding session, wiring
together the reorder buffer, the snapshot builder, and the output plugin's
callbacks; it lives in its own memory context. [verified-by-code]
(`logical.h:33-115` — via
`knowledge/files/src/include/replication/logical.h.md`).



### LogicalDecodingProcessRecord
The logical-decoding dispatch entry point: for each WAL record read via an `XLogReaderState` it switches on `XLogRecGetRmid` and routes to the per-rmgr decode handler (xlog, heap, heap2, xact, standby, logicalmsg). [verified-by-code] (via `knowledge/files/src/include/replication/decode.h.md`).



### lookup_type_cache
The typcache entry point: a cheap hashtable lookup keyed by type OID that then
lazily computes only the fields the caller's `TYPECACHE_*` flags request
(equality operator, btree opfamily, hash proc, …) and caches "tried and none
exists" negatives. It is how the executor and others get a type's comparison and
I/O support without repeated catalog scans. [verified-by-code] (via
`knowledge/files/src/backend/utils/cache/typcache.c.md`).



### LP_DEAD
The line-pointer flag marking an item as dead — its heap/index tuple is known gone — so scans can skip it and page-level cleanup can reclaim its space. In indexes the bit is a dirty *hint* set by scans; actual cleanup happens later (e.g. at insert time via `_hash_vacuum_one_page` / nbtree page-pruning). [verified-by-code] (via `knowledge/files/src/backend/access/hash/hashsearch.c.md`).



### lp_len
The length field of a heap/index line pointer (ItemId) giving the on-page byte length of the pointed-to item; together with `lp_off` it locates the tuple within the page. amcheck validates the geometry invariants `lp_len >= MAXALIGN(SizeofHeapTupleHeader)` and `lp_off + lp_len <= BLCKSZ`. [verified-by-code] (via `knowledge/files/contrib/amcheck/verify_heapam.md`).



### LP_NORMAL
The `ItemId` line-pointer state for a slot that points at a normal, stored
heap tuple (both offset and length are valid), as opposed to `LP_UNUSED`,
`LP_REDIRECT`, or `LP_DEAD`. [verified-by-code] (via
`knowledge/files/contrib/amcheck/verify_heapam.md`).



### lp_off
The 15-bit byte offset within an 8 kB page where a line pointer's (`ItemIdData`)
tuple begins; together with `lp_len` and `lp_flags` it forms the item
identifier in the page's line-pointer array. The offset is to the start of the
tuple, measured from the page beginning. [verified-by-code] (via
`knowledge/files/src/include/storage/itemid.h.md`).



### LP_REDIRECT
An `ItemId` line-pointer state used by HOT: a redirecting pointer whose
offset names the live root of a HOT chain after the original root tuple was
pruned, keeping index entries valid without rewriting them.
[verified-by-code] (via `knowledge/subsystems/access-heap.md`).



### LP_UNUSED
An `ItemId` line-pointer state marking a slot that holds no storage and is
free for reuse; produced by page pruning and vacuum reclaiming dead tuples.
[verified-by-code] (via `knowledge/subsystems/access-heap.md`).



### LSN (log sequence number)
A byte position in the continuous WAL stream, represented by the 64-bit
`XLogRecPtr` type. Every WAL record and every modified page records an LSN;
comparing LSNs orders changes in time, and `InvalidXLogRecPtr` (0) marks "no
position". [verified-by-code] (`xlogdefs.h:28` — via
`knowledge/files/src/include/access/xlogdefs.h.md`).



### LW_EXCLUSIVE
The `LWLockAcquire` mode requesting exclusive ownership of a lightweight
lock, blocking all other shared and exclusive waiters until released;
contrast `LW_SHARED`. [verified-by-code] (via
`knowledge/subsystems/storage-lmgr.md`).



### LWLock (lightweight lock)
The in-memory lock used to guard shared-memory data structures, offering
exclusive and shared modes but no deadlock detection. LWLocks are cheap
relative to the heavyweight lock manager and are automatically released on
`elog(ERROR)` via `LWLockReleaseAll`. [from-comment] (`lwlock.c:6` — via
`knowledge/files/src/backend/storage/lmgr/lwlock.c.md`).



### LWLockAcquire
Acquires a lightweight lock in `LW_SHARED` or `LW_EXCLUSIVE` mode, sleeping
on the lock's wait queue if it can't be granted immediately; it is the
primary primitive guarding shared-memory data structures. [verified-by-code]
(via `knowledge/subsystems/storage-lmgr.md`).



### LWLockRelease
Releases an LWLock held by the current backend and wakes the next compatible
waiter(s) on its queue; every `LWLockAcquire` must be balanced by exactly
one of these (resource owners catch leaks on error). [verified-by-code] (via
`knowledge/subsystems/storage-lmgr.md`).



### MAIN_FORKNUM
The `ForkNumber` (0) of a relation's main data fork, as distinct from the
free-space-map (`FSM_FORKNUM`), visibility-map (`VISIBILITYMAP_FORKNUM`),
and unlogged-table init forks. [verified-by-code] (via
`knowledge/subsystems/contrib-pageinspect.md`).



### MainLWLockArray
The shared-memory array holding all individually-named LWLocks plus the slices handed out by `RequestNamedLWLockTranche`; the named locks are declared via `PG_LWLOCK` macros in `lwlocklist.h`. [verified-by-code] (`lwlocklist.h:34-91` — via `knowledge/idioms/locking-overview.md`).



### MAKE_SYSCACHE
The macro that declares one syscache: it ties a `SysCacheIdentifier` enum value
to the backing catalog and the unique index used as the lookup key, feeding the
generated `cacheinfo[]` table that `InitCatalogCache` builds from.
[verified-by-code] (`syscache.c:13` — via
`knowledge/files/src/backend/utils/cache/syscache.c.md`).



### makeNode
Allocates a zeroed node of the given type and stamps its `nodeTag`; every parse/plan node creation goes through it so `nodeTag()` dispatch in the copy/equal/out/read funcs works. [verified-by-code] (via `knowledge/files/src/backend/parser/gram.y.md`).



### makeObjectName
Constructs a candidate catalog object name from up to three component strings, truncating on NAMEDATALEN with a separator; the basis for `ChooseRelationName`/`ChooseIndexName` auto-naming of constraints and indexes. [verified-by-code] (`indexcmds.c:2546` — via `knowledge/files/src/backend/commands/indexcmds.c.md`).



### makeStringInfo
Allocates and initialises a `StringInfo` in one call (palloc + `initStringInfo`), returning the pointer; used where the buffer outlives the current stack frame, e.g. as aggregate transition state. [verified-by-code] (via `knowledge/files/src/backend/utils/adt/bytea.c.md`).



### MarkBufferDirty
The call that flags a pinned, exclusively-locked buffer as modified so the
background writer/checkpointer will eventually write it; it must run inside the
WAL critical section so the dirty mark and the WAL record are atomic with
respect to crashes. Contrast `MarkBufferDirtyHint`, which is for
non-WAL-critical hint-bit changes. [verified-by-code] (`bufmgr.c:3156` — via
`knowledge/files/src/backend/storage/buffer/bufmgr.c.md`).



### MarkBufferDirtyHint
Marks a buffer dirty for a non-critical "hint" change (e.g. setting a tuple
hint bit or a VM bit), optionally emitting a WAL full-page image when
checksums or `wal_log_hints` are on; unlike `MarkBufferDirty` it tolerates
being skipped. [from-comment] (via
`knowledge/files/src/backend/access/heap/heapam_visibility.c.md`).



### MarkGUCPrefixReserved
The call an extension makes (typically in `_PG_init`) to claim a custom-GUC
prefix such as `postgres_fdw.`, so the GUC machinery rejects unknown
`prefix.something` settings instead of silently keeping them as placeholders.
It is how a module turns its namespace into validated configuration.
[verified-by-code] (`option.c:572` — via
`knowledge/files/contrib/postgres_fdw/option.c.md`).



### MAXALIGN
The macro rounding a size or pointer up to `MAXIMUM_ALIGNOF`, the strictest alignment any SQL datum requires; tuple headers, datums on a page, and palloc chunks are all MAXALIGN'd so typed access never faults. Width estimates and on-page layout math (e.g. `MAXALIGN(width) + MAXALIGN(SizeofHeapTupleHeader)`) use it constantly. [verified-by-code] (via `knowledge/files/contrib/file_fdw/file_fdw.c.md`).



### MaxAllocSize
The 1 GB − 1 (`0x3fffffff`) soft ceiling that ordinary `palloc` enforces;
requests above it raise an error. Chosen so allocation sizes always fit safely
in arithmetic; allocations that genuinely need more must use the `*Huge`
variants (`MemoryContextAllocHuge`, `palloc_extended` with `MCXT_ALLOC_HUGE`),
which raise the bound to `SIZE_MAX/2`. [from-comment] (`memutils.h:40` — via
`knowledge/idioms/memory-contexts.md`).



### MaxBackends
The computed ceiling on concurrent backends (max_connections + autovacuum workers + background workers + auxiliary procs); shared-memory structures such as the deadlock detector's worst-case workspace are pre-sized from it at startup. [verified-by-code] (`deadlock.c:143` — via `knowledge/files/src/backend/storage/lmgr/deadlock.c.md`).



### MaxBlockNumber
The largest valid `BlockNumber`, one below `InvalidBlockNumber`
(0xFFFFFFFE), bounding a relation at ~4 billion blocks. Code that allocates
per-block arrays sized off the relation length is implicitly bounded by it —
and doing so without the huge-allocation flag is a flagged resource concern in
`pg_visibility`. [verified-by-code] (via
`knowledge/files/contrib/pg_visibility/pg_visibility.c.md`).



### MaxHeapTuplesPerPage
The upper bound on line pointers a heap page can hold, derived from the smallest possible tuple and the page size; it sizes per-page work arrays (e.g. prune/redirect) and bounds the OffsetNumbers on a heap page. [verified-by-code] (via `knowledge/files/src/backend/access/heap/pruneheap.c.md`).



### MAXPGPATH
The compile-time maximum length (1024) for a filesystem-path buffer in PostgreSQL C code; path helpers snprintf into char[MAXPGPATH] arrays and treat truncation past it as an error. [verified-by-code] (via `knowledge/files/src/bin/pg_dump/pg_backup_directory.c.md`).



### MCXT_ALLOC_HUGE
The `MemoryContextAllocExtended` flag that lifts the normal 1 GB allocation
cap, allowing a single chunk up to `MaxAllocHugeSize`; used for genuinely
large buffers like big sorts. [verified-by-code] (via
`knowledge/subsystems/utils-mmgr.md`).



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



### MemoryContextAlloc
The base allocator that requests a chunk from a specific MemoryContext rather than CurrentMemoryContext; palloc is the common wrapper that targets CurrentMemoryContext, and variants add zeroing, huge-size, or no-OOM-error behavior. [verified-by-code] (via `knowledge/files/src/backend/utils/mmgr/mcxt.c.md`).



### MemoryContextAllocAligned
Allocates a chunk guaranteed to start on a requested power-of-two alignment by
over-allocating and embedding a redirection header, so the returned pointer
still frees correctly via the normal chunk machinery. [verified-by-code]
(`mcxt.c:1485-1591` — via
`knowledge/files/src/backend/utils/mmgr/alignedalloc.c.md`).



### MemoryContextCreate
The low-level constructor that initialises a new memory-context node of a
given method type and links it under a parent; allocator-specific creators
such as `AllocSetContextCreate` call it. [verified-by-code]
(`memutils_internal.h:148-158` — via
`knowledge/files/src/include/utils/memutils_internal.h.md`).



### MemoryContextData
The common header every memory context node begins with — method id,
parent/child/sibling links, name, and reset/delete callback — that the
concrete allocators (`AllocSetContext` etc.) extend. [verified-by-code]
(`aset.c:158-171` — via `knowledge/files/src/backend/utils/mmgr/aset.c.md`).



### MemoryContextDelete
Frees a memory context and all its children in one shot, releasing every
allocation made in them without per-chunk `pfree`s — the workhorse of PG's
region-based memory discipline. Tearing down a per-function or per-query context
(e.g. plpgsql's `func->fn_cxt`) reclaims all its palloc'd state at once.
[verified-by-code] (via
`knowledge/files/src/pl/plpgsql/src/pl_funcs.md`).



### MemoryContextInit
The startup routine that creates the bootstrap memory contexts; per its own comment only `TopMemoryContext` and `ErrorContext` are initialized here, while every other context is created later by its owning subsystem. [from-comment] (`memutils.h:53-57` — via `knowledge/files/src/include/utils/memutils.h.md`).



### MemoryContextMethodID
The small enum tag stored in a memory chunk's header identifying which
allocator (AllocSet/Slab/Generation/Bump) owns it, so `pfree`/`repalloc` can
dispatch to the right method without a context pointer. [verified-by-code]
(`memutils_internal.h:107-147` — via
`knowledge/files/src/include/utils/memutils_memorychunk.h.md`).



### MemoryContextReset
Frees all allocations made in a memory context (and resets it for reuse)
without destroying the context object itself — the cheap bulk-free that makes
per-tuple and per-call scratch contexts practical. Caches that rebuild from
scratch, like sepgsql's userspace AVC, reset their context rather than
`pfree`-ing entries one by one. [verified-by-code] (`uavc.c:78-86` — via
`knowledge/files/contrib/sepgsql/uavc.c.md`).



### MemoryContextStats
The mcxt.c routine (`mcxt.c:866`) that walks a context subtree and logs per-context allocation totals; the engine behind backend memory-context dumps and `pg_log_backend_memory_contexts`. [verified-by-code] (`mcxt.c:866` — via `knowledge/files/src/backend/utils/mmgr/mcxt.c.md`).



### MemoryContextStrdup
The palloc-family helper that copies a NUL-terminated string into a *specified* memory context (rather than `CurrentMemoryContext`, which is what `pstrdup` uses). [verified-by-code] (via `knowledge/files/src/include/utils/palloc.h.md`).



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



### MergeJoin
The executor node that joins two inputs already sorted on the join key by advancing through both in lockstep; efficient when the inputs are pre-sorted (or cheaply sortable) and the join is an equality or range condition. [verified-by-code] (via `knowledge/subsystems/executor.md`).



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



### missing_ok
A widespread boolean-parameter convention: when true, a lookup that fails to find its object returns a sentinel (NULL/`InvalidOid`) instead of raising an error — e.g. `IndexGetRelation(indrelid, true)`. Lets callers probe for existence without `PG_TRY`. [inferred] (via `knowledge/files/contrib/amcheck/verify_common.md`).



### ModifyTable
The executor plan node that performs `INSERT` / `UPDATE` / `DELETE` / `MERGE`,
driving the per-row table-AM and trigger machinery via
`ExecForeignInsert/Update/Delete` for foreign targets. postgres_fdw can bypass
it entirely with "direct modify", emitting the remote UPDATE/DELETE straight
from a single ForeignScan when all SET clauses are shippable and there are no
local quals. [verified-by-code]
(via `knowledge/files/contrib/postgres_fdw/postgres_fdw.c.md`).



### MultiExec
The executor path for nodes that return a whole materialized result at once instead of tuple-at-a-time; `MultiExecProcNode` dispatches to e.g. `MultiExecBitmapIndexScan`/`MultiExecHash`, which hand back a bitmap or hash table. [from-comment] (via `knowledge/files/src/backend/executor/nodeBitmapIndexscan.c.md`).



### MultiXact
A "multiple transaction" id used as a tuple's `xmax` when several transactions
hold a shared lock (or a mix of share/update locks) on the same row at once. The
visibility code resolves the real updater lazily via `HeapTupleGetUpdateXid`,
which may force MultiXact SLRU I/O, so it only does so after the cheaper
infomask-only checks fail. [verified-by-code]
(`heapam_visibility.c:1173-1176` — via
`knowledge/files/src/backend/access/heap/heapam_visibility.c.md`).



### MultiXactId
An identifier for a set of transactions that simultaneously hold a lock on one row; when more than one transaction locks a tuple (e.g. FOR SHARE) the tuple's xmax stores a MultiXactId resolving to the member list, tracked by the multixact SLRUs. [verified-by-code] (via `knowledge/files/src/backend/access/transam/multixact.c.md`).



### MultiXactId (multixact)
An identifier standing in for a *set* of transactions that simultaneously hold
a row lock (e.g. several `SELECT ... FOR SHARE`), stored in a tuple's xmax when
more than one locker is involved. Members and offsets live in dedicated SLRUs
under `pg_multixact/`. [from-comment] (via
`knowledge/files/src/backend/access/transam/multixact.c.md`).



### MultiXactMember
One entry in a multixact's member array: a `TransactionId` plus status flag bits encoding the lock/update strength that transaction holds on a shared-locked row. The member arrays live in the pg_multixact "members" SLRU. [from-comment] (via `knowledge/files/src/backend/access/transam/multixact.c.md`).



### MultiXactOffset
The 32-bit index type into the pg_multixact "members" SLRU; each `MultiXactId` maps to an offset marking where its `MultiXactMember` array begins. [verified-by-code] (via `knowledge/files/src/backend/access/transam/multixact.c.md`).



### MVCC
Multi-Version Concurrency Control — PostgreSQL keeps multiple row versions and uses per-tuple xmin/xmax plus a snapshot to decide which version each transaction sees, so readers never block writers or vice versa; the decision lives in the heapam visibility routines. [verified-by-code] (`heapam_visibility.c:6` — via `knowledge/files/src/backend/access/heap/heapam_visibility.c.md`).



### MVCC (multiversion concurrency control)
PostgreSQL's concurrency model: each row version (tuple) carries `xmin`/`xmax`
transaction stamps, and a snapshot decides which versions a query may see, so
readers never block writers. The visibility logic lives in routines like
`HeapTupleSatisfiesMVCC`, which test a tuple's xmin/xmax against the snapshot.
[verified-by-code] (`heapam_visibility.c:938` — via
`knowledge/files/src/backend/access/heap/heapam_visibility.c.md`).



### MXID
A MultiXactId — an identifier standing in for a *set* of transactions, used when several transactions hold a shared row lock (or a mix of share/update locks) on the same tuple simultaneously. Like XIDs, MXIDs are 32-bit and subject to wraparound, so they have their own freeze/vacuum horizon; the membership lives in the `pg_multixact` SLRU. [verified-by-code] (via `knowledge/files/contrib/amcheck/verify_heapam.md`).



### MyDatabaseId
The global holding the OID of the database the current backend is connected to, set during InitPostgres once the backend latches onto a database; most catalog lookups are implicitly scoped by it. [verified-by-code] (`postinit.c:707` — via `knowledge/files/src/backend/utils/init/postinit.c.md`).



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



### MyProcNumber
The current backend's index into the shared PGPROC array (its ProcNumber) — a small dense integer used to address per-backend shared-state slots (fast-path locks, the sinval queue, ProcSignal) without a pointer. [verified-by-code] (via `knowledge/files/src/backend/utils/init/globals.c.md`).



### MyProcPid
The cached process id (getpid()) of the current backend, set at startup and reused in log lines, cancel-key checks, and lock/lwlock owner bookkeeping instead of calling getpid() repeatedly. [verified-by-code] (`csvlog.c:69` — via `knowledge/files/src/backend/utils/error/csvlog.c.md`).



### MyProcPort
The Port struct for the current backend's client connection — socket, remote/local addresses, negotiated protocol/auth state, GSS/SSL info, and startup-packet parameters; the backend reads client identity from it. [verified-by-code] (`backend_startup.c:177` — via `knowledge/subsystems/tcop.md`).



### NameData
The fixed-width catalog name type: a struct wrapping `char data[NAMEDATALEN]`
(64 bytes), used for identifier columns like `relname`/`proname` so they sit at
fixed offsets in a catalog row rather than as variable-length text.
[inferred] (via `knowledge/idioms/catalog-conventions.md`).



### NAMEDATALEN
The compile-time limit (default 64, so 63 usable bytes) on the length of any
SQL identifier stored in `name`-typed catalog columns; identifiers longer than
this are truncated. [verified-by-code] (via
`knowledge/files/contrib/postgres_fdw/option.c.md`).



### NameStr
Macro yielding a `char *` view of a fixed-width `Name` (NAMEDATALEN) field; the read accessor for catalog `name`-typed columns, the counterpart of `namestrcpy` on the write side. [from-comment] (via `knowledge/files/src/pl/plpython/plpy_procedure.md`).



### namestrcpy
Copies a C string into a fixed-width `Name` (NAMEDATALEN) field, zero-padding the remainder; the safe way to set a catalog `name`-typed column. [verified-by-code] (`name.c:233` — via `knowledge/files/src/backend/utils/adt/name.c.md`).



### NestLoop
The nested-loop join plan node: for each outer-side row it scans (or re-scans)
the inner side, optionally passing the outer row's values down as
`NestLoopParam`s to drive a parameterized inner index scan. [verified-by-code]
(`plannodes.h:1006` — via
`knowledge/files/src/include/nodes/plannodes.h.md`).



### NextSampleBlock
The TABLESAMPLE method callback that returns the next heap block number to
sample for a scan (or `InvalidBlockNumber` when done); the system methods cache
state across calls so the choice is stable within one scan. `tsm_system_time`
computes it from elapsed time rather than a row target.
[verified-by-code] (via
`knowledge/files/contrib/tsm_system_time/tsm_system_time.c.md`).



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



### NoLock
The lock-mode sentinel (value 0) meaning "take no heavyweight lock"; passed to relation_open / table_open when the caller already holds a suitable lock, so the open just builds the relcache entry without re-locking. [verified-by-code] (`relation.c:65` — via `knowledge/files/src/backend/access/common/relation.c.md`).



### NullableDatum
A compact `{ Datum value; bool isnull; }` struct used to carry a
possibly-NULL value as one unit — notably the per-argument storage inside
`FunctionCallInfo`. [verified-by-code] (via `knowledge/idioms/fmgr.md`).



### NUM_BUFFER_PARTITIONS
The fixed number (128) of partitions the shared buffer-mapping hash table is
divided into, each guarded by its own `BufMappingLock`, so lookups in
different partitions don't contend. [verified-by-code] (via
`knowledge/subsystems/storage-lmgr.md`).



### NUM_LOCK_PARTITIONS
The fixed number (16) of partitions the heavyweight-lock shared hash table is
split into, each with its own LWLock, to spread contention. A backend needing
more than one partition lock must take them in partition-number order — a
deadlock-avoidance rule enforced in `CheckDeadLock`. [from-README] (via
`knowledge/files/src/backend/storage/lmgr/README.md`).



### O_NOFOLLOW
The open(2) flag that makes the call fail if the final path component is a symbolic link, used as a TOCTOU/symlink-attack defense when a privileged process opens a path an unprivileged user could influence. Several server-side file paths (file_fdw, the COPY path it shims, pg_rewind targets) have been flagged in corpus issues for *not* setting it. [inferred] (via `knowledge/files/contrib/file_fdw/file_fdw.c.md`).



### ObjectAddress
The canonical triple `(classId, objectId, objectSubId)` that uniquely names
any database object — the currency of dependency tracking, `ALTER`/`COMMENT`/
`SECURITY LABEL` routing, and DDL event collection. `objectSubId` distinguishes
a column from its table; functions returning the object they just created hand
back an `ObjectAddress`. [verified-by-code] (via
`knowledge/files/src/include/tcop/deparse_utility.h.md`).



### ObjectIdGetDatum
Macro packing an OID into a `Datum`; the `*GetDatum` member for `Oid`, used when passing a relation/type/proc OID to fmgr or syscache lookups. [verified-by-code] (via `knowledge/files/contrib/spi/moddatetime.c.md`).



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



### OidFunctionCall1
Looks up a function by OID and calls it with one argument in a single step (an fmgr_info + FunctionCall1 combination); used for handler functions like a tablesample method's, where the OID is known but not the symbol. [verified-by-code] (via `knowledge/files/src/backend/access/tablesample/tablesample.c.md`).



### OidOutputFunctionCall
Calls a type's output function (looked up by the output-proc OID) to render a Datum as a `char *`; the generic "Datum to text" step after `getTypeOutputInfo`. [verified-by-code] (via `knowledge/files/contrib/postgres_fdw/deparse.c.md`).



### OldestXmin
The computed horizon xid below which no running transaction can still see a given table's dead tuples; vacuum and HOT pruning use it to decide what is removable. [from-comment] (via `knowledge/community/user-questions/2026-06-02.md`).



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



### output_plugin
The logical-decoding extension interface: a shared library that registers callbacks (`startup`, `begin`, `change`, `commit`, …) through `OutputPluginCallbacks`, invoked by the decoder to turn WAL changes into a consumer-defined format. `test_decoding` is the in-tree example. [from-comment] (via `knowledge/files/contrib/test_decoding/test_decoding.c.md`).



### OutputPluginCallbacks
The struct of callbacks (startup / begin / change / truncate / commit / ...)
that a logical-decoding output plugin fills in from `_PG_output_plugin_init`
to receive the reordered transaction stream. [verified-by-code] (via
`knowledge/idioms/output-plugin-callbacks.md`).



### PageAddItem
The bufpage macro (a wrapper over `PageAddItemExtended`) that inserts a new item — heap tuple or index entry — into a page's line-pointer array; the heap, btree, gist, and brin AMs all build pages through it. [from-comment] (`bufpage.h:24-78` — via `knowledge/files/src/backend/storage/page/bufpage.c.md`).



### PageGetItem
The page-access macro returning a pointer to the tuple/item referenced by a given line pointer on a buffer page, the standard way AM code reads an item after `PageGetItemId`. Hardened wrappers (e.g. amcheck's `PageGetItemIdCareful`) bounds- and flag-check the line pointer first to avoid following corruption. [verified-by-code] (via `knowledge/files/contrib/amcheck/verify_nbtree.md`).



### PageGetItemId
The macro returning the `ItemId` (line pointer) for a given 1-based
`OffsetNumber` on a page — the indirection layer that lets the heap move tuples
within a page (during pruning/compaction) without changing their TIDs. Callers
pair it with `ItemIdIsValid`/`ItemIdIsNormal` before dereferencing.
[verified-by-code] (via
`knowledge/files/contrib/pageinspect/gistfuncs.c.md`).



### PageGetMaxOffsetNumber
Returns the highest valid line-pointer offset on a page (0 if empty), derived from `pd_lower`; the loop bound for scanning every item on a page. Off-by-one or unchecked use is a classic page-corruption read bug. [verified-by-code] (via `knowledge/files/contrib/pageinspect/brinfuncs.c.md`).



### PageHeaderData
The fixed header at the start of every 8 KB page: page LSN, checksum, flag
bits, the `pd_lower`/`pd_upper`/`pd_special` offsets that bound the line-pointer
array and the tuple area, and the page-size/version word. pageinspect's
`page_header()` decodes exactly these fields. [verified-by-code] (via
`knowledge/files/contrib/pageinspect/pageinspect.md`).



### PageIsNew
The predicate that reports whether a page has never been initialised
(`pd_upper == 0`), i.e. freshly extended zero-filled space. AMs detect it on
read and run their page-init routine before use; bloom does
`PageIsNew || BloomPageIsDeleted` to decide a page needs reinitialising.
[verified-by-code] (via `knowledge/files/contrib/bloom/blinsert.c.md`).



### PageSetLSN
The macro that stamps a page's LSN with the position returned by `XLogInsert`, recording that the page's latest change is durable once WAL up to that LSN is flushed; it must be set *after* `XLogInsert` returns. [from-README] (`transam/README:457-466` — via `knowledge/architecture/wal.md`).



### palloc
Context-aware memory allocation. Memory returned by `palloc` belongs to the
`CurrentMemoryContext` rather than to the caller; it can be freed individually
with `pfree` but is more usually reclaimed in bulk when its context is reset or
deleted. OOM is reported via `ereport`, never a NULL return. [from-comment]
(`palloc.h:1-9,31-52` — via
`knowledge/files/src/include/utils/palloc.h.md`).



### palloc_array
Type-safe allocation macro: `palloc_array(Type, n)` palloc's room for `n` elements of `Type`, computing the size and casting the result; the array sibling of `palloc_object`. An unbounded `n` is the allocation-DoS surface to cap at the input boundary. [verified-by-code] (via `knowledge/files/contrib/intarray/_int_gin.md`).



### PANIC
The highest ereport severity: it logs the message and then aborts the whole postmaster, forcing a crash-recovery cycle on restart; reserved for corruption that makes continuing unsafe (e.g. a failed WAL redo). [verified-by-code] (via `knowledge/files/src/backend/utils/error/elog.c.md`).



### parallel query
The execution mode in which the leader backend launches parallel worker
backends (via `dsm` + a `ParallelContext`) to run a parallel-aware portion of a
plan beneath a `Gather`. Functions are labelled parallel-safe / -restricted /
-unsafe to decide what may run in a worker. [from-comment] (via
`knowledge/files/src/backend/access/transam/parallel.c.md`).



### ParallelContext
The handle a leader backend uses to set up parallel query: it describes the
entry point, the DSM segment, and the shared state to copy to workers, and is
the object `RegisterDynamicBackgroundWorker` workers attach to.
[verified-by-code] (`parallel.h:33-50` — via
`knowledge/files/src/include/access/parallel.h.md`).



### PARAM_EXEC
The parameter kind for values passed internally within a plan at run time —
correlated-subquery references, recursive-CTE working state, and similar — as
opposed to `PARAM_EXTERN` client bind parameters. The planner assigns each a
slot id held in `PlannerInfo`. [verified-by-code] (via
`knowledge/files/src/backend/optimizer/plan/subselect.c.md`).



### ParameterStatus
The protocol message (tag 'S') by which the backend reports a GUC's value to the client — sent at startup for the reportable parameters (e.g. server_version, client_encoding, TimeZone) and again whenever one changes. [verified-by-code] (`fe-protocol3.c:183` — via `knowledge/files/src/interfaces/libpq/fe-protocol3.c.md`).



### ParamListInfo
The runtime parameter list (`params.h`) that carries external query-parameter values and types into the executor; e.g. PL/pgSQL's execstate threads one through to bind `$n` placeholders. [verified-by-code] (via `knowledge/files/src/pl/plpgsql/src/plpgsql.md`).



### parse_manifest
The frontend/common parser for the backup manifest JSON emitted by
`pg_basebackup` — it validates the file list, checksums, and WAL range, and is
consumed by `pg_verifybackup` and `pg_combinebackup`. Built on the incremental
JSON parser so a huge manifest need not be held in memory at once.
[verified-by-code] (via
`knowledge/files/src/include/common/parse_manifest.h.md`).



### ParseExprKind
The enum passed to `transformExpr` naming the syntactic context of an expression (WHERE, SELECT target, CHECK constraint, index predicate, …) so parse analysis can apply context-specific rules and error messages. [verified-by-code] (via `knowledge/files/src/include/parser/parse_expr.h.md`).



### ParseState
The working context threaded through parse analysis: it carries the range
table being built, the source query text (for error positions), parameter-type
hooks, and flags controlling what expression kinds are allowed in the current
clause. [verified-by-code] (`parse_node.h:91` — via
`knowledge/files/src/backend/parser/parse_node.c.md`).



### parseTypeString
Parses a textual type name (e.g. `numeric(10,2)`, `myschema.mytype`) into a
type OID and typmod by running it through the SQL grammar, honoring the
current search_path — a NAME-to-OID resolution point relevant to Phase-D
analysis. [verified-by-code] (`plpy_spi.c:105` — via
`knowledge/files/src/pl/plpython/plpy_plpymodule.md`).



### PartitionDesc
The cached runtime descriptor of a partitioned table's partition set: the
ordered bound info plus the child relation OIDs, built from the catalog and
attached to the relcache entry. Tuple routing and partition pruning both read
it; it is rebuilt on invalidation so concurrent ATTACH/DETACH are seen.
[verified-by-code] (via
`knowledge/files/src/include/partitioning/partdesc.h.md`).



### password_required
A postgres_fdw user-mapping option whose default (`true`) forbids non-superusers from using a mapping that would let libpq connect without a password, blocking the classic "loopback to bypass RLS / impersonate" attack. The corpus calls its two-layered enforcement (CREATE-time superuser check plus a post-connect `PQconnectionUsedPassword` cross-check) the gold standard, which file_fdw and dblink lack. [verified-by-code] (via `knowledge/files/contrib/file_fdw/file_fdw.c.md`).



### Path
The planner's representation of one candidate way to produce a relation's rows
(seqscan, indexscan, a particular join order), annotated with estimated startup
and total cost. The optimizer enumerates Paths into each `RelOptInfo`, keeps
the cheapest non-dominated ones, and turns the winner into a `Plan`.
[from-comment] (via `knowledge/subsystems/optimizer.md`).



### patternToSQLRegex
The fe_utils sibling of `processSQLNamePattern`, used by pg_amcheck and
others, that converts a shell-style object-name pattern into an anchored POSIX
regex for catalog matching. [verified-by-code] (`string_utils.c:1219` — via
`knowledge/issues/pg_amcheck.md`).



### PD_ALL_VISIBLE
The page-header flag bit asserting that every tuple on the page is visible to
all transactions; it lets sequential scans skip per-tuple visibility checks
and must stay in sync with the relation's visibility-map bit.
[verified-by-code] (via
`knowledge/files/src/backend/access/common/bufmask.c.md`).



### pd_lower
The page-header field marking the end of the line-pointer array — the low
boundary of a heap/index page's free space (free space runs from `pd_lower` up
to `pd_upper`). WAL full-page-image compression can omit the hole between the
two when `pd_lower`/`pd_upper` are set correctly. [verified-by-code] (via
`knowledge/files/src/include/storage/bufpage.h.md`).



### performDeletion
The dependency-aware object-drop driver: given an `ObjectAddress` it walks `pg_depend`, collects everything that must go, honours `RESTRICT`/`CASCADE`, and deletes the whole set in dependency order. Backs `DROP` and temp-namespace cleanup. [verified-by-code] (via `knowledge/files/src/backend/catalog/dependency.c.md`).



### PerformWalRecovery
The xlogrecovery.c driver that runs the main redo loop after `InitWalRecovery` has decided between crash, archive, and standby recovery, replaying records up to the consistency/recovery target. [from-comment] (via `knowledge/files/src/backend/access/transam/xlogrecovery.c.md`).



### pg_amop
The system catalog identifying the operators associated with each index operator family/class; one row per operator, marked as a search operator or an ordering operator by `amoppurpose`, with its strategy number. The planner consults it to decide which operators an index can satisfy. [from-comment] (via `knowledge/files/src/include/catalog/pg_amop.h.md`).



### pg_any_to_server
The encoding-conversion routine that converts a client-supplied string from the
current client_encoding to the server (database) encoding, applying the
registered conversion procedure and rejecting invalidly-encoded input. Its
inverse is `pg_server_to_any`. [verified-by-code] (via
`knowledge/files/contrib/pgcrypto/pgp-pgsql.md`).



### PG_ARGISNULL
Macro a SQL-callable C function uses to test whether argument N was passed SQL NULL before touching it; mandatory for non-strict functions, since `PG_GETARG_*` on a NULL arg yields garbage. [verified-by-code] (via `knowledge/files/src/backend/utils/adt/misc.c.md`).



### pg_atomic_uint64
The 64-bit atomic integer type from `port/atomics.h`, touched only through `pg_atomic_read_u64`/`pg_atomic_write_u64`/`pg_atomic_compare_exchange_u64` etc.; used for lock-free counters and packed state words such as the buffer descriptor's `state`. [verified-by-code] (via `knowledge/files/src/include/storage/buf_internals.h.md`).



### pg_attribute
The system catalog with one row per table/index/view column, covering user attnums (1..relnatts) plus the negative system attnums; its initial contents are generated at compile time by genbki.pl (there is no `pg_attribute.dat`). It records each column's type, length, alignment, not-null, defaults flags, and dropped status. [from-comment] (via `knowledge/files/src/include/catalog/pg_attribute.h.md`).



### pg_auth_members
The cluster-wide system catalog recording role-membership edges (member → role) created by `GRANT role TO role`, with grantor and the admin/inherit/set option flags. Privilege resolution (`has_privs_of_role`, `is_member_of_role`) walks it; the INHERIT-vs-SET distinction is what makes the two checks differ. [verified-by-code] (via `knowledge/files/src/include/catalog/pg_auth_members.h.md`).



### pg_authid
The cluster-wide (`BKI_SHARED_RELATION`) system catalog storing one row per role, including role attributes (superuser, login, createrole, replication) and the hashed `rolpassword` column. `pg_shadow` and `pg_group` are now views over it; the password column is why it is readable only by superusers. [from-comment] (via `knowledge/files/src/include/catalog/pg_authid.h.md`).



### pg_b64_decode
Decodes base64 input into a caller-supplied buffer, rejecting invalid characters and returning the decoded length or -1 on overflow; the inverse of `pg_b64_encode`, shared by frontend and backend. [verified-by-code] (`base64.c:115` — via `knowledge/files/src/common/base64.c.md`).



### pg_b64_encode
Encodes a byte buffer into base64 into a caller-supplied destination, returning the encoded length or -1 on overflow; the shared encoder behind SCRAM, GSSAPI, and `encode(…, 'base64')`. [verified-by-code] (`base64.c:48` — via `knowledge/files/src/common/base64.c.md`).



### pg_basebackup
The client tool that takes a physical base backup of a running cluster over the replication protocol (`BASE_BACKUP` command), writing either a plain extracted directory tree or one tar per tablespace. It can stream WAL in parallel via a forked background process so the backup is self-consistent on restore. [verified-by-code] (via `knowledge/files/src/bin/pg_basebackup/pg_basebackup.c.md`).



### PG_BINARY
The platform file-open flag (0 on Unix, `O_BINARY` on Windows) OR'd into
`open`/`OpenTransientFile` calls to suppress text-mode CRLF translation so
byte streams are read verbatim. [from-comment] (via
`knowledge/files/contrib/file_fdw/file_fdw.c.md`).



### pg_buffercache
The contrib extension exposing the shared-buffer pool's contents as SQL — one row per buffer with its relfilenode, fork, block number, usage count, and pin count — plus, in newer versions, eviction helpers. It is the standard way to inspect what is cached without attaching a debugger. [verified-by-code] (via `knowledge/files/contrib/pg_buffercache/pg_buffercache_pages.c.md`).



### pg_catalog
The schema holding all built-in system catalogs, types, functions, and operators; it is implicitly first on every backend's effective `search_path`, so built-in names resolve before user objects of the same name. Security-sensitive code (e.g. postgres_fdw remote sessions) forces `search_path = pg_catalog` to avoid user-object shadowing. [from-comment] (via `knowledge/files/contrib/postgres_fdw/connection.c.md`).



### PG_CATCH
The cleanup arm of a `PG_TRY` block, entered only when an `ereport(ERROR)`
longjmps out of the guarded code. It runs with the error still pending, so
after releasing whatever the try-block acquired it must re-raise the error via
`PG_RE_THROW`. [from-comment] (via `knowledge/idioms/error-handling.md`).



### pg_checksum_page
Computes the 16-bit data checksum of an 8 KB page from its contents and block number — the block number is folded in so a page written to the wrong place is detected — compared against the stored `pd_checksum` on read when checksums are enabled. [verified-by-code] (via `knowledge/files/contrib/pageinspect/pageinspect.md`).



### pg_class
The central system catalog with one row per relation (table, index, view, sequence, composite type, TOAST table, materialized view), holding relkind, relfilenode, reltuples/relpages stats, and access-method/ownership links. Most pg_class rows are written from `heap.c` (`InsertPgClassTuple`, `AddNewRelationTuple`) and many fields are maintained by inplace update. [verified-by-code] (via `knowledge/files/src/backend/catalog/pg_class.c.md`).



### pg_collation
The system catalog with one row per collation, recording its provider (libc / ICU / builtin), `collcollate`/`collctype`, encoding, and whether it is deterministic. `CollationCreate` writes the rows for CREATE COLLATION; locale changes to the underlying provider can silently invalidate stored ordering. [verified-by-code] (via `knowledge/files/src/backend/catalog/pg_collation.c.md`).



### pg_combinebackup
The tool that reconstructs a full backup from a chain of incremental backups plus their full base, reading each backup's manifest to assemble the final data directory (and pulling missing WAL from an archive via `restore_command` when needed). It underpins PostgreSQL's incremental-backup feature. [verified-by-code] (via `knowledge/files/src/fe_utils/archive.c.md`).



### pg_compress_specification
The parsed representation of a compression method plus its options (e.g.
`gzip:9`, `zstd:level=3,long`), produced by `parse_compress_specification` and
consumed by the streaming-compression (`astreamer`) and backup code. It
normalizes the `method:detail` syntax used across `pg_basebackup`/`pg_dump`.
[verified-by-code] (via `knowledge/files/src/fe_utils/astreamer_zstd.c.md`).



### pg_conflict_detection
A PG18 internal replication slot (a reserved slot name) that holds back the
xid horizon on a logical-replication subscriber so it can detect
update/delete conflicts against rows a concurrent transaction may have changed.
Created when `retain_dead_tuples` / conflict tracking is enabled. [verified-by-code]
(via `knowledge/files/src/backend/replication/logical/worker.c.md`).



### pg_control
The cluster control file (`global/pg_control`) — not a heap relation, but documented as the `ControlFileData` struct: it records the catalog/control version, system identifier, latest checkpoint location and `CheckPoint` body, `DBState`, and WAL/block layout constants. A torn or stale control file blocks startup; `pg_resetwal` rewrites it as a last resort. [from-comment] (via `knowledge/files/src/include/catalog/pg_control.h.md`).



### pg_controldata
Both a CLI and a set of SQL functions (`pg_control_checkpoint/system/init/recovery`) that read and pretty-print `$PGDATA/global/pg_control` — the control version, system identifier, latest checkpoint, and WAL/block layout. It is the read-only inspection counterpart to the rarely-used `pg_resetwal`. [verified-by-code] (via `knowledge/files/src/backend/utils/misc/pg_controldata.c.md`).



### pg_cryptohash_create
Allocates and initialises a cryptographic-hash context (MD5/SHA-*) over either the built-in or the OpenSSL backend; each call palloc's a context, so hot callers should reuse one. Paired with `pg_cryptohash_free`. [verified-by-code] (via `knowledge/files/contrib/uuid-ossp/uuid-ossp.c.md`).



### pg_cryptohash_free
Frees a `pg_cryptohash_ctx` created by `pg_cryptohash_create`, releasing the underlying OpenSSL/built-in state; must be called even on the error path to avoid leaking the context. [verified-by-code] (via `knowledge/files/src/backend/utils/adt/cryptohashfuncs.c.md`).



### pg_database
The cluster-wide (`BKI_SHARED_RELATION`) system catalog with one row per database, holding its name, owner, encoding, locale provider, collation/ctype, connection limit, allow-connections flag, and frozen-xid horizons. The shared nature is why database creation and `datfrozenxid` advancement are cluster-global concerns. [from-comment] (via `knowledge/files/src/include/catalog/pg_database.h.md`).



### pg_db_role_setting
The system catalog backing `ALTER ROLE/DATABASE ... SET`, with one row per (database, role) pair holding the GUC settings applied at session start for that combination (either is zero for a role-wide or database-wide default). Session startup applies these before the connection is handed to the client. [inferred] (via `knowledge/files/src/include/catalog/pg_db_role_setting.h.md`).



### pg_depend
The system catalog recording dependencies between database objects (one row per dependency edge), so DROP can detect what would break and CASCADE can follow the graph. This file does low-level row CRUD; the actual graph traversal lives in `dependency.c`. [from-comment] (via `knowledge/files/src/backend/catalog/pg_depend.c.md`).



### pg_dump
The per-database logical dump driver: from a single connection it collects schema and data, orders objects by their dependency graph, and emits either plain SQL or an archive (custom/directory/tar) for `pg_restore`. It is the largest single C file in `bin/pg_dump` and the canonical "trust the source database" boundary in the corpus. [verified-by-code] (via `knowledge/files/src/bin/pg_dump/pg_dump.c.md`).



### pg_dumpall
The client driver that dumps cluster-wide state not covered by a single-database `pg_dump`: roles (`pg_authid`/`pg_roles`), tablespaces, role memberships, and per-role GUC settings, then invokes `pg_dump` for each database. Because it dumps role definitions it can emit password hashes, so its output is sensitive. [verified-by-code] (via `knowledge/files/src/bin/pg_dump/pg_dumpall.c.md`).



### pg_enum
The system catalog with one row per enum-type label, holding the owning type, the label text, and a sort-order float; it backs CREATE TYPE AS ENUM and ALTER TYPE ADD VALUE. Adding a value mid-transaction uses an "uncommitted enum" mechanism so the new OID is usable only where it is visible. [verified-by-code] (via `knowledge/files/src/backend/catalog/pg_enum.c.md`).



### pg_fatal
The frontend (client-program) fatal-error helper: it prints a formatted error
message to stderr and exits the process. It is the libpq-side analogue of a
backend `ereport(FATAL, …)` and appears throughout `pg_dump`, `pg_basebackup`,
and the `fe_utils` code. [verified-by-code] (via
`knowledge/files/src/fe_utils/archive.c.md`).



### pg_file_create_mode
The permission mask (`PG_FILE_MODE_OWNER`, 0600, relaxed to 0640 under group access) the server and frontend tools apply when creating files in the data directory; one of the three `pg_*_create_mode` globals forming the cluster's permission boundary. [verified-by-code] (`file_perm.c:19` — via `knowledge/files/src/common/file_perm.c.md`).



### PG_FINALLY
The unconditional-cleanup arm of a `PG_TRY` block (an alternative to
`PG_CATCH`); its body runs on both the normal and the error path, with the
pending error re-thrown automatically afterward on the error path.
[from-comment] (via `knowledge/idioms/error-handling.md`).



### pg_foreign_server
The system catalog with one row per foreign server (CREATE SERVER), tying a server name to its foreign-data wrapper, type/version, owner, and option array; user mappings and foreign tables reference it. FDWs read its options when establishing a remote connection. [from-comment] (via `knowledge/files/src/include/catalog/pg_foreign_server.h.md`).



### PG_FREE_IF_COPY
The fmgr cleanup macro that frees a detoasted/aligned copy of a varlena argument only if `PG_GETARG_*_P` actually made one (i.e. the pointer differs from the original toast datum), avoiding both leaks and double-frees. Functions that detoast bytea/text arguments are expected to pair each argument with it before returning. [verified-by-code] (via `knowledge/files/contrib/pgcrypto/pgp-pgsql.md`).



### PG_FUNCTION_ARGS
The macro spelling the fixed signature of every fmgr-callable C function — `(FunctionCallInfo fcinfo)` — so all SQL-callable functions share one calling convention. Argument access (`PG_GETARG_*`, `PG_ARGISNULL`) and result return (`PG_RETURN_*`) macros all operate on the implicit `fcinfo` it introduces. [from-comment] (via `knowledge/idioms/fmgr.md`).



### PG_FUNCTION_INFO_V1
The macro every dynamically-loaded C function must use to emit the `Pg_finfo`
record that tells the fmgr its calling convention is the version-1
(Datum-based) ABI. [verified-by-code] (`fmgr.h:40` — via
`knowledge/idioms/fmgr.md`).



### pg_get_viewdef
The ruleutils function reconstructing a view's defining SELECT (or a rule's action) as SQL text from its stored parse tree, used by `\d`/`psql` and pg_dump. The corpus notes it does not re-emit `WITH (security_barrier/security_invoker/check_option)` view options, so callers relying on it alone can silently lose those clauses. [verified-by-code] (via `knowledge/files/src/backend/utils/adt/ruleutils.c.md`).



### PG_GETARG_INT32
Macro fetching call argument N as a 32-bit int inside a `PG_FUNCTION_ARGS` function (a `DatumGetInt32(PG_GETARG_DATUM(n))`); the per-type argument accessor family backing fmgr v1 functions. [verified-by-code] (via `knowledge/files/contrib/dict_int/dict_int.c.md`).



### pg_index
The system catalog with one row per index, complementing the index's own pg_class row with the indexed key columns, expression/predicate trees, uniqueness/exclusion flags, and the validity/ready/live state bits that drive concurrent index builds. The planner and executor read it to decide and execute index access. [from-comment] (via `knowledge/files/src/include/catalog/pg_index.h.md`).



### pg_init_privs
The system catalog snapshotting the "initial" ACL of objects as of initdb (for system objects) or CREATE EXTENSION (for extension-owned objects), so pg_dump can emit only the *delta* between current and initial privileges rather than re-granting defaults. [from-comment] (via `knowledge/files/src/include/catalog/pg_init_privs.h.md`).



### PG_KEYWORD
The macro used in `kwlist.h` (and PL keyword lists) to declare a SQL keyword
together with its token value and category; each includer redefines the
macro to build a different table from the one shared list.
[verified-by-code] (via `knowledge/files/src/pl/plpgsql/src/pl_kwlists.md`).



### pg_largeobject_metadata
The system catalog with one row per large object, holding its owner and ACL, separate from `pg_largeobject` which stores the object's data in 2 KB chunks. It exists so large objects can have ownership and privileges independent of their byte storage. [inferred] (via `knowledge/files/src/include/catalog/pg_largeobject_metadata.h.md`).



### pg_locale_t
The opaque handle bundling a collation's locale provider (libc, ICU, or
builtin) with its provider-specific data, returned by `pg_newlocale_from_collation`
and threaded through every locale-sensitive comparison, case-folding, and
formatting routine. [verified-by-code] (via
`knowledge/files/src/backend/utils/adt/pg_locale.c.md`).



### pg_locks
The system view exposing the lock manager's currently held and awaited locks — one row per (lock, holder) — covering relation, tuple, transaction, page, and advisory locks. It exposes per-tuple LOCKTAG detail (block + offset) to unprivileged users, which the corpus flags as a monitoring-as-extraction surface. [verified-by-code] (via `knowledge/files/contrib/pgrowlocks/pgrowlocks.c.md`).



### pg_logical_emit_message
The function that writes a logical-decoding message (transactional or not) into
WAL via the `RM_LOGICALMSG_ID` resource manager, letting extensions inject
custom payloads that output plugins can read during decoding. It is the basis
for application-level signalling over logical replication. [verified-by-code]
(via `knowledge/files/src/backend/access/rmgrdesc/logicalmsgdesc.c.md`).



### pg_lzcompress
PostgreSQL's built-in LZ-family compressor (`pglz`), the default TOAST
compression method and the codec behind `pglz_compress`/`pglz_decompress`. It is
simple and dependency-free; `lz4`/`zstd` are the optional alternatives selected
per-column via `SET STORAGE`/`default_toast_compression`. [verified-by-code]
(via `knowledge/files/src/include/common/pg_lzcompress.h.md`).



### pg_malloc
The frontend `malloc` wrapper (`fe_memutils.c`) that aborts with an out-of-memory message on failure, giving client programs and `libpgcommon` code backend-style "allocation never returns NULL" semantics without a memory context. [verified-by-code] (via `knowledge/files/src/common/fe_memutils.c.md`).



### pg_md5_encrypt
The backend helper that produces the `md5<hex>` shadow-password string by
hashing password+username; retained for the legacy `md5` authentication method
even though SCRAM is now preferred. Found alongside the SCRAM verifier code in
the password-encryption path. [verified-by-code] (via
`knowledge/files/src/backend/libpq/crypt.c.md`).



### PG_MODULE_MAGIC
The macro a loadable C module must place at file scope so the server can
compare an ABI/version fingerprint at load time and refuse `.so` files built
against an incompatible major version. [verified-by-code] (via
`knowledge/idioms/fmgr.md`).



### pg_monitor
A predefined (bootstrap) role that grants read access to privileged monitoring
views and functions — including parts of `pg_stat_*`, `pgstattuple`, and other
statistics that are otherwise superuser-only. Granting it avoids handing out
superuser for monitoring. [verified-by-code] (via
`knowledge/files/contrib/pgstattuple/pgstatindex.c.md`).



### pg_multixact
The SLRU subsystem (and `pg_multixact/` directory, split into `offsets` and `members`) storing the membership of each MultiXactId — which transactions share-lock a tuple and with what status. Like the clog it is subject to wraparound and is truncated by vacuum past the cluster's oldest multixact horizon. [verified-by-code] (via `knowledge/files/src/backend/access/transam/slru.c.md`).



### pg_namespace
The system catalog with one row per schema; `NamespaceCreate` writes its tuples for CREATE SCHEMA. This file is only the catalog-row I/O — the search-path resolution machinery that maps unqualified names to namespaces lives in `namespace.c`. [from-comment] (via `knowledge/files/src/backend/catalog/pg_namespace.c.md`).



### pg_node_tree
The built-in pseudo-type used to store a serialized parse/plan Node tree as text in catalogs (column defaults, check constraints, index expressions, rule actions, view queries). It has no SQL input function for users — values are produced by the backend's nodeToString and read back via stringToNode. [verified-by-code] (via `knowledge/files/src/backend/utils/adt/pseudotypes.c.md`).



### pg_noreturn
The PG18 portability macro placed on functions that never return (they
`ereport(ERROR)`/`exit`/`abort`), replacing the older `pg_attribute_noreturn()`;
it expands to C11 `[[noreturn]]` or a compiler attribute so the optimizer and
static analyzers know control does not come back. [verified-by-code] (via
`knowledge/files/contrib/pgcrypto/px.md`).



### pg_opclass
The system catalog with one row per (access method, operator-class name, schema) operator class — the named bundle that ties an input data type to the operators and support functions an index AM uses. Each opclass belongs to an operator family (`pg_opfamily`) and may be the default for its type. [from-comment] (via `knowledge/files/src/include/catalog/pg_opclass.h.md`).



### pg_operator
The system catalog with one row per operator, recording its name, left/right argument types, result type, the implementing function, and commutator/negator links (resolved via shell-operator forward references when needed). `OperatorCreate` is the CREATE OPERATOR backend and records the dependencies. [verified-by-code] (via `knowledge/files/src/backend/catalog/pg_operator.c.md`).



### pg_parse_json
The JSON lexer/parser driver that tokenizes input and invokes a
`JsonSemAction` callback table, used both by the `json`/`jsonb` input functions
and by ad-hoc internal consumers (manifest parsing, statistics import). The
same parser supports incremental (chunked) parsing. [verified-by-code] (via
`knowledge/files/src/backend/utils/adt/jsonb.c.md`).



### pg_prng
PostgreSQL's process-local pseudo-random generator, implementing Blackman & Vigna's xoroshiro128** (a small, fast 128-bit-state PRNG) behind `pg_prng_*` calls on a global state. It is explicitly **not** cryptographically strong — security-sensitive randomness must use `pg_strong_random` instead. [verified-by-code] (`pg_prng.c:5-11` — via `knowledge/files/src/common/pg_prng.c.md`).



### pg_proc
The system catalog with one row per function, procedure, and aggregate (the latter pairs with `pg_aggregate`), holding language, argument/return types, volatility, parallel-safety, cost, and the function body or symbol. `ProcedureCreate` is the universal entry used by CREATE FUNCTION/PROCEDURE/AGGREGATE/OPERATOR. [verified-by-code] (via `knowledge/files/src/backend/catalog/pg_proc.c.md`).



### pg_publication
The system catalog (with `pg_publication_rel` and `pg_publication_namespace`) defining logical-replication publications — the set of tables/schemas and the operations published. `pg_publication.c` is the C API behind CREATE/ALTER PUBLICATION and the publishability predicates walsender consults. [verified-by-code] (via `knowledge/files/src/backend/catalog/pg_publication.c.md`).



### PG_RE_THROW
The macro that re-raises the in-flight error from inside a `PG_CATCH` block
after cleanup, longjmp-ing control to the next outer `PG_TRY` handler (or to
the top-level abort if none). [verified-by-code] (via
`knowledge/idioms/error-handling.md`).



### pg_read_server_files
A predefined (built-in) role granting its members the right to read arbitrary server-side files through SQL-reachable facilities (`COPY FROM`, file_fdw, `pg_read_file`, the basebackup file APIs). Several corpus issues note it as a broad capability whose grantees can reach data outside any single relation's ACLs. [verified-by-code] (via `knowledge/files/contrib/file_fdw/file_fdw.c.md`).



### pg_receivewal
The standalone client that connects in replication mode and streams WAL segments to a local directory (optionally managing a replication slot), used as a low-latency archive substitute or to feed an external consumer. It writes complete segments and can fsync/compress them. [verified-by-code] (via `knowledge/files/src/bin/pg_basebackup/pg_receivewal.c.md`).



### pg_replslot
The data-directory subdirectory holding one durable state file per replication
slot (`state.dat`), persisting each slot's `restart_lsn`, `xmin`/`catalog_xmin`,
and plugin name across restarts. The slot manager fsyncs these on checkpoint and
on graceful shutdown. [verified-by-code] (via
`knowledge/files/src/backend/replication/slot.c.md`).



### pg_restore
The client driver that reads a `pg_dump` archive (custom/directory/tar format — not plain SQL, which is `psql`'s job) and either prints its table of contents or replays a selected, dependency-ordered subset into a target database. Selective restore and parallel restore are driven from the archive TOC. [verified-by-code] (via `knowledge/files/src/bin/pg_dump/pg_restore.c.md`).



### pg_rewind
The tool that resynchronizes a diverged former primary with a new primary by copying only the blocks that changed since their histories split, far cheaper than a fresh base backup. Its header exposes the shared config and the helpers spanning `parsexlog.c`, `filemap.c`, and `timeline.c`. [verified-by-code] (via `knowledge/files/src/bin/pg_rewind/pg_rewind.h.md`).



### pg_rewrite
The system catalog with one row per rewrite rule (CREATE RULE), holding the rule's event type, enable flag, INSTEAD flag, optional WHEN qualification, and the action query tree; its primary key is `(ev_class, rulename)`. The rewriter expands these rules — including the ON SELECT rule that backs every view — between parse and plan. [from-comment] (via `knowledge/files/src/include/catalog/pg_rewrite.h.md`).



### pg_seclabel
The system catalog storing `SECURITY LABEL` assignments for per-database objects, one row per (object, provider), so multiple label providers (e.g. sepgsql plus a custom one) can coexist on the same object via the `provider` column. Shared/global objects use `pg_shseclabel`. [from-comment] (via `knowledge/files/src/include/catalog/pg_seclabel.h.md`).



### pg_shdepend
The cluster-wide system catalog recording dependencies on *shared* objects (roles, tablespaces, databases) — e.g. that a role owns or has privileges on objects in some database. It is the only dependency catalog keyed by both `dbid` and the local object, so DROP ROLE/OWNED BY can find references across all databases. [verified-by-code] (via `knowledge/files/src/backend/catalog/pg_shdepend.c.md`).



### pg_stat_activity
The system view exposing one row per server process with its state, current/last query text, wait event, and client/application identity. Because the query and `application_name` fields can carry user-influenced strings, several corpus issues flag it as an extraction/spoofing surface. [verified-by-code] (via `knowledge/files/contrib/postgres_fdw/option.c.md`).



### pg_stat_statements
The contrib extension that hooks the planner, executor, and ProcessUtility paths to aggregate per-(userid, dbid, queryid, toplevel) call counts and planning/execution/buffer/WAL metrics, normalizing literals into a canonical query text. It is near-ubiquitous in production; the corpus flags that with `track_utility=on` it can capture cleartext passwords from `CREATE/ALTER ... PASSWORD`. [verified-by-code] (via `knowledge/files/contrib/pg_stat_statements/pg_stat_statements.c.md`).



### pg_statistic
The system catalog holding per-(relation, attribute, inheritance) column statistics produced by ANALYZE — null fraction, average width, n-distinct, and slot-encoded most-common-values/histogram/correlation arrays. The planner reads it (via the `pg_stats` view and selectivity estimators) to cost paths; its contents can be sensitive (MCV leakage). [from-comment] (via `knowledge/files/src/include/catalog/pg_statistic.h.md`).



### pg_strcasecmp
PostgreSQL's locale-independent ASCII case-insensitive string compare, used for keyword/option matching so behaviour does not shift with the server locale (unlike libc `strcasecmp`). [verified-by-code] (`px-crypt.c:165` — via `knowledge/files/contrib/pgcrypto/px-crypt.md`).



### pg_strdup
The frontend `strdup` wrapper that aborts on OOM; the string-duplicating member of the `pg_malloc`/`pg_realloc`/`pg_strdup` frontend allocation family. [verified-by-code] (via `knowledge/files/src/common/fe_memutils.c.md`).



### pg_strong_random
The portability wrapper generating cryptographically-secure random bytes (from OpenSSL or the OS CSPRNG), used for SCRAM salts and nonces, query-cancel keys, RADIUS authenticators, and `gen_random_uuid()`. It is the strong counterpart to the non-cryptographic `pg_prng`. [verified-by-code] (via `knowledge/files/src/port/pg_strong_random.c.md`).



### pg_subtrans
The SLRU subsystem (and `pg_subtrans/` directory) mapping each subtransaction XID to its immediate parent XID, letting visibility checks walk up to the top-level transaction. Readers consult it because once a subxid is no longer cached in `MyProc`, the parent link lives only here. [verified-by-code] (via `knowledge/files/src/backend/access/transam/varsup.c.md`).



### pg_tablespace
The system catalog with one row per tablespace, mapping a tablespace OID to its on-disk location. This catalog file is tiny — just the directory-existence check used by CREATE TABLESPACE; the substantive tablespace logic lives in `commands/tablespace.c`. [from-comment] (via `knowledge/files/src/backend/catalog/pg_tablespace.c.md`).



### pg_tblspc
The data-directory subdirectory of symlinks, one per non-default tablespace,
pointing at the external storage location; base backups must recreate these
links (or remap them via `--tablespace-mapping`) when restoring. [verified-by-code]
(via `knowledge/files/src/fe_utils/astreamer_file.c.md`).



### pg_trigger
The system catalog with one row per trigger (including system-generated constraint triggers), recording the firing function, BEFORE/AFTER/INSTEAD timing, ROW/STATEMENT level, the triggering events, and any column list or WHEN qualification. The executor reads it to build a relation's trigger descriptor. [from-comment] (via `knowledge/files/src/include/catalog/pg_trigger.h.md`).



### PG_TRY
The opening macro of PostgreSQL's structured exception-handling idiom; it
establishes a sigsetjmp landing pad so a later `ereport(ERROR)` longjmps back
here instead of unwinding the C stack by hand. It pairs with `PG_CATCH`
(cleanup on the error path) or `PG_FINALLY` (cleanup on both paths) and a
closing `PG_END_TRY`. [verified-by-code] (`elog.h:242` — via
`knowledge/idioms/error-handling.md`).



### pg_type
The system catalog with one row per data type (base, composite, domain, enum, range, multirange, array, pseudo), recording length, by-value-ness, alignment, storage, the input/output/send/receive functions, and the element/array links. `TypeCreate` is the universal type-row writer; `TypeShellMake` creates the forward-reference shell for mutually-recursive types. [verified-by-code] (via `knowledge/files/src/backend/catalog/pg_type.c.md`).



### pg_unreachable
A macro marking a code point the compiler should treat as never reached (after an exhaustive `switch` or a `noreturn` call); it expands to a compiler builtin in production and to `Assert(false)` under `--enable-cassert`. Omitting it after a full switch is a common style nit. [from-comment] (via `knowledge/files/contrib/pg_plan_advice/pgpa_walker.c.md`).



### pg_upgrade
The tool that performs an in-place major-version upgrade by dumping only the old cluster's schema, restoring it into the new cluster, then copying/linking/cloning the relation files and fixing the xid/multixact/oid counters — avoiding a full dump+reload of the data. Its `main()` is a linear pipeline with no dispatch table. [verified-by-code] (via `knowledge/files/src/bin/pg_upgrade/pg_upgrade.c.md`).



### pg_usleep
The portable microsecond-sleep helper used inside the backend (e.g. lock-retry
backoff, the `auth_delay` extension, vacuum delays). It is interruptible by
signals and is the standard way backend C code waits a short, fixed interval.
[verified-by-code] (via `knowledge/files/contrib/auth_delay/auth_delay.c.md`).



### pg_wal
The cluster subdirectory holding the write-ahead log segment files (and `pg_wal/archive_status`), formerly named `pg_xlog`. WAL is written here first and only later applied to data files; archiving and streaming replication both read from it, and unbounded retention here (e.g. an abandoned slot) can fill the filesystem. [inferred] (via `knowledge/files/contrib/pg_walinspect/pg_walinspect.c.md`; see `knowledge/architecture/wal.md`).



### pg_waldump
The CLI that decodes and prints WAL records from segment files for debugging, using each resource manager's rmgrdesc routine to render record contents. The contrib `pg_walinspect` extension is its in-process, SQL-callable counterpart. [verified-by-code] (via `knowledge/files/contrib/pg_walinspect/pg_walinspect.c.md`).



### pg_wchar
PostgreSQL's wide-character representation and the multibyte-encoding abstraction layer (`pg_wchar.h`) providing per-encoding character-length, validation, and conversion routines (`pg_mblen`, `pg_mbstrlen`, verifymbstr). All encoding-aware text processing routes through it rather than assuming single-byte characters. [verified-by-code] (via `knowledge/files/contrib/ltree/ltree_io.c.md`).



### pg_xact
The cluster subdirectory (and SLRU) storing transaction commit/abort status — two bits per transaction id — formerly named `pg_clog`. Visibility checks consult it via `TransactionIdDidCommit`, but only *after* `TransactionIdIsInProgress`, because `xact.c` records commit in pg_xact before clearing `MyProc->xid`. [from-comment] (via `knowledge/files/src/backend/access/heap/heapam_visibility.c.md`).



### PGC_POSTMASTER
The most restrictive `GucContext`: a variable so marked can only be set at
server start (command line or `postgresql.conf` read by the postmaster) and
cannot be changed by reload or `SET`. [verified-by-code] (via
`knowledge/idioms/guc-variables.md`).



### PGC_SIGHUP
The GUC context level for parameters that can be changed at server reload
(SIGHUP) but not per-session — they may be set in `postgresql.conf` and take
effect on `pg_reload_conf()`, but `SET` rejects them. One of the `GucContext`
values that gates where each GUC is settable. [verified-by-code] (via
`knowledge/idioms/guc-variables.md`).



### PGC_SUSET
The GUC context level for settings that only a superuser (or a role granted
`SET` on them) may change at run time within a session — e.g. pgcrypto's
`pgcrypto.builtin_crypto_enabled`. It sits between `PGC_SIGHUP` (config-file
only) and `PGC_USERSET` (any user) in the privilege ladder. [verified-by-code]
(via `knowledge/files/contrib/pgcrypto/pgcrypto.md`).



### PGC_USERSET
The GUC context level marking a parameter any user may change at any time
within a session (the most permissive level); the context constrains who may
`SET` the variable and when. [verified-by-code] (`guc.h:71-80` — via
`knowledge/idioms/guc-variables.md`).



### PGDATA
The data directory — the filesystem root of a database cluster holding base/, global/, pg_wal/, the config files, and PG_VERSION. Also the environment variable / -D option naming it, consulted by initdb, the postmaster, and every standalone tool. [verified-by-code] (via `knowledge/files/src/bin/initdb/initdb.c.md`).



### PgFdwRelationInfo
The `fdw_private` struct postgres_fdw attaches to every base/join/upper `RelOptInfo` it plans, caching pushdown decisions, remote conditions, cost estimates, and the user mapping for that relation. [verified-by-code] (via `knowledge/files/contrib/postgres_fdw/postgres_fdw.h.md`).



### PGPROC
The per-process shared-memory slot describing a backend to the rest of the
system. Every backend is assigned exactly one `PGPROC` from
`ProcGlobal->allProcs` at startup and returns it to a freelist at exit; it
holds the proc's wait state, LSNs, and lock links, and is how other backends
find and signal it. [verified-by-code] (`proc.h:184` — via
`knowledge/files/src/include/storage/proc.h.md`).



### PinBuffer
Increments a buffer's pin count (and bumps its usage count) so the clock-sweep
cannot evict it while a backend holds a reference; every buffer access must
pin before touching the page. [verified-by-code] (`bufmgr.c:3280-3372` — via
`knowledge/files/src/backend/storage/buffer/bufmgr.c.md`).



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



### PlannerGlobal
The planner's per-statement global state, shared across all subquery levels of one planning run — it accumulates the final range table, the relations and PlanInvalItems the plan depends on, subplans, and parallel-safety flags that go into the finished PlannedStmt. [verified-by-code] (via `knowledge/subsystems/optimizer.md`).



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



### pnstrdup
Duplicates at most n bytes of a string into palloc'd memory and NUL-terminates the copy; the length-bounded `pstrdup`, used to detach a substring from a larger buffer. [verified-by-code] (`dict_int.c:93,96` — via `knowledge/files/contrib/dict_int/dict_int.c.md`).



### PointerGetDatum
The macro that packages a C pointer as a `Datum` for return or argument
passing through fmgr — the encoding side of by-reference value passing (its
inverse is `DatumGetPointer`). It performs no copy: the pointed-to value must
outlive the `Datum`, so callers are careful about memory-context lifetime.
[from-comment] (via `knowledge/files/src/include/postgres.h.md`).



### portal
The backend-local object holding the execution state of a single query or
cursor — its plan, parameters, and memory contexts — between bind and the
fetching of results. Portals are created under `TopPortalContext` (e.g. by
`CreateNewPortal`) and torn down when the statement completes or the cursor
closes. [verified-by-code] (`portalmem.c:237` — via
`knowledge/files/src/backend/utils/mmgr/portalmem.c.md`).



### PortalContext
The memory context holding the executable state of the currently active portal
(cursor / query). It is made the current context while a portal runs, so
per-execution allocations are reclaimed when the portal is dropped.
[verified-by-code] (via `knowledge/subsystems/utils-mmgr.md`).



### PortalDrop
Tears down a portal: it removes the portal from the portal hash table early
(so abort-retry is idempotent) and then releases its resources and memory
context. [verified-by-code] (`portalmem.c:516` — via
`knowledge/subsystems/utils-mmgr.md`).



### PortalRun
The tcop entry point that executes a portal (a named, runnable query container)
and routes its result tuples to a `DestReceiver`. The extended-query and simple-
query paths both funnel through it; `PortalRun(FETCH_ALL, dest)` drains a portal
to completion. [verified-by-code]
(via `knowledge/files/src/backend/tcop/postgres.c.md`).



### PortalStart
The step that readies a portal for execution after planning: it chooses the
execution strategy, creates the executor state (for an optimizable query), and
pushes the active snapshot, before `PortalRun` pulls tuples.
[verified-by-code] (`pquery.c:430` — via `knowledge/subsystems/tcop.md`).



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



### PostmasterContext
The memory context holding data needed only during startup (e.g. the parsed
pg_hba/pg_ident configuration). A freshly forked backend deletes it once it no
longer needs that startup-only data. [verified-by-code]
(`postgres.c:4388-4391` — via `knowledge/subsystems/tcop.md`).



### PostmasterMain
The postmaster's top-level setup routine — parses options, creates shared memory and semaphores, opens the listen sockets, and enters ServerLoop to accept connections and fork a backend per client. [verified-by-code] (via `knowledge/subsystems/main.md`).



### pq_beginmessage
Starts composing a wire-protocol message: it initialises the `StringInfo` buffer and stashes the message-type byte, to be finished by `pq_endmessage` which prepends the length. The send-side framing primitive in `pqformat.c`. [verified-by-code] (`pqformat.c:87` — via `knowledge/files/src/backend/libpq/pqformat.c.md`).



### pq_getmsgint
Reads a big-endian integer of the given width from an incoming protocol message buffer, advancing the cursor and erroring on underrun; the receive-side counterpart of `pq_sendint*`, used by type receive functions. [verified-by-code] (via `knowledge/files/src/backend/libpq/pqformat.c.md`).



### pq_getmsgtext
The wire-protocol read helper that pulls a counted string out of an incoming
`StringInfo` message buffer and converts it from client to server encoding,
used while parsing protocol messages and certain binary `recv` functions.
[verified-by-code] (via `knowledge/files/contrib/ltree/ltree_io.c.md`).



### pq_sendint32
Appends a 32-bit integer in network byte order to an outgoing message `StringInfo`; the send-side primitive a binary-output (send) function uses, e.g. emitting a count followed by its elements. [verified-by-code] (via `knowledge/files/src/backend/libpq/pqformat.c.md`).



### PrepareToInvalidateCacheTuple
The catcache helper that, given a changed catalog tuple, computes which
catcache entries (by cache id and hash) must be invalidated, feeding the
invalidation machinery. [verified-by-code] (via
`knowledge/files/src/backend/utils/cache/catcache.c.md`).



### primary_conninfo
The standby-side GUC holding the libpq connection string the walreceiver uses to
reach the primary for streaming replication; `pg_basebackup -R` and
`recovery_gen` write it into the generated `postgresql.auto.conf`/standby
signal setup. [verified-by-code] (via
`knowledge/files/src/fe_utils/recovery_gen.c.md`).



### proc_exit
The backend's orderly-exit routine: it runs all registered `on_proc_exit` and
`before_shmem_exit` callbacks (releasing shared resources, detaching shmem) in
LIFO order, then calls `exit()`. Backend cleanup hangs off it rather than off
raw `exit`. [verified-by-code] (via
`knowledge/files/src/backend/storage/ipc/ipc.c.md`).



### ProcArray
The shared-memory array of pointers to active backends' `PGPROC`s, used to take
snapshots (which xids are in-progress), compute the oldest visible xid, and
find backends to signal. `GetSnapshotData` walks it under `ProcArrayLock`.
[from-comment] (via `knowledge/files/src/backend/storage/ipc/procarray.c.md`).



### ProcArrayEndTransaction
Clears a backend's XID from the shared ProcArray at transaction end — the step
that makes the transaction's effects visible to others; all FATAL exit paths
must reach it so the proc slot does not linger. [verified-by-code] (via
`knowledge/files/src/backend/utils/init/postinit.c.md`).



### ProcArrayLock
The LWLock guarding the `ProcArray` (the set of live `PGPROC`s). Snapshot
building takes it SHARED (`GetSnapshotData`); transaction commit/abort and
backend exit take it EXCLUSIVE to update visibility. Its contention is a known
scalability pressure point. [verified-by-code] (`procarray.c:2170` — via
`knowledge/subsystems/storage-ipc.md`).



### processSQLNamePattern
The fe_utils routine that turns a psql `\d`-style name pattern into SQL
WHERE-clause conditions against the catalogs, safely quoting the literal
pieces. It is the single chokepoint that makes `\d*` pattern matching
injection-safe across psql and pg_dump. [verified-by-code] (via
`knowledge/files/src/fe_utils/string_utils.c.md`).



### ProcessUtility
The dispatch point for non-optimizable statements — DDL, transaction control,
COPY, VACUUM, and the like — that bypass the planner/executor. It is the
canonical hook target (`ProcessUtility_hook`) for extensions wanting to
intercept commands. [verified-by-code] (`utility.c:504` — via
`knowledge/subsystems/tcop.md`).



### ProcessUtility_hook
The hook point through which extensions intercept utility (non-optimizable)
statements; `ProcessUtility` dispatches down the hook chain and ultimately to
`standard_ProcessUtility`. [verified-by-code] (`utility.c:548` — via
`knowledge/files/src/backend/tcop/utility.c.md`).



### ProcGlobal
The shared `PROC_HDR` structure anchoring all `PGPROC`s: the `allProcs` array
plus the per-class free lists (regular, autovacuum, bgworker, walsender) and
cache-friendly mirrored arrays of xids/status flags scanned during snapshot
building. [verified-by-code] (`proc.h:444` — via
`knowledge/files/src/backend/storage/lmgr/proc.c.md`).



### ProcNumber
A backend's dense 0-based index into the shared PGPROC and proc arrays (the modern successor to "backend id"); used as a lease-holder identity, e.g. the `acquired_by` of a replication-origin session. [verified-by-code] (via `knowledge/files/src/include/replication/origin.h.md`).



### ProcSignalBarrier
The mechanism for forcing every backend to process a global state change
(e.g. relmapper or smgr invalidation) before the initiator proceeds: the
emitter bumps a generation counter, signals all backends via `ProcSignal`, and
waits until each has absorbed the barrier. [verified-by-code] (via
`knowledge/files/src/backend/storage/ipc/procsignal.c.md`).



### ProcSleep
The lock-manager primitive that puts a backend to sleep on its PGPROC
semaphore while it waits for a heavyweight lock, after `JoinWaitQueue` has
inserted it into the lock's wait queue. It wakes on the deadlock-timeout
SIGALRM (re-checking `got_deadlock_timeout`) or when `ProcWakeup` grants the
lock. [verified-by-code] (`proc.c:1348` — via
`knowledge/files/src/backend/storage/lmgr/proc.c.md`).



### ProcState
The per-backend slot in the sinval shared array (`sinvaladt.c`) tracking that backend's read position in the shared-invalidation message ring; a reader updates its own slot under a shared lock. [verified-by-code] (via `knowledge/files/src/backend/storage/ipc/sinvaladt.c.md`).



### ps_status
The process-title machinery (`set_ps_display`, `init_ps_display`) that updates
what `ps`/`top` show for each backend — typically the current command and the
client identity. When `update_process_title` is on (the Unix default) it can
leak SQL text, including literal passwords, to any local user. [verified-by-code]
(via `knowledge/files/src/include/utils/ps_status.h.md`).



### pstrdup
Duplicates a NUL-terminated string into the current memory context via palloc; the context-aware `strdup` whose result is freed automatically at context reset (or on an ereport longjmp). [verified-by-code] (via `knowledge/files/contrib/sepgsql/selinux.c.md`).



### PushActiveSnapshot
Pushes a snapshot onto the backend's active-snapshot stack so it becomes what "the current command" sees; paired with PopActiveSnapshot, it scopes visibility around each executed command and is tracked by the snapshot manager. [verified-by-code] (via `knowledge/files/src/backend/utils/time/snapmgr.c.md`).



### PushFilter / PullFilter
pgcrypto's streaming I/O abstraction: a `PushFilter` chain transforms bytes on
the way out (encrypt, compress) and a `PullFilter` chain transforms them on the
way in (decrypt, decompress), each stage wrapping the next. The PGP compression
code adapts zlib `deflate`/`inflate` as filter stages this way. [from-comment]
(via `knowledge/files/contrib/pgcrypto/pgp-compress.md`).



### px_memset
pgcrypto's indirection over `memset` (through a volatile function pointer) used to scrub key/secret buffers so the compiler cannot optimise the wipe away; e.g. `clear_and_pfree` wipes a `text` before freeing it. [verified-by-code] (via `knowledge/files/contrib/pgcrypto/pgp-pgsql.md`).



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



### query_planner
The core of the optimizer that, given the FROM-clause relations and join
restrictions, builds base-relation `RelOptInfo`s and runs join-order search to
produce the cheapest join `RelOptInfo`; `grouping_planner` wraps it to add
grouping/aggregation/sort/limit on top. [verified-by-code] (via
`knowledge/subsystems/optimizer.md`).



### QueryDesc
The "bag of everything" the executor needs to run one query — plan tree, snapshot, dest receiver, params, instrumentation — constructed by tcop/SPI/SQL-functions and passed to `ExecutorStart`/`Run`/`End`. [from-comment] (via `knowledge/files/src/include/executor/execdesc.h.md`).



### QueryEnvironment
The per-query container for objects that exist only for the duration of a
query but aren't in the catalog — most notably ephemeral named relations (the
transition tables a statement-level trigger sees). `create_queryEnv()`
`palloc0`s one and the parser/executor consult it to resolve such names.
[verified-by-code] (via
`knowledge/files/src/backend/utils/misc/queryenvironment.c.md`).



### queryjumble
The query-normalization machinery that walks a parse tree, substitutes constants
with placeholders, and computes a stable `queryId` hash so different literal
values collapse to one entry. It is what `pg_stat_statements` and
`compute_query_id` group statistics by. [verified-by-code] (via
`knowledge/files/src/include/nodes/queryjumble.h.md`).



### QueryRewrite
The top entry of the rule-rewriter: it takes a single parse-analysed `Query`
and returns a list of Querys after applying ON SELECT (view expansion) and
non-SELECT rules, re-acquiring locks on rewritten range-table entries. It is the
stage between parse-analysis and planning. [verified-by-code]
(`rewriteHandler.c:4780-4870` — via
`knowledge/files/src/backend/rewrite/rewriteHandler.c.md`).



### quote_identifier
The routine that returns a SQL identifier, double-quoting it only when necessary
(it contains uppercase/special characters or collides with a reserved keyword).
It is what `pg_dump`, `ruleutils`, and `format('%I', …)` rely on to emit safe,
round-trippable identifiers. [verified-by-code] (via
`knowledge/files/src/backend/utils/adt/quote.c.md`).



### quote_literal_cstr
Returns a SQL string literal (single-quoted, with embedded quotes/backslashes escaped) for a C string; the safe way to interpolate a value into dynamically-built SQL, used by trigger code generating statements. [verified-by-code] (via `knowledge/files/contrib/spi/refint.c.md`).



### RangeTblEntry
A range-table entry (RTE): one element of a query's rtable describing a relation, subquery, join, function, CTE, or values-scan the query references; expression nodes name columns by (rtindex, attno) into this list. [verified-by-code] (`nodes/parsenodes.h:1137` — via `knowledge/subsystems/parser-and-rewrite.md`).



### RangeTblEntry (RTE)
A range-table entry: the parse/plan-tree node describing one relation reference
in a query's FROM clause — a table, subquery, join, function, or CTE. Its
`rtekind` discriminates the variant, and other query nodes refer to RTEs by a
1-based range-table index (`varno`) rather than by pointer. [verified-by-code]
(`parsenodes.h:1137` — via
`knowledge/files/src/include/nodes/parsenodes.h.md`).



### RangeType
The varlena on-disk representation of a single range value (lower/upper bounds plus flag byte); a multirange is parsed and assembled as an array of `RangeType`. [verified-by-code] (via `knowledge/files/src/backend/utils/adt/multirangetypes.c.md`).



### RangeVarGetRelid
The namespace.c routine resolving a `RangeVar` (possibly schema-qualified name) to a relation OID, optionally taking a lock and running a callback before the lock to guard against concurrent rename/drop. [verified-by-code] (via `knowledge/files/src/backend/catalog/namespace.c`-derived doc, `knowledge/files/src/pl/plpgsql/src/pl_comp.md`).



### raw_parser
The first parser stage: it runs the flex scanner and bison grammar over a query string and returns a list of raw parse trees (`RawStmt`), before any catalog lookup or semantic analysis. PL/pgSQL installs hooks around it so it can recognize and substitute its own variable references during compilation. [from-comment] (via `knowledge/files/src/pl/plpgsql/src/pl_comp.md`).



### RawStmt
The grammar-output wrapper around one raw (un-analyzed) parse-tree statement,
carrying its byte offsets within the query string. The rewriter/analyzer
consumes a list of `RawStmt`s, one per statement in a multi-command string.
[verified-by-code] (`nodes/parsenodes.h:2187` — via
`knowledge/subsystems/parser-and-rewrite.md`).



### read_stream
The high-level streaming-read API (`read_stream.h`/`.c`) that most callers use instead of the raw AIO interface: a caller supplies a callback yielding a sequence of block numbers, and the stream issues lookahead/prefetch reads and hands back pinned buffers in order. It is the PG18-era replacement for ad-hoc `ReadBuffer` loops in sequential and bitmap scans. [verified-by-code] (via `knowledge/files/src/backend/storage/aio/read_stream.c.md`).



### ReadBuffer
The canonical bufmgr entry that returns a pinned buffer for a given relation/fork/block, reading it from storage on a cache miss; the foundation under `ReadBufferExtended`/`StartReadBuffers`. [verified-by-code] (via `knowledge/files/src/backend/storage/buffer/bufmgr.c.md`).



### ReadBufferExtended
The general buffer-read entry point taking an explicit fork number and
read-mode (`RBM_NORMAL`, `RBM_ZERO_ON_ERROR`, …), used when the plain
`ReadBuffer` defaults don't fit — e.g. reading the visibility-map fork or
tolerating a torn page. It returns a pinned `Buffer`; the caller still must
`LockBuffer` for content access. [verified-by-code] (via
`knowledge/files/contrib/pageinspect/pageinspect.md`).



### ReadBufferWithoutRelcache
A buffer-read entry point that takes an explicit `RelFileLocator`/fork rather
than an open `Relation`, for code paths that have no relcache entry — recovery
redo, and cross-database or bootstrap reads. It returns a pinned buffer like
`ReadBuffer` but bypasses the smgr lookup through the relcache.
[verified-by-code] (`bufmgr.c:818-1031` — via
`knowledge/files/src/backend/storage/buffer/bufmgr.c.md`).



### ReadyForQuery
The protocol message (tag 'Z') the backend sends at the end of each message-processing cycle to signal it is idle and report transaction status (idle / in-transaction / failed); the client may then send its next query. [verified-by-code] (via `knowledge/architecture/query-lifecycle.md`).



### ReceiveSharedInvalidMessages
The inval.c routine that pulls pending shared-invalidation messages from the sinval queue and applies each via a callback, falling back to `InvalidateSystemCaches` when the queue has overflowed; driven by `AcceptInvalidationMessages`. [verified-by-code] (via `knowledge/files/src/backend/utils/cache/inval.c.md`).



### record_recv
The binary-input function for the generic `record`/composite pseudo-type: it
reads a wire-format tuple (column count, then per-column OID + length + binary
datum) and reconstructs a `HeapTuple`/`Datum`. The counterpart to `record_send`.
[verified-by-code] (via `knowledge/files/contrib/hstore/hstore_io.c.md`).



### recordDependencyOn
Inserts one `pg_depend` row recording that a dependent object depends on a referenced object with a given `deptype`; the single write primitive every higher-level dependency-recording helper funnels through. [verified-by-code] (via `knowledge/files/src/backend/catalog/pg_depend.c.md`).



### RecordTransactionCommit
The routine that makes a transaction durable: it snapshots pending invalidation
messages, writes (and flushes, per `synchronous_commit`) the commit WAL record,
and marks the xid committed in CLOG — strictly before sinval broadcast so other
backends never see the commit before its catalog effects. [from-comment]
(`inval.c:30` — via `knowledge/files/src/backend/utils/cache/inval.c.md`).



### RecoveryInProgress
The cheap check that returns true while the server is still replaying WAL
(crash or archive/standby recovery) and has not yet reached a consistent,
read-write state. Many operations gate on it — e.g. a transaction notes
`startedInRecovery` so it knows it ran read-only against a standby snapshot.
[verified-by-code] (via
`knowledge/files/src/backend/access/transam/xact.c.md`).



### RedoRecPtr
The cached WAL position from which recovery would start (the latest
checkpoint's redo point); `GetRedoRecPtr` exposes it and it gates whether a
page change needs a full-page image. [verified-by-code] (`xlog.c:6937` — via
`knowledge/files/src/backend/access/transam/xlog.c.md`).



### REGBUF_WILL_INIT
The `XLogRegisterBuffer` flag declaring that redo will re-initialize the
page from scratch, so the record need not carry the page's prior contents
and full-page-image logging is suppressed for it. [verified-by-code] (via
`knowledge/subsystems/access-nbtree.md`).



### RegisterCustomRmgr
The rmgr.c API (`rmgr.c:107`) an extension calls at load time to claim a custom `RmgrId` and install its `RmgrData` callback table, so its WAL records can be replayed and described. [verified-by-code] (`rmgr.c:107` — via `knowledge/files/src/backend/access/transam/rmgr.c.md`).



### RegisterDynamicBackgroundWorker
The runtime API a backend calls to ask the postmaster to start a background
worker on the fly (as opposed to `RegisterBackgroundWorker` at shared_preload
time), optionally learning the worker's PID through a
`BackgroundWorkerHandle`. [verified-by-code] (`bgworker.h:69-75` — via
`knowledge/idioms/bgworker-and-parallel.md`).



### RegisterSnapshot
Bumps a snapshot's reference count and tracks it under the active resource
owner so it survives past the call that took it; `UnregisterSnapshot` releases
it. Callers that stash a snapshot (cursors, held portals, long-lived scans) must
register it or risk it being recycled out from under them. [from-comment] (via
`knowledge/files/src/backend/utils/time/snapmgr.c.md`).



### relation
The internal name for any table-like object (table, index, sequence,
materialized view, composite type) — anything with a `pg_class` row and a
relfilenode. The in-memory `RelationData`/`Relation` handle caches a relation's
catalog metadata, tuple descriptor, and access-method routines. [from-README]
(via `knowledge/idioms/catalog-conventions.md`).



### relation_close
Drops the reference (and optionally the lock) on a relcache entry opened with `relation_open`; `table_close`/`index_close`/`sequence_close` all forward to it. [verified-by-code] (via `knowledge/files/src/backend/access/common/relation.c.md`).



### relation_open
Takes the requested lock then resolves a relcache entry via `RelationIdGetRelation`, asserting that some lock is held when `lockmode == NoLock` (outside bootstrap); the low-level open that `table_open`/`index_open` build on. [verified-by-code] (`relation.c:47` — via `knowledge/files/src/backend/access/common/relation.c.md`).



### RelationBuildDesc
Builds a `RelationData` entry from the catalogs on a relcache miss; it runs
under a recursion-and-retry guard (`InProgressEnt`) so invalidations arriving
mid-build are handled correctly. [verified-by-code] (`relcache.c:166` — via
`knowledge/files/src/backend/utils/cache/relcache.c.md`).



### RelationData
The in-memory relation descriptor (`Relation`) cached by the relcache — one
per open relation, keyed by OID and built on demand from
`pg_class`/`pg_attribute`/etc. — holding everything the executor needs about a
table or index. [verified-by-code] (`relcache.c:10` — via
`knowledge/files/src/backend/utils/cache/relcache.c.md`).



### RelationGetBufferForTuple
The heap-insertion helper that picks (or extends to) a page with room for a new
tuple: it tries the relation's cached target block, consults the FSM, and may
extend the relation, returning a pinned, exclusively-locked buffer. It also
encodes the two-buffer lock-ordering rule used by cross-page UPDATE.
[from-comment] (`hio.c:500` — via
`knowledge/files/src/include/access/hio.h.md`).



### RelationGetDescr
The macro returning a relation's `TupleDesc` (`rel->rd_att`) — the column
layout used to form and deform tuples. amcheck-style invariants compare a
tuple's stored attribute count against `RelationGetDescr(rel)->natts`.
[verified-by-code] (via `knowledge/files/contrib/amcheck/verify_heapam.md`).



### RelationGetIndexList
Returns the list of index OIDs on a relation from the relcache (cached and refreshed on invalidation); the starting point for code that must consider every index, e.g. building a change-notification payload or planning index maintenance. [verified-by-code] (via `knowledge/files/contrib/tcn/tcn.c.md`).



### RelationGetNumberOfBlocks
Returns the current block count of a relation fork by asking smgr (`smgrnblocks`); the upper bound for any block-scanning loop and a value that can grow under concurrent extension. [verified-by-code] (via `knowledge/files/contrib/pageinspect/btreefuncs.c.md`).



### RelationGetRelationName
Macro returning the `char *` name of a relation from its cached `pg_class` form; handy for error messages, often combined with `psprintf` to build a string without pre-sizing a buffer. [verified-by-code] (via `knowledge/files/src/common/psprintf.c.md`).



### RelationPutHeapTuple
Places an already-prepared heap tuple onto a target buffer page during insert
and stamps the tuple's `t_self` with the resulting TID. [verified-by-code]
(via `knowledge/files/src/backend/access/heap/heapam.c.md`).



### relcache (relation cache)
The per-backend cache of `RelationData` entries, so opening a frequently-used
table doesn't re-read its `pg_class`/`pg_attribute`/index metadata each time. It
is kept coherent by shared-invalidation messages and can be rebuilt in place to
preserve pointer identity. [from-comment] (via
`knowledge/files/src/backend/utils/cache/relcache.c.md`).



### ReleaseBuffer
Drops one pin on a shared or local buffer without touching its content lock; the unpin half of the pin/unpin discipline, called once per `ReadBuffer` to let the buffer become evictable again. [verified-by-code] (via `knowledge/files/contrib/pgstattuple/pgstatapprox.c.md`).



### ReleaseCurrentSubTransaction
The xact.c routine that commits the current internal subtransaction (the success path of a PL/pgSQL `BEGIN ... EXCEPTION` block); its rollback counterpart is `RollbackAndReleaseCurrentSubTransaction`. [verified-by-code] (via `knowledge/files/src/pl/plpgsql/src/pl_exec.md`).



### ReleaseSysCache
The mandatory release call that pairs with every non-Copy `SearchSysCache*` hit; skipping it leaks the pin and raises a "cache reference leak" warning at transaction end. [verified-by-code] (via `knowledge/idioms/catalog-conventions.md`).



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



### RelFileNumber
The integer that names a relation's on-disk file within its tablespace/
database — the "relfilenode" portion of a `RelFileLocator`, distinct from the
relation's catalog OID so that `TRUNCATE`/`VACUUM FULL`/rewrites can swap
storage without changing the OID. `pg_upgrade` preserves these explicitly via
`binary_upgrade_next_heap_pg_class_relfilenumber`. [verified-by-code] (via
`knowledge/files/src/include/catalog/binary_upgrade.h.md`).



### RelOptInfo
The planner's per-relation bookkeeping node: for each base or join relation it
accumulates candidate `Path`s, row/width estimates, and available columns. Join
planning combines smaller `RelOptInfo`s into larger ones until the whole join
tree has a cheapest Path. [from-comment] (via
`knowledge/subsystems/optimizer.md`).



### relptr
A "relative pointer" — an offset stored relative to a known base address rather
than an absolute pointer — so a structure living in a shared or relocatable
memory region (e.g. the freepage manager, DSA) stays valid regardless of where
each process maps the region. [verified-by-code] (via
`knowledge/files/src/include/utils/relptr.md`).



### RELSEG_SIZE
The build-time number of blocks per physical segment file (default 131072,
i.e. 1 GB at 8 kB blocks); a relation larger than one segment is stored as
`<relfilenode>`, `.1`, `.2`, ... files. [verified-by-code] (via
`knowledge/files/src/backend/storage/file/buffile.c.md`).



### reorder buffer
The logical-decoding component that buffers each in-progress transaction's
change stream and replays it, in commit order, to the output plugin only once
the transaction commits — turning the interleaved physical WAL back into
per-transaction logical change sets. Large transactions can spill to disk.
[from-comment] (via
`knowledge/files/src/backend/replication/logical/reorderbuffer.c.md`).



### ReorderBuffer
The logical-decoding component that reassembles interleaved WAL changes into per-transaction, commit-ordered streams, spilling large transactions to disk and replaying them at commit (or streaming them for in-progress decoding). [verified-by-code] (via `knowledge/files/src/include/replication/reorderbuffer.h.md`).



### ReorderBufferChange
A single decoded WAL event (insert/update/delete/message/...) buffered inside logical decoding; changes are accumulated per `ReorderBufferTXN` and replayed to the output plugin in commit order. [verified-by-code] (via `knowledge/files/src/backend/replication/logical/reorderbuffer.c.md`).



### ReorderBufferTXN
The per-xid container inside the reorder buffer holding a transaction's decoded `ReorderBufferChange`s plus bookkeeping (commit time, base snapshot, subtxns, invalidation messages); one exists per in-flight top-level or sub transaction. [verified-by-code] (via `knowledge/files/src/include/replication/reorderbuffer.h.md`).



### repalloc
Resizes a palloc'd chunk in the current memory context, preserving contents and returning the (possibly moved) pointer; throws on OOM like palloc. The grow primitive behind dynamic buffers such as `StringInfo` and `mbuf`. [verified-by-code] (via `knowledge/files/contrib/pgcrypto/mbuf.md`).



### replication slot
A named, persistent server-side marker that records how far a consumer
(physical standby or logical subscriber) has confirmed receiving WAL, so the
primary retains the WAL (and, for logical, the catalog xmin) that consumer still
needs. Slots prevent premature WAL removal at the cost of unbounded retention if
a consumer disappears. [from-comment] (via
`knowledge/files/src/backend/replication/slot.c.md`).



### ReplicationSlotRelease
Detaches the current backend from the replication slot it has acquired (clears active_pid and the in-memory acquired state) without dropping the slot, so the slot's retained-WAL and xmin guarantees persist for the next consumer. [verified-by-code] (via `knowledge/subsystems/replication.md`).



### ReplOriginId
The compact 2-byte identifier for a replication origin (the node that produced a change); stored alongside commit timestamps in pg_commit_ts and stamped on WAL commit records so logical replication can avoid re-applying its own changes. [verified-by-code] (`commit_ts.c:55-59` — via `knowledge/files/src/backend/access/transam/commit_ts.c.md`).



### ReScan
The executor's restart operation: `ExecReScan(node)` cooperatively resets a plan-subtree's state so it can be re-evaluated (e.g. for the inner side of a nested loop or a correlated subplan), reusing already-built structures where possible. [verified-by-code] (via `knowledge/subsystems/executor.md`).



### ResetLatch
Clears a process latch's set flag so a subsequent `WaitLatch` will block until
newly signalled; it asserts the caller owns the latch and must be called
before re-checking the work condition to avoid lost wakeups.
[verified-by-code] (`latch.c:374-388` — via
`knowledge/subsystems/storage-ipc.md`).



### ResolveRecoveryConflictWithSnapshot
The standby-side routine called during WAL redo (btree delete/vacuum, heap prune, …) that cancels read-only queries whose snapshot predates a record's `snapshotConflictHorizon`, so the cleanup the record describes can be applied. [verified-by-code] (via `knowledge/files/src/backend/access/nbtree/nbtxlog.c.md`).



### ResourceOwner
The per-scope bookkeeper that records the buffers, relcache pins, catcache
references, locks, and files a (sub)transaction or portal acquired, so they can
all be released deterministically at commit/abort even on error. New owners nest
under a parent. [from-comment] (`pl_handler.c:223` — via
`knowledge/files/src/pl/plpgsql/src/pl_handler.md`).



### restart_lsn
The replication-slot field marking the oldest WAL location the slot still requires, so the server must retain WAL from this point forward; advancing consumers move it forward and free older segments. A stalled or abandoned slot pins `restart_lsn`, causing unbounded WAL retention. [verified-by-code] (via `knowledge/files/src/backend/replication/walsender.c.md`; see `knowledge/subsystems/replication.md`).



### restore_command
The recovery configuration command that fetches an archived WAL segment (or other fixed-size file) by shelling out to an operator-supplied command string; archive recovery and `pg_combinebackup` use it to pull WAL that is no longer present locally. Its shell-interpolation of `%f`/`%p` is a long-standing injection-surface caveat. [verified-by-code] (via `knowledge/files/src/fe_utils/archive.c.md`).



### RestoreArchive
The pg_restore core routine that walks a parsed archive's table-of-contents
and replays each entry's SQL/data into the target database (or a script); it
is also reused in a special mode to build the tar format's `restore.sql`.
[from-comment] (via `knowledge/files/src/bin/pg_dump/pg_backup_tar.c.md`).



### RestoreArchivedFile
Runs the `restore_command` to fetch a WAL segment (or other archived file)
from the archive into pg_wal during recovery, validating the result before
use. [verified-by-code] (`xlogarchive.c:55` — via
`knowledge/files/src/backend/access/transam/xlogarchive.c.md`).



### RestrictInfo
The planner's wrapper around a single qualification clause, caching derived facts — referenced relids, selectivity estimates, whether it is a mergejoinable/hashable equality, pushed-down vs join clause — so the optimizer evaluates a clause's properties once and reuses them across candidate paths. [verified-by-code] (via `knowledge/files/src/backend/optimizer/util/restrictinfo.c.md`).



### ResultRelInfo
The executor's per-target-relation state for INSERT/UPDATE/DELETE/MERGE — the open relation, index lists, trigger info, RETURNING projection, and ON CONFLICT helpers; partitioned targets build one per touched leaf via `ExecInitPartitionInfo`. [verified-by-code] (via `knowledge/subsystems/executor.md`).



### RewriteQuery
The rule-rewriter driver that applies INSTEAD/ALSO rules and view expansion to
a parse-analyzed `Query`, potentially producing several result queries from
one input. [verified-by-code] (`rewriteHandler.c:4044` — via
`knowledge/subsystems/parser-and-rewrite.md`).



### rmgr (resource manager)
A WAL resource manager: each subsystem that emits WAL (heap, btree, transaction
commit, …) registers a record-type id and callbacks (notably `rm_redo`) in the
global `RmgrTable[RM_MAX_ID + 1]`. Recovery dispatches each WAL record to its
rmgr's redo function to replay the change. [verified-by-code] (`rmgr.c`
`RmgrTable` — via `knowledge/files/src/backend/access/transam/rmgr.c.md`).



### RmgrData
The eight-callback table a resource manager registers (via `RegisterCustomRmgr` for custom rmgrs) so that WAL replay, identification, and `pg_waldump` description dispatch on its `RmgrId`. [from-docs] (via `knowledge/docs-distilled/wal-for-extensions.md`).



### RmgrId
The `uint8` resource-manager identifier (built from `rmgrlist.h`) tagging every WAL record so redo, description, and identification dispatch to the right rmgr; helper macros distinguish builtin from custom ids. [verified-by-code] (via `knowledge/files/src/include/access/rmgr.h.md`).



### RmgrTable
The static dispatch table mapping each resource-manager id (RM_HEAP_ID, RM_XLOG_ID, …) to its rmgr callbacks (redo, desc, identify, startup, cleanup); WAL replay indexes it by a record's rmid to find the redo routine. [verified-by-code] (`rmgr.c:50` — via `knowledge/subsystems/access-transam.md`).



### RollbackAndReleaseCurrentSubTransaction
Aborts the current subtransaction and pops it, the C-level primitive behind PL
exception blocks and `plpy.subtransaction()`/SPI subxact rollback.
[verified-by-code] (`plpy_spi.c:447-539` — via
`knowledge/files/src/pl/plpython/plpy_spi.md`).



### RowDescription
The protocol message (tag 'T') that precedes result rows, describing each result column's name, table/column OID, type OID, typmod, and format code; printtup builds it from the query's TupleDesc. [verified-by-code] (via `knowledge/files/src/backend/access/common/printtup.c.md`).



### RowExclusiveLock
The table lock level taken by ordinary INSERT/UPDATE/DELETE (and by catalog
DML such as `performDeletion` opening `pg_depend`); it conflicts with schema
changes but not with other writers. [verified-by-code] (via
`knowledge/files/src/backend/catalog/dependency.c.md`).



### RTE_RELATION
The range-table-entry kind denoting a plain base relation (table, matview,
etc.), as opposed to subquery/join/function RTEs; the planner routes it to
`set_plain_rel_pathlist` to build scan paths. [verified-by-code]
(`allpaths.c:834` — via `knowledge/subsystems/optimizer.md`).



### RTE_SUBQUERY
The range-table-entry kind for a sub-SELECT appearing in a query's FROM clause;
its `subquery` field holds the nested `Query`. It is one of the RTEKind values
(`RTE_RELATION`, `RTE_SUBQUERY`, `RTE_FUNCTION`, `RTE_VALUES`, …) that classify
every entry in a query's range table. [verified-by-code] (via
`knowledge/files/src/backend/parser/parse_relation.c.md`).



### SaltedPassword
In SCRAM, `PBKDF2-HMAC-SHA-256(password, salt, iterations)` — the iterated
hash from which the client/server keys derive. libpq computes it once during
authentication and keeps it in the SCRAM state for reuse when verifying the
server signature. [verified-by-code] (`fe-auth-scram.c:792-797` — via
`knowledge/files/src/interfaces/libpq/fe-auth-scram.c.md`).



### SASL
Simple Authentication and Security Layer — the RFC 4422 challenge/response framework PostgreSQL's wire protocol uses to carry SCRAM exchanges; the backend drives the mechanism through a pg_be_sasl_mech vtable. [verified-by-code] (`auth-sasl.c:50` — via `knowledge/files/src/backend/libpq/auth-sasl.c.md`).



### saslprep
The SASLprep (RFC 4013 / stringprep) normalization applied to UTF-8 passwords
before SCRAM hashing, so visually-equivalent Unicode inputs hash identically.
The backend applies it when storing a SCRAM verifier; mismatched client/server
normalization would otherwise break authentication. [verified-by-code] (via
`knowledge/files/src/include/common/saslprep.h.md`).



### ScalarArrayOpExpr
The expression node for `scalar op ANY/ALL (array)` (the parsed form of
`IN (...)` and `= ANY (array)`): it holds the per-element operator, a
`useOr` flag distinguishing ANY from ALL, and the left/right argument
expressions. The planner can turn it into an index scan or a hashed lookup;
fmgr special-cases its arg at `fmgr.c:1925-1931`. [verified-by-code] (via
`knowledge/files/src/backend/utils/fmgr/fmgr.c.md`).



### ScanKey
One element of the comparison-predicate array an index scan is opened with: a
(attribute, strategy/operator, comparison value) triple, optionally flagged for
NULL handling or `ScalarArrayOp`. AMs preprocess the `ScanKey[]` to drop
redundant or contradictory clauses before scanning. [from-comment] (via
`knowledge/files/src/backend/access/nbtree/nbtpreprocesskeys.c.md`).



### ScanKeyData
The struct describing one index/heap scan qualification — a
(strategy number, comparison function, attribute number, argument) tuple plus
flag bits (e.g. `SK_ISNULL`, `SK_SEARCHNULL`). `ScanKeyInit` fills one in, and
AMs evaluate an array of them to decide which tuples match.
[verified-by-code] (via `knowledge/files/src/include/access/skey.h.md`).



### ScanKeyInit
Initialises a `ScanKeyData` in place from an attribute number, a strategy
number, a comparison `RegProcedure`, and an argument `Datum` — the standard way
to build the qual array handed to an index or heap scan. Because the function is
looked up by OID, callers must pass a trusted comparison proc.
[verified-by-code] (via `knowledge/files/src/include/access/valid.h.md`).



### ScanKeywordList
The generated lookup table (`gen_keywordlist.pl` emits `*_d.h`) consumed by `ScanKeywordLookup`: a sorted offset array plus a packed value blob plus per-keyword token/category data. [from-comment] (via `knowledge/files/src/pl/plpgsql/src/pl_kwlists.md`).



### ScanKeywordLookup
The binary-search routine that maps an identifier to a keyword token using a generated `ScanKeywordList` (an offset table plus a packed value blob); it is shared by the backend lexer and PL/pgSQL. [from-comment] (via `knowledge/subsystems/parser-and-rewrite.md`).



### SCRAM
Salted Challenge Response Authentication Mechanism (SCRAM-SHA-256, RFC 7677) — PostgreSQL's default password authentication; the server stores a salted, iterated verifier and proves knowledge without the cleartext password crossing the wire, run inside the SASL exchange. [verified-by-code] (`auth-scram.c:481` — via `knowledge/files/src/backend/libpq/auth-scram.c.md`).



### scram_common
The shared SCRAM-SHA-256 constants and primitives (salted-password derivation,
client/server keys, channel-binding tags) used by both the backend verifier and
the libpq client, keeping the two sides of the challenge-response in agreement.
[verified-by-code] (via
`knowledge/files/src/include/common/scram-common.h.md`).



### search_path
The session GUC listing the schemas, in order, that unqualified object names resolve against (plus the implicit `pg_catalog` first and an optional temp schema). It is a recurring security concern: SECURITY DEFINER functions and remote FDW sessions pin it (e.g. `SET search_path = pg_catalog`) to prevent object-shadowing attacks. [verified-by-code] (via `knowledge/files/contrib/postgres_fdw/connection.c.md`).



### SearchSysCache
The primary entry point for a syscache lookup by key, returning a reference-
counted `HeapTuple` (or a cached negative entry meaning "no such row" so the
miss is not re-scanned). Callers must `ReleaseSysCache` the result.
[verified-by-code] (`catcache.c:1621` — via
`knowledge/subsystems/utils-cache.md`).



### SearchSysCache1
Looks up a single-key catalog tuple through the syscache (the cached catalog reader), returning a HeapTuple that must be released with ReleaseSysCache; the numbered variants (…1/…2/…3/…4) take that many key columns. [verified-by-code] (via `knowledge/idioms/catalog-conventions.md`).



### SearchSysCacheExists
The existence-test family of syscache lookups (`SearchSysCacheExists1`…) that
returns a boolean without materializing or pinning the tuple — cheaper than
`SearchSysCache` + `ReleaseSysCache` when only "does a row exist" matters.
[verified-by-code] (`syscache.c:13` — via
`knowledge/files/src/backend/utils/cache/syscache.c.md`).



### SearchSysCacheExists1
Tests existence of a catalog row by a single key through the syscache without returning the tuple (no `ReleaseSysCache` needed); the cheap "does this OID still exist?" probe, e.g. inside `try_relation_open`. [verified-by-code] (`relation.c:88` — via `knowledge/files/src/backend/access/common/relation.c.md`).



### SearchSysCacheLocked1
A syscache lookup variant that also takes a lock on the found catalog tuple,
used where a caller must read a catalog row safely against concurrent in-place
updates (e.g. of `pg_class` relfrozenxid). [verified-by-code]
(`syscache.c:283` — via
`knowledge/files/src/backend/utils/cache/syscache.c.md`).



### SECURITY_RESTRICTED_OPERATION
The `SecurityRestrictionContext` flag that forbids changing session state
(SET ROLE, creating temp objects, etc.) while running otherwise-untrusted
code such as index expressions, triggers, and maintenance commands.
[verified-by-code] (via `knowledge/idioms/commit-transaction-sequence.md`).



### SendProcSignal
Sets a reason flag in a target backend's ProcSignal slot and sends it SIGUSR1 — the mechanism for inter-backend requests like recovery-conflict, barrier, and catchup signals; the recipient services it at the next CHECK_FOR_INTERRUPTS. [verified-by-code] (via `knowledge/subsystems/storage-ipc.md`).



### SendSharedInvalidMessages
Broadcasts a batch of accumulated invalidation messages into the shared sinval
queue so other backends will flush the affected cache entries; commit records
the messages before this broadcast (commit-before-broadcast ordering).
[verified-by-code] (via `knowledge/files/src/backend/utils/cache/inval.c.md`).



### SeqScan
The sequential-scan plan/executor node that reads every live tuple of a relation block by block through the table AM, applying the scan qual; the baseline access path the planner costs all others against. [verified-by-code] (via `knowledge/subsystems/executor.md`).



### ServerKey
In SCRAM, `HMAC(SaltedPassword, "Server Key")`; the server signs the auth
message with it so the client can authenticate the server in turn (mutual auth).
It is stored (alongside `StoredKey`) in the SCRAM verifier in `pg_authid`.
[verified-by-code] (`auth-scram.c:1189` — via
`knowledge/files/src/backend/libpq/auth-scram.c.md`).



### ServerLoop
The postmaster's accept loop after startup: it selects on the listen sockets, accepts each client connection, and forks a backend to handle it, while also reaping dead children and launching background processes. [verified-by-code] (`postmaster.c:1678` — via `knowledge/files/src/backend/postmaster/postmaster.c.md`).



### SET_VARSIZE
The macro that writes the total length (4-byte header plus data) into a
varlena's header — the standard final step when constructing a varlena datum
in the long (uncompressed) form. [verified-by-code] (via
`knowledge/files/contrib/pgcrypto/pgp-pgsql.md`).



### SetLatch
Sets a process's latch, waking it from a `WaitLatch` sleep; it is the
edge-triggered "you have work / wake up" signal between backends and is
async-signal-safe, so signal handlers (e.g. the postmaster's
`handle_pm_*_signal`) set a flag and call `SetLatch` to break the main loop out
of its wait. [verified-by-code] (via
`knowledge/files/src/backend/postmaster/postmaster.c.md`).



### SetSecurityLabel
The internal routine that binds a security label string to an object under a
given provider (the catalog-write half of the `SECURITY LABEL` machinery).
sepgsql computes the SELinux context for a new object and then calls
`SetSecurityLabel` to record it. [verified-by-code] (via
`knowledge/files/contrib/sepgsql/database.c.md`).



### shadow_pass
The stored authentication verifier for a role (the contents of
`pg_authid.rolpassword`) — either an `md5…` hash or a `SCRAM-SHA-256$…`
verifier — checked against the client's response during password
authentication. Never the cleartext password. [verified-by-code] (via
`knowledge/files/src/backend/libpq/crypt.c.md`).



### shared_preload_libraries
The GUC naming shared libraries the postmaster loads at startup, before any backend forks, so an extension can run `_PG_init`, reserve shared memory, register background workers, and install process-wide hooks. It is `PGC_POSTMASTER` (change requires restart); modules needing shared state or LSM-style hooks must use it rather than per-session `LOAD`. [from-comment] (via `knowledge/files/contrib/sepgsql/label.c.md`).



### SharedFileSet
A `FileSet` extended with DSM-backed reference counting so parallel-query workers can share a set of temporary files; the last process to detach from the DSM segment cleans them up. [verified-by-code] (via `knowledge/files/src/backend/storage/file/sharedfileset.c.md`).



### SharedRecordTypmodRegistry
The opaque shared structure (declared in `typcache.h`) that lets parallel
workers agree on blessed record typmods, so an anonymous `RECORD` type assigned a
typmod in the leader resolves to the same tuple descriptor in a worker. It is
attached to the parallel DSM and backed by `dshash`. [verified-by-code] (via
`knowledge/files/src/include/utils/typcache.h.md`).



### ShareLock
The table-level lock mode (and the heavyweight conflict class) that permits
concurrent readers but blocks writers; `CREATE INDEX` (non-concurrent) holds it
so the table can be read but not modified during the build. Verification tools
note when an operation needs only `ShareLock` versus a stronger mode.
[verified-by-code] (via `knowledge/files/contrib/amcheck/verify_nbtree.md`).



### ShareUpdateExclusiveLock
The self-conflicting table lock level held by VACUUM, ANALYZE, CREATE INDEX
CONCURRENTLY and similar maintenance; it permits ordinary reads and writes but
serialises against other maintenance on the same relation. [verified-by-code]
(via `knowledge/files/src/backend/access/brin/brin_revmap.c.md`).



### shm_mq
The single-reader, single-writer shared-memory message queue — a pipe-like construct living in a DSM region, used chiefly to ferry tuples and error messages between a parallel-query leader and its workers. Writers block when full and readers when empty, coordinated through process latches. [verified-by-code] (via `knowledge/files/src/backend/storage/ipc/shm_mq.c.md`).



### shm_mq (shared-memory message queue)
A single-reader/single-writer ring buffer living in a DSM segment, the standard
way a parallel leader and worker stream bytes (tuples, errors, tuple counts) to
each other. `shm_mq_send`/`shm_mq_receive` block on the peer's latch and report
`SHM_MQ_DETACHED` when the other end goes away. [from-comment] (via
`knowledge/files/src/backend/storage/ipc/shm_mq.c.md`).



### ShmemIndex
The hash table (itself in shared memory) mapping a string name to the address and size of each registered shared-memory structure, so backends can attach to shared areas by name during startup. [verified-by-code] (via `knowledge/files/src/backend/storage/ipc/shmem.c.md`).



### SIGHUP
The signal the postmaster (and, propagated, each backend) treats as "reload configuration": it re-reads `postgresql.conf`/`pg_hba.conf` and applies any changed `PGC_SIGHUP`-class GUCs without a restart. Backends already running pick up the change at the next `CHECK_FOR_INTERRUPTS`/config-reload point, so in-flight queries may not see it immediately. [from-comment] (via `knowledge/files/contrib/sepgsql/uavc.c.md`).



### simple_heap_insert
Inserts a single tuple into a heap with a frozen command id and no speculative-insertion machinery; the catalog-write building block beneath `CatalogTupleInsert`. [verified-by-code] (via `knowledge/files/src/backend/catalog/indexing.c.md`).



### simple_prompt
Frontend helper that prints a prompt and reads a line from the terminal with echo optionally disabled (for passwords); used by `psql`, `connect_utils.c`, and other client tools. [verified-by-code] (`connect_utils.c:48-49` — via `knowledge/files/src/fe_utils/connect_utils.c.md`).



### slock_t
The platform-specific spinlock type manipulated by `SpinLockInit/Acquire/Release`, used to guard very short critical sections over a handful of shared-memory fields where an LWLock would be too heavy. Spinlocks must never be held across anything that can block or error, since they have no deadlock detection and no interrupt servicing. [verified-by-code] (via `knowledge/files/src/backend/access/brin/brin.c.md`).



### SLRU
Simple LRU — the fixed-size, page-buffered cache layer for the dense numbered logs that don't live in the main buffer pool (clog/xact-status, commit_ts, multixact, subtrans, notify), with its own simple replacement and fsync logic. [verified-by-code] (`commit_ts.c:150` — via `knowledge/subsystems/access-transam.md`).



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



### smgropen
Returns (creating if needed) the `SMgrRelation` handle for a `RelFileLocator`+backend — the entry point to the storage-manager layer. It is cheap and cache-backed, so callers re-open freely rather than stash the handle. [verified-by-code] (via `knowledge/files/src/backend/catalog/storage.c.md`).



### SMgrRelation
The storage-manager handle for a relation's physical files, obtained from
`smgropen` on a `RelFileLocator`. It is the layer `md.c` implements and through
which buffer reads/writes, extends, and truncates reach the filesystem.
[verified-by-code] (`storage.c:122` — via
`knowledge/files/src/backend/catalog/storage.c.md`).



### smgrwrite
Writes one already-filled buffer block to a relation fork through the storage manager (`md.c`), without WAL or buffer-pool involvement; used by bulk-write paths and during recovery. [verified-by-code] (via `knowledge/files/src/backend/storage/smgr/bulk_write.c.md`).



### SnapBuild
The logical-decoding snapshot builder that reconstructs a historic MVCC
snapshot from the WAL stream so that catalog tuples can be interpreted
correctly as of each decoded change. [from-comment] (via
`knowledge/subsystems/contrib-pg_logicalinspect.md`).



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



### snapshotConflictHorizon
The XID carried by many WAL records marking the newest transaction whose
visibility could conflict with replay of that record. On a hot standby it
drives recovery-conflict cancellation of queries that might still need the
about-to-be-removed tuples. [from-comment] (via
`knowledge/files/src/backend/access/spgist/spgxlog.c.md`).



### SnapshotData
The read-side struct recording which transactions count as committed at snapshot time (xmin/xmax plus the in-progress `xip` array and a snapshot type); it holds the visibility horizon, not the rows themselves. [verified-by-code] (via `knowledge/data-structures/snapshot-lifecycle.md`).



### SortSupport
An optimization interface letting a datatype supply an inlinable comparator (and sometimes abbreviated keys) to tuplesort, avoiding a full fmgr call per comparison; opclasses register it via a SortSupport support function. [verified-by-code] (via `knowledge/files/src/backend/utils/sort/sortsupport.c.md`).



### SpecialJoinInfo
The planner struct (built in initsplan.c) describing a non-inner join — its outer/anti/semi type and minimum left/right relid sets — so the join-order search respects the join's commutativity and associativity limits. [verified-by-code] (via `knowledge/files/src/backend/optimizer/plan/initsplan.c.md`).



### SPI (Server Programming Interface)
The in-backend API (`SPI_connect`, `SPI_execute`, `SPI_prepare`, …) that lets C
code and PL handlers run SQL through the regular parser/planner/executor while
managing their own memory and snapshot nesting. It is how triggers, PL/pgSQL,
and many extensions issue queries. [from-comment] (via
`knowledge/idioms/spi.md`).



### SPI_connect
Opens a Server Programming Interface session for the current backend, setting up the SPI memory context and procedure nesting so the caller can run SQL from C; balanced by `SPI_finish`. The canonical referential-integrity trigger demo uses it. [verified-by-code] (via `knowledge/files/contrib/spi/refint.c.md`).



### SPI_execute
The SPI entry point that parses, plans and executes a one-shot query string in
a single call, capturing results in `SPI_tuptable`; the workhorse used by PLs
and C code to run SQL from inside the backend. [verified-by-code] (via
`knowledge/files/src/pl/plpython/plpy_spi.md`).



### SPI_finish
The Server Programming Interface call that tears down the SPI session opened by `SPI_connect`, freeing the SPI memory context and restoring the caller's context; every `SPI_connect` must be balanced by it (including on the error path). It is the close bracket around C/PL code that runs SQL via `SPI_execute`/`SPI_prepare`. [inferred] (via `knowledge/files/contrib/lo/lo.c.md`; see `knowledge/idioms/spi.md`).



### SPI_getvalue
Returns a column of an SPI result tuple as a freshly-palloc'd C string (running the type's output function), given the tuple, its descriptor, and a 1-based column number; NULL for a SQL NULL column. [verified-by-code] (via `knowledge/files/contrib/spi/refint.c.md`).



### SPI_keepplan
The SPI call that marks a prepared plan to survive past `SPI_finish`, moving
it under a long-lived context so a PL can cache the plan across invocations.
[verified-by-code] (via `knowledge/files/src/pl/plpgsql/src/pl_exec.md`).



### SPI_prepare
The SPI entry point that parses and plans a query string into a reusable
prepared-statement handle without executing it; the planned statement is
one-shot unless retained with `SPI_keepplan`. [verified-by-code] (via
`knowledge/idioms/spi.md`).



### spinlock
The lowest-level mutual-exclusion primitive — a busy-wait lock held for only a
handful of instructions, with no deadlock detection and no wait queue. Used to
protect tiny shared structures (and to bootstrap LWLocks); long or blocking
work must never happen under one. [from-comment] (via
`knowledge/files/src/backend/storage/lmgr/s_lock.c.md`).



### SQLSTATE
The five-character machine-readable error code (SQL-standard class plus PostgreSQL subclass) attached to every report, chosen with errcode() from the symbolic names in errcodes.txt; clients branch on it rather than on message text. [verified-by-code] (`elog.h:69` — via `knowledge/idioms/error-handling.md`).



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



### StartTransactionCommand
The state-smart xact.c entry point that postgres.c calls before executing each client command — starting a new transaction or continuing the existing one — paired with `CommitTransactionCommand` afterward. [from-README] (via `knowledge/files/src/backend/access/transam/README.md`).



### StartupXLOG
The startup-process entry point that performs WAL replay / crash recovery and
brings the cluster to a consistent state before normal operation begins.
[verified-by-code] (`xlog.c:5846` — via
`knowledge/files/src/backend/access/transam/xlog.c.md`).



### StaticAssert
A compile-time assertion (`StaticAssertDecl` / `StaticAssertStmt`) that
fails the build if a constant condition is false; used to pin struct sizes
and flag/enum invariants that must not silently drift. [from-comment] (via
`knowledge/subsystems/contrib-hstore_plperl.md`).



### StaticAssertDecl
The compile-time assertion macro (a declaration-context `_Static_assert`
wrapper) used to enforce invariants the compiler can check — struct field
ordering, size relationships, enum bounds — turning a silent miscompile into a
build error. Several load-bearing catalog/PL conventions lack one (a recurring
corpus issue). [from-comment] (via
`knowledge/files/src/pl/plpgsql/src/plpgsql.md`).



### StaticAssertStmt
The compile-time assertion macro PG uses to enforce invariants the compiler
can check — array lengths matching an enum count, struct sizes, flag-bit
non-overlap — failing the build rather than the running server. e.g.
`StaticAssertStmt(lengthof(arr) == NUM_TAGS, ...)` keeps a lookup table in sync
with its enum. [verified-by-code] (via
`knowledge/files/contrib/pg_plan_advice/pgpa_ast.h.md`).



### StoredKey
In SCRAM, `H(ClientKey)` — the value actually kept in the `pg_authid`
verifier. During authentication the server reconstructs a candidate client key
from the client proof and the computed client signature, hashes it, and compares
to `StoredKey`, so the plaintext-equivalent client key is never stored.
[verified-by-code] (`auth-scram.c:1147-1189` — via
`knowledge/files/src/backend/libpq/auth-scram.c.md`).



### str_tolower
The locale-aware lowercasing routine used by `formatting.c` and the `lower()`
SQL function; it honors the collation's provider (libc/ICU/builtin) and handles
multibyte encodings, unlike a naive byte-wise downcase. Paired with `str_toupper`
and `str_initcap`. [verified-by-code] (via
`knowledge/files/src/backend/utils/adt/formatting.c.md`).



### StringInfo
The resizable string/byte buffer (`StringInfoData`: data, len, maxlen, cursor)
used everywhere PostgreSQL builds up text or binary output — error messages,
wire-protocol messages, COPY data. `appendStringInfo*` grow it via `repalloc`;
`cursor` tracks read position when it backs an incoming message. [from-comment]
(via `knowledge/files/src/common/stringinfo.c.md`).



### StringInfoData
The resizable byte-buffer struct (`data`/`len`/`maxlen`/`cursor`) that is PG's backend-wide alternative to ad-hoc `realloc` and to the frontend `PQExpBuffer`; `makeStringInfo` allocates one initialised to `STRINGINFO_DEFAULT_SIZE` (1024). [verified-by-code] (`stringinfo.c:71-75` — via `knowledge/files/src/common/stringinfo.c.md`).



### stringToNode
The node-tree deserializer (inverse of `outfuncs.c`'s `nodeToString`) that
rebuilds a Node tree from its textual representation; used to load stored
rules, views, and other catalog-serialized plans. [verified-by-code] (via
`knowledge/files/src/backend/nodes/readfuncs.c.md`).



### SubLink
A parse-tree node representing a sub-SELECT appearing in an expression — EXISTS, IN, ANY/ALL, scalar, or expression sublink; the planner later converts it into a SubPlan or, where possible, pulls it up into a join. [verified-by-code] (via `knowledge/subsystems/parser-and-rewrite.md`).



### SubPlan
A planner/executor representation of a sub-SELECT that is evaluated per outer
row (or per comparison) — `SS_process_sublinks` turns a correlated SubLink into
a SubPlan attached to the parent expression tree, with ALL/ANY/EXISTS getting
specialised SubPlan subtypes. Contrast with InitPlan, which runs once.
[from-comment] (via
`knowledge/files/src/backend/optimizer/plan/subselect.c.md`).



### subquery_planner
The recursive entry point that plans one query level (a SELECT/INSERT/UPDATE/DELETE/MERGE Query): it pulls up sublinks and subqueries, flattens the jointree, builds base RelOptInfos, finds the cheapest join order, and hands off to grouping_planner for the upper rels. Set-operation arms and uncorrelated subqueries are each planned by their own subquery_planner call. [from-comment] (via `knowledge/files/src/backend/optimizer/prep/prepunion.c.md`; see `knowledge/subsystems/optimizer.md`).



### SubqueryScan
The plan/exec node wrapping a sub-select's output; a trivial one (adding no real projection) is deleted in setrefs.c by `trivial_subqueryscan` once final target lists are known. [from-comment] (via `knowledge/files/src/backend/optimizer/plan/setrefs.c.md`).



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



### SupportRequestSelectivity
One of the planner-support-function request types (`supportnodes.h`): a function
can register a support function that the planner calls to supply selectivity,
cost, row-count, or index-condition simplifications it could not derive
generically. The mechanism that lets functions like `LIKE` or range operators
teach the optimizer about themselves. [verified-by-code] (via
`knowledge/files/src/include/nodes/supportnodes.h.md`).



### SwitchToUntrustedUser
The helper (paired with `RestoreUserContext`) that temporarily drops to a
less-privileged user id while running code that shouldn't execute with the
caller's privileges — e.g. maintenance commands touching user-defined index
expressions or a SECURITY-sensitive index build. It captures the prior
user/SecContext so the switch is reliably undone. [verified-by-code] (via
`knowledge/files/src/include/utils/usercontext.h.md`).



### SyncRepWaitForLSN
The routine a committing backend calls under synchronous replication to block
until enough standbys have confirmed the commit LSN (per `synchronous_commit`
level and `synchronous_standby_names`). [verified-by-code] (`syncrep.c:149` —
via `knowledge/subsystems/replication.md`).



### syscache (system cache)
The indexed front end over catcache: a fixed table of well-known catalog
lookups (`RELOID`, `PROCOID`, `TYPEOID`, …) addressed by an enum, accessed
through `SearchSysCache1..4` and `GetSysCacheOid`. It is the normal way backend
C code reads a single catalog row. [from-comment] (via
`knowledge/files/src/backend/utils/cache/syscache.c.md`).



### SysCacheGetAttr
Extracts one attribute (handling NULLs) from a tuple obtained via the syscache, given the cache id and attnum; the standard way to read a column off a `SearchSysCache` result before `ReleaseSysCache`. [verified-by-code] (via `knowledge/files/src/backend/utils/cache/syscache.c.md`).



### SysCacheIdentifier
The enum that names each system cache; `SysCache[]` is a global `CatCache *` array indexed by it, populated from a genbki-generated `cacheinfo[]` at `InitCatalogCache`. [verified-by-code] (`syscache.c:87` — via `knowledge/subsystems/utils-cache.md`).



### SysScanDesc
The descriptor returned by `systable_beginscan`, which hides whether a
catalog scan runs as an index scan or a sequential scan behind one interface, so
catalog-reading code (`SearchSysCache` misses, `RelationBuildDesc`, …) doesn't
care which. `systable_getnext` and `systable_endscan` operate on it.
[verified-by-code] (`genam.c:388` — via
`knowledge/files/src/backend/access/index/genam.c.md`).



### systable_beginscan
The genam wrapper for reading a system catalog: it picks an index scan when an
index is usable (`indexOK`, an OID is supplied, and system indexes aren't
ignored) and otherwise does a heap sequential scan applying the scan keys via
`HeapKeyTest` — hiding the choice behind a `SysScanDesc`. Catalog readers use it
so they work even when an index is being rebuilt. [verified-by-code]
(`genam.c:388-490` — via
`knowledge/files/src/backend/access/index/genam.c.md`).



### system_identifier
A 64-bit value generated at `initdb` (from timestamp and PID) stamped into `pg_control` and every WAL page; replication and tools like `pg_rewind` compare it to refuse mixing data from unrelated clusters. [verified-by-code] (`pg_rewind.c:743-790` — via `knowledge/files/src/bin/pg_rewind/pg_rewind.c.md`).



### t_ctid
The field in a heap tuple header holding an item pointer that normally points to the tuple itself, but for an updated row points to the next (newer) version, forming the update/HOT chain that MVCC and the executor follow to find the live tuple. A self-pointing `t_ctid` marks the chain end. [verified-by-code] (via `knowledge/files/src/include/access/htup_details.h.md`).



### t_hoff
The heap-tuple header field giving the byte offset from the start of the tuple to its user data — i.e. the size of the (possibly null-bitmap- and OID-extended) header, MAXALIGN'd. amcheck checks it equals the recomputed `expected_hoff` derived from the header size and the null bitmap. [verified-by-code] (via `knowledge/files/contrib/amcheck/verify_heapam.md`).



### table_close
Releases a table relation opened with `table_open`, optionally keeping the lock until transaction end; the relation-cleanup call paired with `table_open`, forwarding to `relation_close`. [verified-by-code] (via `knowledge/files/contrib/sepgsql/relation.c.md`).



### table_open
The table access-method wrapper around `relation_open` that opens a relation by
OID with a given lockmode and asserts the relation is a table-like object (not
an index). Paired with `table_close`; the index analogue is `index_open`.
[verified-by-code] (via
`knowledge/files/src/backend/access/common/relation.c.md`).



### TableAmRoutine
The struct of callbacks defining a pluggable table access method — tuple insert/update/delete/lock, scan begin/getnext, index-fetch, vacuum, analyze, and size estimation; heap is the built-in implementation returned by its handler. [verified-by-code] (`tableamapi.c:27` — via `knowledge/files/src/backend/access/table/tableamapi.c.md`).



### TargetEntry
A node in a query or plan's target list: an expression paired with its output
resno, column name, and `resjunk` flag. The plpgsql simple-expression fast path,
for example, peels a plan down to a single `Result` and caches that node's lone
TargetEntry expression. [verified-by-code]
(via `knowledge/files/src/pl/plpgsql/src/pl_exec.md`).



### TerminateBufferIO
The bufmgr I/O-coordination routine that ends an in-progress buffer read/write, clears `BM_IO_IN_PROGRESS`, updates validity/dirty flags, and wakes backends blocked in `WaitIO`; it is the close-out partner of `StartSharedBufferIO`. [verified-by-code] (`bufmgr.c:7148` — via `knowledge/files/src/backend/storage/buffer/bufmgr.c.md`).



### text_to_cstring
Converts a `text` varlena Datum to a palloc'd NUL-terminated C string (un-toasting if needed); the inverse of `CStringGetTextDatum`, and a place to watch for missing length caps on attacker-supplied text. [verified-by-code] (via `knowledge/files/contrib/fuzzystrmatch/dmetaphone.c.md`).



### TID (ItemPointer)
A tuple identifier: the physical address of a tuple on disk, encoded as an
`ItemPointerData` of block number plus a 1-based line-pointer offset within that
page. A heap tuple's own location is its `t_self` TID, and indexes store TIDs as
the pointers from index keys to heap rows. [verified-by-code] (`htup.h:62` — via
`knowledge/files/src/include/access/htup.h.md`).



### TidStore
The compact, shared-memory-capable data structure for storing a large set of
TIDs (item pointers) used by VACUUM to remember dead tuples — successor to the
old flat array, with radix-tree internals so it scales and can be shared by
parallel vacuum workers. Parallel index cleanup reads dead TIDs from a shared
`TidStore`. [verified-by-code] (via
`knowledge/files/src/backend/commands/vacuumparallel.c.md`).



### TimeADT
The on-disk/in-memory representation of SQL `TIME` (time of day without zone)
— a 64-bit microsecond count since midnight — declared alongside `DateADT` and
`TimeTzADT`. The adt layer's date/time functions take and return these typed
integers rather than raw `int64`. [verified-by-code] (via
`knowledge/files/src/include/utils/date.h.md`).



### TimestampTz
The storage type for `timestamp with time zone`: a signed 64-bit count of
microseconds from the Postgres epoch (2000-01-01), stored in UTC and rendered in
the session time zone on output. Conversion helpers like
`timestamptz_to_time_t(TimestampTz)` bridge it to Unix time.
[verified-by-code] (via `knowledge/files/src/include/utils/date.h.md`).



### timingsafe_bcmp
A constant-time memory comparison returning zero iff two equal-length buffers match, used so that comparisons of secrets (MACs, authentication tags, tokens) do not leak how many leading bytes matched via timing. It replaces `memcmp` on security-sensitive equality checks. [verified-by-code] (via `knowledge/files/src/port/timingsafe_bcmp.c.md`).



### TOAST
The Oversized-Attribute Storage Technique — values too large for a heap page are compressed and/or split into chunks stored in a side TOAST relation, leaving an 18-byte pointer in the main tuple; a per-column storage strategy controls when it kicks in. [verified-by-code] (`toast_internals.c:1` — via `knowledge/files/src/backend/access/common/toast_internals.c.md`).



### TOAST (The Oversized-Attribute Storage Technique)
PostgreSQL's mechanism for values too large to fit inline in a heap tuple:
oversized attributes are compressed and/or moved out-of-line into an associated
TOAST table, leaving a small pointer in the row. Reads transparently
reconstruct the value via the detoasting path. [verified-by-code]
(`detoast.c:205` — via
`knowledge/files/src/backend/access/common/detoast.c.md`).



### toast_compression
The module implementing the pluggable TOAST compression methods — historic PGLZ and LZ4 — behind the per-column `STORAGE`/compression setting, providing the compress/decompress entry points used when a value is too large to store inline. The chosen method is recorded in the toast pointer so decompression knows which codec to use. [verified-by-code] (via `knowledge/files/src/backend/access/common/toast_compression.c.md`).



### TopMemoryContext
The root of a backend's memory-context tree, living for the whole process
lifetime; it is effectively `malloc`. Almost nothing should allocate here
directly — doing so is a backend-lifetime leak — but it parents the long-lived
caches (`CacheMemoryContext`, etc.). [from-comment] (`memutils.h:52-67` — via
`knowledge/files/src/include/utils/memutils.h.md`).



### TopPortalContext
The long-lived parent memory context under which every portal's own context is
created; owned by `portalmem.c` together with the portal-name hash table.
[verified-by-code] (`portalmem.c:93` — via
`knowledge/subsystems/utils-mmgr.md`).



### TopTransactionContext
The memory context whose lifetime is the current top-level transaction; it is
reset/deleted at commit or abort, making it the natural home for state that must
survive across statements but not across the transaction (e.g. PL subtransaction
bookkeeping lists). [from-comment] (`memutils.h:52-67` — via
`knowledge/files/src/include/utils/memutils.h.md`).



### TransactionId
A 32-bit transaction identifier (XID) stamped into each tuple's xmin/xmax to drive MVCC visibility; XIDs are assigned lazily on first write and wrap around, so they are compared modulo-2^31 and frozen by vacuum to stay ahead of wraparound. [verified-by-code] (`varsup.c:299` — via `knowledge/files/src/backend/access/transam/varsup.c.md`).



### TransactionId (xid)
A 32-bit transaction identifier stamped into each tuple's xmin/xmax. Special
values include `InvalidTransactionId` (0); the 32-bit space wraps around, so
PostgreSQL also carries a 64-bit `FullTransactionId` to reason about age
without ambiguity. [verified-by-code] (`transam.h:3-4` — via
`knowledge/files/src/include/access/transam.h.md`).



### TransactionIdCommitTree
The clog routine that atomically marks a top-level xid and all its committed subtransaction xids as committed in pg_xact; called from the commit path after the WAL commit record is durable. [verified-by-code] (via `knowledge/files/src/backend/access/transam/xact.c.md`).



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



### TriggerData
The context struct a C-language trigger function receives (via
`fcinfo->context`): it carries the event flag bits (BEFORE/AFTER, ROW/STATEMENT,
INSERT/UPDATE/DELETE), the `Relation`, the old/new `HeapTuple`s, and any
transition tables. The trigger reads it to learn what fired and returns the
(possibly modified) tuple. [from-comment] (via
`knowledge/docs-distilled/trigger-interface.md`).



### TsmRoutine
The callback struct returned by a tablesample method's `tsm_handler` function (`tsmapi.h:55`), driving `TABLESAMPLE` block/row selection; the built-in methods are `SYSTEM` (block-level) and `BERNOULLI` (row-level). [verified-by-code] (`tsmapi.h:55` — via `knowledge/docs-distilled/tablesample-method.md`).



### TupleDesc
A tuple descriptor: the runtime description of a row shape — an array of
`Form_pg_attribute` entries (name, type, length, alignment, …) plus optional
constraint/default info — that tells code how to form and deform tuples. It is
reference-counted when cached against a relation. [from-comment] (via
`knowledge/files/src/backend/access/common/tupdesc.c.md`).



### TupleDescInitEntry
Fills one attribute slot of a `TupleDesc` by looking up the `pg_type` row for a given type OID (name, length, alignment, etc.); the per-column initialiser used when building a descriptor programmatically. [verified-by-code] (`tupdesc.c:900` — via `knowledge/files/src/backend/access/common/tupdesc.c.md`).



### TupleHashTable
The simplehash-based hash table in `execGrouping.c` shared by hash aggregation, hashed SubPlan/IN, SetOp, and recursive-union dedup; constructed by `BuildTupleHashTable`. [verified-by-code] (via `knowledge/subsystems/executor.md`).



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



### two_phase
The logical-replication subscription/slot option that enables decoding of
prepared (two-phase commit) transactions at PREPARE time rather than only at
COMMIT PREPARED, so the changes reach the subscriber as a prepared transaction.
Interacts with slot creation and the apply worker's transaction handling.
[verified-by-code] (via
`knowledge/files/src/backend/replication/logical/worker.c.md`).



### twophase_rmgr
The static dispatch tables mapping each `TwoPhaseRmgrId` (lock manager, predicate locks, multixact, pgstat, ...) to its prepare/commit/abort/recover callbacks, so two-phase commit can persist and replay each subsystem's per-transaction state across a `PREPARE TRANSACTION`. [verified-by-code] (via `knowledge/files/src/backend/access/transam/twophase_rmgr.c.md`).



### TypeCacheEntry
The per-type cached bundle the typcache builds on demand — comparison/hash operators and procs, btree/hash opclass info, type length/byval/align, and composite tuple descriptors — so hot paths avoid repeated catalog lookups. [verified-by-code] (via `knowledge/files/src/include/utils/typcache.h.md`).



### UnlockBufHdrExt
The buffer-header unlock primitive that atomically releases `BM_LOCKED` while applying a set/clear of state bits and a refcount delta in one store; it deliberately cannot adjust the usage count, which needs separate capping. [verified-by-code] (via `knowledge/data-structures/bufferdesc-state.md`).



### UnlockRelationOid
Releases a heavyweight relation lock taken with `LockRelationOid`; normally locks are held to transaction end, so explicit unlock is reserved for narrow, well-understood cases (e.g. early release of a catalog lock). [verified-by-code] (via `knowledge/files/src/backend/access/common/relation.c.md`).



### UnlockReleaseBuffer
Convenience that releases a buffer's content lock and then unpins it in one call; the standard cleanup at the end of a read-modify loop over a page. [verified-by-code] (via `knowledge/files/contrib/amcheck/verify_gin.md`).



### USE_ASSERT_CHECKING
The compile-time symbol enabled by a `--enable-cassert` / cassert build; it
turns on every `Assert()` plus extra invariant checks (node-tag checks, memory
sentinel bytes via `MEMORY_CONTEXT_CHECKING`, randomized free fills). Off in
production builds, so asserts must never have side effects. [verified-by-code]
(`nodes.h:173-183` — via
`knowledge/files/src/backend/nodes/value.c.md`).



### usercontext
The helper pair (`GetUserIdAndSecContext`/`SetUserIdAndSecContext`,
`SwitchToUntrustedUser`/`RestoreUserContext`) that temporarily switches the
current user id and security context — e.g. so maintenance commands run index
expressions or triggers under the table owner rather than the invoking
superuser, closing a privilege-escalation hole. [verified-by-code] (via
`knowledge/files/src/include/utils/usercontext.h.md`).



### UserMapping
The catalog object (pg_user_mapping) binding a local role to remote credentials and options for a foreign server; postgres_fdw keys its per-backend connection cache solely on `UserMapping.umid`. [verified-by-code] (via `knowledge/files/contrib/postgres_fdw/connection.c.md`).



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



### VARDATA_ANY
The macro returning a pointer to a varlena's data payload while
transparently handling both the 1-byte (short) and 4-byte (long) header
layouts; pair with `VARSIZE_ANY_EXHDR` for the length. [verified-by-code]
(via `knowledge/subsystems/contrib-citext.md`).



### VARSIZE
The varlena accessor macro returning the total stored size (including the length header) of a variable-length datum; the `VARSIZE_ANY_EXHDR` variant returns the payload size excluding the header. Code that builds or validates text/bytea results uses it to bound copies and enforce server-side size limits. [verified-by-code] (via `knowledge/files/contrib/pgcrypto/pgp-pgsql.md`).



### VARSIZE_ANY_EXHDR
The macro giving a varlena's payload length excluding its header, for either
the short or long header form; the companion of `VARDATA_ANY`.
[verified-by-code] (via `knowledge/subsystems/contrib-citext.md`).



### visibility map (VM)
A two-bits-per-page relation fork (`VISIBILITYMAP_FORKNUM`) marking pages whose
tuples are all-visible (and optionally all-frozen) to every transaction. It lets
index-only scans skip heap fetches and lets `VACUUM` skip clean pages; the bits
are cleared whenever a page is modified. [from-comment] (via
`knowledge/files/src/backend/access/heap/visibilitymap.c.md`).



### VXID
A virtual transaction id — the pair (backend proc number, local counter) that names a transaction before it has been assigned a real XID, so read-only transactions can be referenced (e.g. in locks and `pg_locks`) without consuming an XID. It becomes associated with a permanent XID only if and when the transaction first writes. [from-comment] (via `knowledge/files/src/backend/access/transam/README.md`).



### WaitEventSet
A reusable set of wait conditions (sockets, latches, postmaster-death) a
backend blocks on in one `epoll`/`kqueue`/`poll` call, multiplexing client I/O,
inter-process latches, and shutdown detection. Long-lived sets avoid rebuilding
the kernel structure each wait. [verified-by-code] (via
`knowledge/files/src/backend/storage/ipc/waiteventset.c.md`).



### WaitEventSetWait
The latch.c entry point that sleeps on a `WaitEventSet` (latch + sockets + postmaster-death) until an event fires or the timeout elapses; the waiter's `maybe_sleeping` flag lets a concurrent `SetLatch` know a wakeup is required. [verified-by-code] (via `knowledge/files/src/backend/storage/ipc/latch.c.md`).



### WaitLatch
The convenience wrapper that waits on a single latch (plus optional timeout and
postmaster-death) by building a one-shot `WaitEventSet`. Latches are the
backend's edge-triggered "you have work / wake up" primitive, set with
`SetLatch` from another process or a signal handler. [verified-by-code]
(`waiteventset.c:88` — via `knowledge/subsystems/storage-ipc.md`).



### WaitLatchOrSocket
The latch.c convenience wrapper (`latch.c:222`) that builds a one-shot `WaitEventSet` over the latch, postmaster death, a timeout, and optionally a socket's readability/writability — the `WL_SOCKET_*` events are only available through this entry. [verified-by-code] (via `knowledge/files/src/backend/storage/ipc/latch.c.md`).



### WaitLSNType
The category of LSN a backend can wait for in `xlogwait.c` (e.g. replay vs flush); each type has its own pairing-heap of waiters keyed by target LSN. [verified-by-code] (`xlogwait.c:99` — via `knowledge/files/src/backend/access/transam/xlogwait.c.md`).



### WAL (xlog)
The write-ahead log: every change is recorded as an XLOG record and flushed to
durable storage *before* the modified data pages are written back, which is
what makes crash recovery possible. `XLogInsertRecord` appends records on the
fast path; `StartupXLOG` replays them during recovery. [from-comment]
(`xlog.c:6-28` — via
`knowledge/files/src/backend/access/transam/xlog.c.md`).



### wal_consistency_checking
The GUC listing resource managers for which the server, during recovery, must
compare its replayed page image against the full-page image captured at insert
time — a developer/debugging aid that catches redo routines that don't exactly
reproduce the original page change. [verified-by-code] (via
`knowledge/files/src/backend/access/rmgrdesc/xlogdesc.c.md`).



### wal_level
The GUC controlling how much information is written to WAL (`minimal`, `replica`, `logical`), trading log volume against the features it enables — archiving/streaming need `replica`, logical decoding needs `logical`. Under `minimal`, certain operations (e.g. a permanent relation created in the same transaction) skip WAL and instead fsync the file at commit, tracked via `pendingSyncHash`. [verified-by-code] (via `knowledge/files/src/backend/catalog/storage.c.md`).



### WalRcv
The global pointer to the walreceiver's shared `WalRcvData` control struct; its `WalRcvState` field walks STOPPED → STARTING → CONNECTING → STREAMING as the receiver attaches to the primary. [verified-by-code] (via `knowledge/files/src/include/replication/walreceiver.h.md`).



### WalRcvData
The single shared-memory control struct for the walreceiver (`extern WalRcvData *WalRcv`), tracking receiver state, the received/written/flushed LSNs, and the primary conninfo; most fields are guarded by its spinlock `mutex`. [verified-by-code] (via `knowledge/files/src/include/replication/walreceiver.h.md`).



### walreceiver
The standby-side process that connects to a primary's walsender, receives the
streamed WAL, writes and flushes it locally, and reports flush/apply positions
back for synchronous replication. It runs `WalReceiverMain` and hands received
WAL to the startup process for replay. [from-comment] (via
`knowledge/files/src/backend/replication/walreceiver.c.md`).



### WalSegSz
The configured WAL segment size in bytes (default 16 MB, fixed at initdb);
many tools must read it from pg_control before computing segment file names, a
known ordering hazard in pg_rewind. [verified-by-code] (via
`knowledge/files/src/bin/pg_rewind/pg_rewind.h.md`).



### walsender
The primary-side backend that streams WAL to a connected standby or
logical-replication client, speaking the replication sub-protocol over a normal
libpq connection. Each connected standby has its own walsender running
`WalSndLoop`; for logical replication it drives the decoding output plugin.
[from-comment] (via `knowledge/files/src/backend/replication/walsender.c.md`).



### WalSnd
One walsender's shared-memory slot (`WalSnd` in `walsender_private.h`), holding its state, sent/write/flush/apply LSNs, and latch; the array of them lives under `WalSndCtl`. [verified-by-code] (via `knowledge/files/src/include/replication/headers.md`).



### WalSndCtl
The shared-memory control struct for walsenders and synchronous replication; it holds the per-wait-mode `SyncRepQueue` arrays and the released-LSN watermarks, protected by `SyncRepLock`. [verified-by-code] (`syncrep.h:21-27` — via `knowledge/files/src/backend/replication/syncrep.c.md`).



### WalUsage
The instrumentation counter struct (`instrument.c`) tracking WAL records, full-page images, and bytes generated during execution (and optionally planning); reported by `EXPLAIN (WAL)` and aggregated by pg_stat_statements. [verified-by-code] (via `knowledge/files/contrib/pg_stat_statements/pg_stat_statements.c.md`).



### WindowAgg
The executor node (`nodeWindowAgg.c`) that evaluates window functions over the ordered, partitioned frames produced by an upstream sort. [verified-by-code] (via `knowledge/subsystems/executor.md`).



### WL_EXIT_ON_PM_DEATH
The `WaitLatch` event flag that makes a latch wait terminate the process if
the postmaster dies — the standard way background loops avoid lingering as
orphans after a crash. [verified-by-code] (via
`knowledge/subsystems/contrib-postgres_fdw.md`).



### work_mem
The GUC bounding the memory a single query operation (sort, hash, hash-join build, bitmap) may use before spilling to temporary disk files; a complex query may use several multiples of it concurrently across operations. It is the chief knob trading RAM against spill I/O for executor working state. [inferred] (via `knowledge/files/contrib/pgcrypto/mbuf.md`).



### XactLastRecEnd
The end-LSN of the current transaction's last WAL record; at commit it is what `XLogFlush` flushes to (under `synchronous_commit`) or what `XLogSetAsyncXactLSN` advertises to the walwriter for asynchronous commit. [verified-by-code] (via `knowledge/subsystems/access-transam.md`).



### XactLockTableWait
Blocks until a given transaction ends by taking a share lock on that
transaction's self-exclusive "transaction lock"; used to wait out a concurrent
updater (e.g. in tuple-lock and index-build conflict resolution).
[verified-by-code] (via `knowledge/files/src/backend/storage/lmgr/lmgr.c.md`).



### XactLogCommitRecord
The xact.c routine that assembles the WAL commit record — carrying subxact xids, dropped-relation and invalidation data, and the replication origin — for a committing transaction; its abort sibling is `XactLogAbortRecord`. [verified-by-code] (`xact.c:5870` — via `knowledge/files/src/backend/access/transam/xact.c.md`).



### XidGenLock
The LWLock that serialises transaction-id assignment and protects the shared
`nextXid` / epoch counters in `ShmemVariableCache`. `GetNewTransactionId`
holds it while bumping the counter and advancing the CLOG/subtrans page
boundaries. [verified-by-code]
(via `knowledge/files/src/backend/access/transam/varsup.c.md`).



### XidInMVCCSnapshot
The visibility helper that decides whether a given XID counts as "in progress"
relative to an MVCC snapshot (checking it against the snapshot's xmin/xmax and
xip array) — the snapshot-based analog of `TransactionIdIsInProgress`.
[from-comment] (via
`knowledge/files/src/backend/access/heap/heapam_visibility.c.md`).



### XLOG_BTREE_REUSE_PAGE
The nbtree WAL record emitted when a deleted, now-recyclable B-tree page is
about to be reused; it carries a `snapshotConflictHorizon` so standbys can
cancel conflicting queries before the page changes identity.
[verified-by-code] (via
`knowledge/files/src/backend/access/nbtree/nbtxlog.c.md`).
### XLogBeginInsert
Begins assembling a new WAL record; the caller then registers buffers and
data and finally calls `XLogInsert` to finalize it. [verified-by-code] (via
`knowledge/subsystems/access-transam.md`).



### XLogFlush
Forces WAL up to a given LSN to be written and fsynced to durable storage;
the barrier a backend must cross before reporting a commit or evicting a
dirty buffer whose WAL isn't yet flushed (WAL-before-data).
[verified-by-code] (via `knowledge/subsystems/access-transam.md`).



### XLogInsert
Finalizes the WAL record begun by `XLogBeginInsert`: it assembles the record
from the registered buffers and data, copies it into the WAL buffers under
the insertion locks, and returns the record's end LSN. [verified-by-code]
(via `knowledge/subsystems/access-transam.md`).



### XLogReadBufferForRedo
The redo-side helper that locks and reads the buffer a WAL record targets
and reports whether the record still needs applying — handling
already-applied pages and restoring full-page images when present.
[verified-by-code] (via `knowledge/subsystems/access-transam.md`).



### XLogReaderState
The WAL-decoder state object that reads and validates records sequentially
from a pluggable page source; shared by crash/archive recovery, logical
decoding, and `pg_walinspect`. [verified-by-code] (via
`knowledge/subsystems/contrib-pg_walinspect.md`).



### XLogRecPtr
A 64-bit Log Sequence Number (LSN) naming a byte position in the WAL stream,
conventionally printed as `%X/%X`; ordering and durability decisions are
expressed as comparisons between these. [verified-by-code] (via
`knowledge/subsystems/access-transam.md`).



