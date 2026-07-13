# pgrocks-fdw (vidardb/pgrocks-fdw) — an FDW whose "foreign server" is a local RocksDB owned by a per-table background worker

> Ideology note produced by the `pg-extension-anthropologist` cloud routine.
> Repo: `vidardb/pgrocks-fdw` @ branch `master`. ~131★, language **C/C++**. All
> `file:line` cites below point into that repo (cited as `src/kv_fdw.c:NN`
> etc.), not `source/`, since this doc characterizes an *external* extension.
> Cites verified against the files fetched on 2026-07-13 (see Sources footer).
> Backend target: an embedded **RocksDB** (or VidarDB) LSM-tree key-value store
> living on the *same machine*, in `$PGDATA/kv_fdw/{dbOid}/{relOid}`
> (`src/kv_utility.c:198-204` `[verified-by-code]`).

pgrocks-fdw is "the first foreign data wrapper that connects a LSM-tree-based
storage engine to PostgreSQL" (`README.md:11` `[from-README]`). It is the FDW
corpus's **inverted-premise** entry: where `[[knowledge/subsystems/foreign]]`
and `[[knowledge/ideologies/tds_fdw]]` reach *across a network* to a remote
server, and `[[knowledge/ideologies/sqlite_fdw]]` links an embedded engine
*into the backend's own address space*, pgrocks-fdw does neither. Its "foreign
server" is a RocksDB instance on local disk, and the backend never links
RocksDB at all — the C++ engine is owned by a **separate per-table background
worker process**, reached over **POSIX shared memory + unnamed semaphores**.
The FDW is thus not really a data *wrapper* so much as a bespoke **storage
engine bolted onto PG through the FDW callback seam** — closer in spirit to
`[[knowledge/ideologies/cstore_fdw]]` (FDW-as-storage) than to a remote-access
FDW, but with a client/server process split that neither of those has.

## Domain & purpose

The control comment is `'KV Foreign Data Wrapper'`, default version `0.0.1`,
`relocatable = true` (`kv_fdw.control:2-5` `[verified-by-code]`). A KV foreign
table is created with **no options at all** — `CREATE FOREIGN TABLE student(id
INTEGER, name TEXT) SERVER kv_server` — and the validator accepts anything
because "no options are supported" (`src/kv_fdw.c:1309-1326`; the option-check
body is commented out) `[verified-by-code]`. The whole feature is: rows of a PG
foreign table are persisted as RocksDB key/value pairs, with the **first
column serving as the primary key** and the remaining columns packed into the
value. "The first attribute in the table definition must be the primary key"
(`README.md:89` `[from-README]`); the code hard-codes column 0 as the key
everywhere (`src/kv_utility.c:550-551` carries the `TODO: we assume the 1st
column is primary key` comment) `[from-comment]`. Because RocksDB is
embeddable, the README markets it as "you do not need to run another server"
(`README.md:11` `[from-README]`) — an ironic claim given the extension in fact
spawns a manager process and one worker process per table (see below).
`shared_preload_libraries = kv_fdw` is mandatory (`README.md:69`
`[from-README]`), because the manager bgworker must be registered at postmaster
start.

## How it hooks into PG

- **Handler / validator**: `kv_fdw_handler` returns a `makeNode(FdwRoutine)`
  (`src/kv_fdw.c:1267`) wired with the required scan callbacks
  (`GetForeignRelSize`, `GetForeignPaths`, `GetForeignPlan`,
  `BeginForeignScan`, `IterateForeignScan`, `ReScanForeignScan`,
  `EndForeignScan`, `src/kv_fdw.c:1281-1287`), the full modify set
  (`AddForeignUpdateTargets`, `PlanForeignModify`, `BeginForeignModify`,
  `ExecForeignInsert/Update/Delete`, `EndForeignModify`,
  `src/kv_fdw.c:1291-1297`), `ExplainForeign{Scan,Modify}`, and
  `AnalyzeForeignTable` (`src/kv_fdw.c:1300-1304`) `[verified-by-code]`. This is
  the exact `[[knowledge/idioms/fmgr]]` + `[[knowledge/idioms/fdw-routine-callbacks]]`
  handler pattern. Both entry points are `PG_FUNCTION_INFO_V1`
  (`src/kv_fdw.c:39-40`) `[verified-by-code]`. No JOIN/UPPER pushdown, no batch
  insert, no direct-modify, no `ImportForeignSchema` — those fields are simply
  never set.
- **Key/value column mapping**: `SerializeTuple` walks the tuple and routes
  attribute 0 into the `key` StringInfo and every other attribute into the
  `val` StringInfo (`src/kv_fdw.c:924-943`); a null in column 0 is a hard error
  (`"first column cannot be null!"`, `src/kv_fdw.c:933-934`) `[verified-by-code]`.
  Non-key attributes carry a varint length header; the key does not
  (`src/kv_utility.c:483-495`, `EncodeVarint64` at `:421-435`) `[verified-by-code]`.
  Read-back reverses this in `DeserializeTuple`/`DeserializeAttribute`, keying
  off `index == 0 ? key : val` (`src/kv_fdw.c:521-537`, `src/kv_utility.c:515-545`)
  `[verified-by-code]`.
- **`_PG_init` installs a utility hook and launches the manager**: it chains
  `ProcessUtility_hook = KVProcessUtility` (`[[knowledge/idioms/process-utility-hook-chain]]`)
  then calls `LaunchKVManager()` (`src/kv_utility.c:94-99`) `[verified-by-code]`.
- **DDL event trigger**: the SQL script also registers
  `kv_ddl_event_end_trigger` on `ddl_command_end`
  (`kv_fdw--0.0.1.sql:16-25`). On `CREATE FOREIGN TABLE` it creates the
  per-database directory and *opens then immediately closes* the RocksDB
  instance to initialize it on disk (`src/kv_utility.c:263-320`, `OpenConn`/
  `CloseConn` at `:308-313`) `[verified-by-code]`.
- **Utility-hook DDL/DML plumbing**: `KVProcessUtility` intercepts
  `COPY kv_table FROM/TO` (routing FROM through `KVCopyIntoTable` +
  `KVLoadRequest`, `src/kv_utility.c:568-668,786-802`), `DROP FOREIGN TABLE`
  (rmtree the RocksDB dir + `KVTerminateRequest` the worker,
  `src/kv_utility.c:840-850`), `DROP EXTENSION`/`DROP DATABASE` (terminate all
  workers for the db, `:827-830,857-878`), and blocks `ALTER TABLE ADD COLUMN` /
  unsafe `ALTER COLUMN TYPE` (`:723-771`) `[verified-by-code]`.

## Where it diverges from core idioms — THE headline

### 1. The "foreign" data is local, and the engine lives in a *separate process*, not the backend

This is the deepest divergence and the reason the codebase is far larger than a
single FDW `.c`. The backend (the "client") never links or calls RocksDB. Every
`KV*Request` in `src/kv_api.h:111-124` is a message to another process:

- **A static manager bgworker** is registered in `_PG_init` →
  `LaunchKVManager`, guarded by `process_shared_preload_libraries_in_progress`,
  via `RegisterBackgroundWorker` with `BgWorkerStart_RecoveryFinished` and
  `bgw_restart_time = 1` (`src/server/kv_manager.cc:245-264`) `[verified-by-code]`.
  Its `Run()` loop services `KVOpLaunch` / `KVOpTerminate` control messages
  (`src/server/kv_manager.cc:137-155`) `[verified-by-code]`.
- **One dynamic worker bgworker per foreign table.** The client keys an
  in-backend `unordered_map<KVWorkerId, KVWorkerClient*>` by relation OID
  (`KVWorkerId == KVRelationId == Oid`, `src/kv_api.h:37-39`); on first use it
  asks the manager to `Launch(workerId)`, which calls `LaunchKVWorker` →
  `RegisterDynamicBackgroundWorker` with `BGW_NEVER_RESTART`, passing the
  relation OID in `bgw_extra` and the database OID in `bgw_main_arg`
  (`src/client/kv_client.cc:42-66`; `src/server/kv_worker.cc:792-826`)
  `[verified-by-code]`. See `[[knowledge/idioms/background-worker-startup]]`.
- **The worker owns the RocksDB handle.** `KVWorker` holds a single `conn_`,
  opened once via `OpenConn` on the first `KVOpOpen` and reference-counted
  across backends (`src/server/kv_worker.cc:41-53,133-159`) `[verified-by-code]`.
  `OpenConn` is the only place `DB::Open(options, path, &conn)` is called
  (`src/server/kv_storage.cc:71,84`) `[verified-by-code]`.

**Why the split (`[inferred]`).** RocksDB is a C++ engine that spawns its own
background flush/compaction threads and takes a single-process exclusive lock on
its data directory (single-writer). PG's per-connection `fork()` model would
otherwise (a) fork those engine threads unsafely into every backend, and (b)
have N backends contend for the same RocksDB directory lock. Funnelling all
operations for a table through one long-lived worker gives single-writer
ownership, a stable crash domain, and one engine-thread pool per table rather
than per backend. The code confirms the *shape* of this (one `conn_` per
worker, ref-counted, opened once); the *rationale* is `[inferred]` — no comment
states it. This is a divergence from both the in-process embedded-library
pattern (`[[knowledge/ideologies/sqlite_fdw]]` opens `sqlite3*` in the backend)
and from core's "each backend owns its own buffers" model
(`[[knowledge/subsystems/storage-buffer]]`).

### 2. IPC is hand-rolled POSIX shmem + semaphores, not PG's shared memory or libpq

The client↔worker transport is a `KVMessageQueue` of four channels backed by
POSIX shared memory (`shm_open`/`mmap`) and **unnamed `sem_t` semaphores**, not
PG's `ShmemAlloc`/LWLock world (`[[knowledge/subsystems/storage-ipc]]`):

- A **circular request channel** (N producers → 1 consumer) using a ring buffer
  with `posMutex`/`putMutex`/`empty`/`full` semaphores
  (`src/ipc/kv_channel.h:68-98`) `[verified-by-code]`.
- **Two simple response channels** (`MSGRESQUEUELENGTH 2`) leased per in-flight
  request (`src/ipc/kv_mq.h:23,49-53`; `LeaseResponseChannel` at
  `src/server/kv_worker.cc:534-545`) `[verified-by-code]`.
- A **control channel** of two semaphores (`workerReady`, `workerDesty`) that
  synchronizes worker startup/teardown with the manager
  (`src/ipc/kv_channel.h:140-162`; `queue_->Wait(WorkerReady)` at
  `src/server/kv_manager.cc:78`) `[verified-by-code]`.

The whole POSIX surface (`ShmOpen`/`Mmap`/`Munmap`/`Ftruncate`/`Sem*`) is
wrapped in `src/ipc/kv_posix.h:19-51` `[verified-by-code]`. The 64 KB message
buffer (`MSGBUFSIZE 65536`, `src/ipc/kv_channel.h:28`) is too small for bulk
scan results, so those go through a **second, per-cursor shared-memory
segment**: the worker `ShmOpen`s a name like `/KVReadBatch{pid}{relId}{opid}`,
`mmap`s it, fills it with a batch of KV pairs, and hands the backend the name to
`mmap` on its side (`src/server/kv_worker.cc:256-298`, client side
`:582-619`) `[verified-by-code]`. This is a bespoke re-implementation of a
`BufferAccessStrategy`-style batched read (`[[knowledge/subsystems/storage-buffer]]`)
entirely outside PG's memory manager.

### 3. No WAL, no MVCC, no buffer manager — PG's entire storage stack is bypassed

RocksDB provides its own durability (its own WAL) and compaction, so PG's
storage stack is simply not used. `OpenConn` sets `create_if_missing = true` and
otherwise takes RocksDB defaults (`src/server/kv_storage.cc:78-89`)
`[verified-by-code]`. There is **no `RelationData` heap, no visibility map, no
hint bits, no snapshot** on the KV data path — a scan is a RocksDB iterator
(`GetIter` → `SeekToFirst`, `src/server/kv_storage.cc:110-114`)
`[verified-by-code]`. Consequently the README lists as *limitations*: "Currently
no rollback, abort" and "once the table is created, cannot drop or add columns"
and "Do not support secondary index" (`README.md:90-94` `[from-README]`). An
INSERT is a fire-and-forget `KVPutRequest` issued from `ExecForeignInsert`
(`src/kv_fdw.c:999-1004`) `[verified-by-code]`; a ROLLBACK cannot undo it
because the write already landed in RocksDB with no PG transaction bracketing
it. This is the sharpest contrast with any heap-backed table and with
`[[knowledge/ideologies/orioledb]]` (which reimplements MVCC + WAL for its
engine); pgrocks-fdw simply forgoes transactional semantics.

### 4. Row identification and pushdown are pinned to column 1 and `=` only

`AddForeignUpdateTargets` adds column 1 as the junk row-identifier
(`src/kv_fdw.c:759-771`); `PlanForeignModify` hard-errors on any UPDATE that
touches column 1 (`"row identifier column update is not supported"`,
`src/kv_fdw.c:827-844`) `[verified-by-code]`. The only pushdown is a **key-point
lookup**: `GetKeyBasedQual` accepts an `OpExpr` only when the left side is
`Var` with `varattno == 1`, the right side is a `Const` or `Param`, and the
operator name is exactly `"="` (`src/kv_fdw.c:285-349`, `varattno != 1` bail at
`:306-309`, `"="` check at `:319`, `TODO: support more operators` at `:318`)
`[verified-by-code]`. A matching qual turns the scan into a single
`KVGetRequest` (`src/kv_fdw.c:626-639`); everything else is a full RocksDB
iterator scan with quals re-checked locally by the executor (`GetForeignPlan`
dumps all `scanClauses` into the plan qual list, `src/kv_fdw.c:245-282`)
`[verified-by-code]`. DELETE does a `KVGetRequest` (to return the old row) then
a `KVDeleteRequest` (`src/kv_fdw.c:1122-1137`); UPDATE is a blind
`KVPutRequest` overwrite at the same key (`src/kv_fdw.c:1067-1072`)
`[verified-by-code]`.

### 5. The key comparator is a PG type comparator pushed *into* RocksDB

So that RocksDB's LSM ordering matches PG's ordering of the key column,
`SetRelationComparatorOpts` extracts the key attribute's `cmp_proc`,
collation, byval, and length from the type cache
(`[[knowledge/idioms/typcache-entry-and-lookup]]`) into a `ComparatorOpts`
(`src/kv_utility.c:547-559`) `[verified-by-code]`, which is shipped over IPC in
`OpenArgs` (`src/kv_api.h:43-57`) and installed into RocksDB as a custom
`Comparator` via `NewDataTypeComparator` (`src/server/kv_storage.cc:58,82`)
`[verified-by-code]`. This is the analogue of `sqlite_fdw` injecting UDFs into
the SQLite handle — pgrocks-fdw injects a PG datum comparator into the LSM tree
so that ordered scans respect PG semantics.

### 6. Statistics and estimation are minimal

`AnalyzeForeignTable` returns `false` with no sample function
(`src/kv_fdw.c:1229-1263`) `[verified-by-code]` — like `sqlite_fdw` and
`tds_fdw`, it collects no stats. `GetForeignRelSize` sets `baserel->rows` from
RocksDB's own `estimate-num-keys` property (`KVCountRequest` →
`GetProperty("rocksdb.estimate-num-keys")`, `src/kv_fdw.c:185-188`,
`src/server/kv_storage.cc:100-108`) with a `TODO: better estimation` comment
`[from-comment]`; `GetForeignPaths` costs the single path as `startupCost = 0`,
`totalCost = baserel->rows` (`src/kv_fdw.c:211-223`) `[verified-by-code]`.

## Notable design decisions (with cites)

- **One RocksDB directory per foreign table**, named by relation OID under
  `$PGDATA/kv_fdw/{dbOid}/{relOid}` (`src/kv_utility.c:198-204`), so each table
  is an independent LSM tree with its own single-writer worker
  `[verified-by-code]`. Default path is overridable by a (undocumented in the
  validator) `filename` option (`src/kv_utility.c:238-243`).
- **Worker lifecycle is DDL-driven, not connection-driven.** Workers are
  launched lazily on first access (`src/client/kv_client.cc:52`) and terminated
  by `DROP TABLE`/`DROP DATABASE`/`DROP EXTENSION` through the utility hook
  (`src/kv_utility.c:840-850,857-878`) `[verified-by-code]`. The manager waits
  for the worker's `WorkerDesty` control signal before reaping the bgworker
  (`src/server/kv_manager.cc:93-135`) `[verified-by-code]`.
- **Bulk load bypasses per-row INSERT.** `COPY … FROM` goes through
  `KVCopyIntoTable` → `KVLoadRequest` (a fire-and-forget put with no response),
  reusing PG's `BeginCopyFrom`/`NextCopyFrom` machinery
  (`[[knowledge/idioms/tablesync-initial-copy]]` is the sibling COPY reuse)
  under `ShareUpdateExclusiveLock` (`src/kv_utility.c:568-668`)
  `[verified-by-code]`.
- **TOAST is flattened before serialization.** `ExecForeignInsert`/`Update`
  call `toast_flatten_tuple` when `HeapTupleHasExternal`, since the value bytes
  are stored raw in RocksDB with no TOAST pointer resolution downstream
  (`src/kv_fdw.c:982-987,1050-1055`) `[verified-by-code]`.
  (`[[knowledge/subsystems/access-heap]]` for the detoast contract.)
- **Optional VidarDB column store.** A compile-time `-DVIDARDB` path
  (`Makefile:8-13`) swaps RocksDB for VidarDB and adds a column-oriented storage
  format, a `storage 'column'` table option, `batch` capacity, and a
  `RangeQuery` scan API projecting only the target attributes
  (`src/kv_fdw.c:418-452`, `src/kv_api.h:89-123`, `src/kv_utility.c:245-253`)
  `[verified-by-code]`. This is the "supercharge analytics" ambition alluded to
  in `README.md:7`, and the closest this repo comes to
  `[[knowledge/ideologies/cstore_fdw]]` / `[[knowledge/ideologies/hydra-columnar]]`
  columnar FDW-storage.
- **`printf` debug tracing everywhere.** Nearly every callback opens with a
  `printf("\n----%s----\n", __func__)` (`src/kv_fdw.c:101,193,230,…`) — a
  development artifact, not production logging, and a marker of the extension's
  "PG13-only, report bugs" maturity (`README.md:15` `[from-README]`).

## Links into corpus

- `[[knowledge/subsystems/foreign]]` — the `FdwRoutine` dispatch + catalog
  accessors this extension plugs into; the single most important cross-ref.
- `[[knowledge/idioms/fdw-routine-callbacks]]` + `[[knowledge/idioms/fdw-iterate-scan]]`
  — the callback set and the `ExecClearTuple`/`ExecStoreVirtualTuple` scan loop
  (`src/kv_fdw.c:618-660`) this extension follows, minus a tuplestore.
- `[[knowledge/idioms/fmgr]]` — `PG_FUNCTION_INFO_V1` handler/validator and the
  event-trigger function plumbing.
- `[[knowledge/idioms/background-worker-startup]]` — the static manager
  (`RegisterBackgroundWorker`) + dynamic per-table worker
  (`RegisterDynamicBackgroundWorker`, `bgw_extra`, `WaitForBackgroundWorkerStartup`)
  lifecycle; pgrocks-fdw is a strong worked example.
- `[[knowledge/subsystems/storage-ipc]]` — the contrast: pgrocks-fdw rolls its
  own POSIX shmem + `sem_t` message queue instead of PG's shmem/LWLock IPC.
- `[[knowledge/idioms/process-utility-hook-chain]]` — `KVProcessUtility`
  intercepting COPY / DROP / ALTER / DROP DATABASE.
- `[[knowledge/ideologies/sqlite_fdw]]` — the "embedded engine linked into the
  backend" sibling; pgrocks-fdw is the "embedded engine in a *separate process*"
  variant (same "local, not remote" inversion, opposite process model).
- `[[knowledge/ideologies/cstore_fdw]]` + `[[knowledge/ideologies/hydra-columnar]]`
  — FDW-as-storage-engine siblings; the VidarDB column path is the analytics
  overlap.
- `[[knowledge/ideologies/orioledb]]` — the "pluggable LSM/COW storage that
  *does* reimplement MVCC + WAL" foil; pgrocks-fdw deliberately forgoes both.
- `[[knowledge/ideologies/tds_fdw]]` + `[[knowledge/ideologies/wrappers]]` — the
  conformant-C and Rust-framework FDW reference points for the callback surface.
- `[[knowledge/idioms/memory-contexts]]` / `[[knowledge/idioms/error-handling]]`
  — the per-scan palloc'd `TableReadState`/`TableWriteState` and the
  `ERRCODE_CONFIGURATION_LIMIT_EXCEEDED` "too many background workers" report
  (`src/client/kv_client.cc:59-64`).

> Corpus gap: as with `sqlite_fdw`, there is no idiom doc for the **FDW
> key/value serialization + varint-length encoding** pattern
> (`SerializeTuple`/`DeserializeAttribute`). More notably, there is no idiom
> doc for the **hand-rolled POSIX-shmem client/server bgworker IPC** pattern
> pgrocks-fdw uses — distinct from both PG's shmem/LWLock IPC and from
> `[[knowledge/idioms/parallel-context-and-dsm]]` (DSM). Worth an
> `idioms/posix-shmem-bgworker-ipc.md` if a second extension is found using it.

## Sources

Fetched 2026-07-13 (branch `master`), all via
`https://raw.githubusercontent.com/vidardb/pgrocks-fdw/master/<path>`:

- `README.md` @ 2026-07-13T00:00Z → HTTP 200 (166 lines).
- `Makefile` @ 2026-07-13T00:00Z → HTTP 200 (OBJS list mapped the source tree).
- `kv_fdw.control` @ 2026-07-13T00:00Z → HTTP 200 (5 lines).
- `kv_fdw--0.0.1.sql` @ 2026-07-13T00:00Z → HTTP 200 (handler/validator/FDW +
  `kv_ddl_event_end` event trigger).
- `src/kv_fdw.c` @ 2026-07-13T00:00Z → HTTP 200 (1326 lines; the FdwRoutine +
  scan/modify lifecycle + key/value serialization).
- `src/kv_fdw.h` @ 2026-07-13T00:00Z → HTTP 200 (57 lines).
- `src/kv_api.h` @ 2026-07-13T00:00Z → HTTP 200 (134 lines; the client↔worker
  request API + arg structs).
- `src/kv_utility.c` @ 2026-07-13T00:00Z → HTTP 200 (884 lines; `_PG_init`,
  utility hook, event trigger, COPY, varint serialization, comparator opts).
- `src/client/kv_client.cc` @ 2026-07-13T00:00Z → HTTP 200 (133 lines; the
  per-relation worker-client map).
- `src/server/kv_manager.cc` @ 2026-07-13T00:00Z → HTTP 200 (265 lines; manager
  bgworker + `LaunchKVManager`).
- `src/server/kv_manager.h` @ 2026-07-13T00:00Z → HTTP 200 (`KVWorkerHandle`
  map).
- `src/server/kv_worker.cc` @ 2026-07-13T00:00Z → HTTP 200 (827 lines; worker
  bgworker owning `conn_`, `LaunchKVWorker`, batch shmem transport).
- `src/server/kv_worker.h` @ 2026-07-13T00:00Z → HTTP 200.
- `src/server/kv_storage.cc` @ 2026-07-13T00:00Z → HTTP 200 (RocksDB/VidarDB
  `OpenConn`/`Get`/`Put`/iterator; first 140 lines read in depth).
- `src/server/kv_storage.h` @ 2026-07-13T00:00Z → HTTP 200.
- `src/ipc/kv_channel.h` @ 2026-07-13T00:00Z → HTTP 200 (164 lines; circular /
  simple / control channels + `sem_t` layout).
- `src/ipc/kv_mq.h` @ 2026-07-13T00:00Z → HTTP 200 (57 lines; the 4-channel
  message queue).
- `src/ipc/kv_posix.h` @ 2026-07-13T00:00Z → HTTP 200 (54 lines; shm/mmap/sem
  wrappers).

Also fetched but only skimmed: `src/ipc/kv_posix.cc`, `src/ipc/kv_message.{cc,h}`,
`src/ipc/kv_channel.cc`, `src/ipc/kv_mq.cc` (IPC implementations; behavior
inferred from the headers above and the worker/manager call sites).

**404 probes** (paths that do NOT exist, recorded so future runs skip them):
`src/kv_shm.c`, `src/kv_shm.h`, `src/kv_posix.cc` (real path is
`src/ipc/kv_posix.cc`), `src/kv_posix.h`, `src/kv_api.cc`, `src/kv_storage.h`,
`src/kv_storage.cc` (real path is `src/server/kv_storage.cc`),
`src/client/kv_client.h` (client has no header; declarations live in
`src/kv_api.h` + `src/server/kv_manager.h`).
</content>
