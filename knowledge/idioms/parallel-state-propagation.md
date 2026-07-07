# Parallel queries — worker bootstrap and state propagation

The leader's `InitializeParallelDSM` serializes a dozen
subsystems into the DSM table-of-contents.  The worker's
`ParallelWorkerMain` reads them back in a **specific order**:
some subsystems have to be restored before others can possibly
work.  This doc walks the boot sequence and what each Serialize/
Restore pair does.

For the context lifecycle and DSM layout see
[[parallel-context-and-dsm]]; for launch/wait/error see
[[parallel-worker-launch-wait-and-errors]].

**Anchors** (all cites against `source/` at commit `e18b0cb7344`):
- `source/src/backend/access/transam/parallel.c:1300-1587` — `ParallelWorkerMain`
- `source/src/backend/utils/misc/guc.c` — GUC serialize/restore
- `source/src/backend/storage/lmgr/proc.c` — `BecomeLockGroupMember`
- `source/src/backend/utils/cache/relmapper.c` — `Restore RelationMap`

## The boot sequence in order

`parallel.c:1300-1587` [verified-by-code].  Twenty-two
ordered steps from worker fork to user-code entry:

```
 1. InitializingParallelWorker = true
 2. BackgroundWorkerUnblockSignals()
 3. ParallelWorkerNumber = bgw_extra
 4. CurrentMemoryContext = ALLOCSET_DEFAULT_SIZES (named "Parallel worker")
 5. dsm_attach(main_arg) + shm_toc_attach(PARALLEL_MAGIC)
 6. fps = shm_toc_lookup(PARALLEL_KEY_FIXED)
 7. before_shmem_exit(ParallelWorkerShutdown)
 8. Attach to error queue [PARALLEL_KEY_ERROR_QUEUE]
 9. pq_redirect_to_shm_mq + pq_set_parallel_leader
10. BecomeLockGroupMember(parallel_leader_pgproc)        ← gate; exit if fails
11. SetParallelStartTimestamps(fps->xact_ts, fps->stmt_ts)
12. Lookup entrypoint via PARALLEL_KEY_ENTRYPOINT
13. SetAuthenticatedUserId + SetSessionAuthorization + SetCurrentRoleId
14. BackgroundWorkerInitializeConnectionByOid(database_id, authuser, BYPASS_*)
15. SetClientEncoding(GetDatabaseEncoding())
16. RestoreLibraryState [PARALLEL_KEY_LIBRARY]   inside a tx
17. StartParallelWorkerTransaction [PARALLEL_KEY_TRANSACTION_STATE]
18. RestorePendingSyncs, RestoreRelationMap, RestoreReindexState, RestoreComboCIDState
19. AttachSession(session_dsm_handle)
20. RestoreSnapshot(active) + RestoreTransactionSnapshot, PushActiveSnapshot
21. InvalidateSystemCaches
22. RestoreGUCState + SetUserIdAndSecContext + SetTempNamespaceState
    + RestoreUncommittedEnums + RestoreClientConnectionInfo
    + InitializeSystemUser + AttachSerializableXact
23. InitializingParallelWorker = false
24. EnterParallelMode
25. entrypt(seg, toc)              ← user code runs here
26. ExitParallelMode + PopActiveSnapshot + EndParallelWorkerTransaction + DetachSession
27. pq_putmessage(PqMsg_Terminate)
```

Steps before 17 (`StartParallelWorkerTransaction`) can do
**syscache lookups, but no relation scans**.  Steps after
have a real transaction; user code (`entrypt`) runs in full
transactional context.

The ordering has been hard-won — most of the comments in
`ParallelWorkerMain` document **why a particular order**, not
just what happens.  Rearranging arbitrarily breaks things in
non-obvious ways.

## Phase 1 — Attach (steps 1-10)

### Attach to DSM and TOC

`parallel.c:1352-1361` [verified-by-code]:

```c
seg = dsm_attach(DatumGetUInt32(main_arg));
if (seg == NULL)
    ereport(ERROR, ...
            "could not map dynamic shared memory segment");
toc = shm_toc_attach(PARALLEL_MAGIC, dsm_segment_address(seg));
if (toc == NULL)
    ereport(ERROR, ...
            "invalid magic number in dynamic shared memory segment");
```

`shm_toc_attach` validates `PARALLEL_MAGIC` — if the leader
crashed and the postmaster recycled this DSM slot for some
other purpose, the magic mismatch catches it.

### Find the error queue and redirect output

`parallel.c:1378-1385` [verified-by-code]:

```c
error_queue_space = shm_toc_lookup(toc, PARALLEL_KEY_ERROR_QUEUE, false);
mq = (shm_mq *) (error_queue_space +
                 ParallelWorkerNumber * PARALLEL_ERROR_QUEUE_SIZE);
shm_mq_set_sender(mq, MyProc);
mqh = shm_mq_attach(mq, seg, NULL);
pq_redirect_to_shm_mq(seg, mqh);
pq_set_parallel_leader(fps->parallel_leader_pid,
                       fps->parallel_leader_proc_number);
```

Each worker gets its own slot in the error-queue block,
indexed by `ParallelWorkerNumber`.  `shm_mq_set_sender` tells
the queue "I'm the sender" so the leader's mq side knows it
has a real partner; this is what
`WaitForParallelWorkersToAttach` polls for.

`pq_redirect_to_shm_mq` is the magic that makes the worker's
`elog`/`ereport`/`NOTIFY`/progress-counter calls **just work**:
the protocol-message machinery has its destination
transparently swapped from "client socket" to "error mq".
User code calling `elog(ERROR, ...)` doesn't know it's in a
worker.

### Register the shutdown handler

`parallel.c:1370` [verified-by-code]:

```c
before_shmem_exit(ParallelWorkerShutdown, PointerGetDatum(seg));
```

`ParallelWorkerShutdown` at `parallel.c:1621-1647`
[verified-by-code] runs at process exit.  Two things:

1. **Notify the leader** that we're going down (if exiting
   abnormally — clean exits send `PqMsg_Terminate` via the
   normal channel).
2. **Detach the DSM** (technically optional since process exit
   handles it, but explicit cleanup helps in EXEC_BACKEND).

The notify is via `kill(leader_pid, SIGUSR1)` → procsignal
multiplexer → `HandleParallelMessageInterrupt` on the
leader.  This is what makes `WaitForParallelWorkersToFinish`
wake up when a worker crashes.

### Lock group membership — the gate

`parallel.c:1401-1403` [verified-by-code]:

```c
if (!BecomeLockGroupMember(fps->parallel_leader_pgproc,
                           fps->parallel_leader_pid))
    return;
```

The comment at lines 1393-1399 [from-comment]:

> Join locking group.  We must do this before anything that
> could try to acquire a heavyweight lock, because any
> heavyweight locks acquired to this point could block either
> directly against the parallel group leader or against some
> process which in turn waits for a lock that conflicts with
> the parallel group leader, causing an undetected deadlock.
> (If we can't join the lock group, the leader has gone away,
> so just exit quietly.)

The "leader gone away" case happens when the leader started a
parallel context, then aborted before workers attached.  The
PGPROC slot may have been recycled or the leader may have
become a non-leader.  Either way, no useful work can be done;
the worker exits without error.

After this point the worker can acquire heavyweight locks
without conflict against the leader.

## Phase 2 — Database connection (steps 11-15)

### Restore start timestamps

`parallel.c:1410` [verified-by-code]:

```c
SetParallelStartTimestamps(fps->xact_ts, fps->stmt_ts);
```

Sets `xactStartTimestamp` and `stmtStartTimestamp` so
`now()`, `transaction_timestamp()`, `statement_timestamp()`
return the same values in workers as the leader.  Must happen
before `StartTransactionCommand` (which Asserts these are
already set in parallel workers).

### Lookup entrypoint

`parallel.c:1417-1421` [verified-by-code]:

```c
entrypointstate = shm_toc_lookup(toc, PARALLEL_KEY_ENTRYPOINT, false);
library_name = entrypointstate;
function_name = entrypointstate + strlen(library_name) + 1;

entrypt = LookupParallelWorkerFunction(library_name, function_name);
```

The two strings live in a single TOC chunk, NUL-separated.
`LookupParallelWorkerFunction` checks the built-in registry
first (`InternalParallelWorkers[]`), then falls back to
`load_external_function` for extension-provided entries.

The lookup happens before `RestoreLibraryState`, so the
built-ins are always available; the fallback path is only
taken after the library state restore later.

### Identity restoration — three layers

`parallel.c:1429-1432` [verified-by-code]:

```c
SetAuthenticatedUserId(fps->authenticated_user_id);
SetSessionAuthorization(fps->session_user_id,
                        fps->session_user_is_superuser);
SetCurrentRoleId(fps->outer_user_id, fps->role_is_superuser);
```

PG identity has three layers:

| Layer | Set by | Meaning |
|---|---|---|
| **Authenticated user** | initial connection | who you logged in as |
| **Session user** | `SET SESSION AUTHORIZATION` | logical "session as" identity |
| **Current role** | `SET ROLE` | active role for permission checks |

All three propagate.  The `is_superuser` bits are
**recomputed by the leader and passed verbatim** to avoid
catalog lookups; the comment at lines 1424-1428
[from-comment]:

> No verification happens here, we just blindly adopt the
> leader's state.

This is safe because the leader did all the verification
when it took the snapshot; the worker just needs to inherit
the result.  Doing the checks ourselves would (a) waste work
and (b) potentially see a newer catalog than the leader if
catalog modifications happened.

### Database connection

`parallel.c:1440-1443` [verified-by-code]:

```c
BackgroundWorkerInitializeConnectionByOid(fps->database_id,
                                          fps->authenticated_user_id,
                                          BGWORKER_BYPASS_ALLOWCONN |
                                          BGWORKER_BYPASS_ROLELOGINCHECK);
```

`BGWORKER_BYPASS_ALLOWCONN` skips the "datallowconn = false"
check, because the leader already passed; `BGWORKER_BYPASS_ROLELOGINCHECK`
skips the rolcanlogin check for the same reason.

The comment at lines 1434-1438 [from-comment]:

> We skip connection authorization checks, reasoning that (a)
> the leader checked these things when it started, and (b) we
> do not want parallel mode to cause these failures, because
> that would make use of parallel query plans not transparent
> to applications.

So a parallel query never fails because the database stopped
allowing connections after the leader connected — the workers
power through.

## Phase 3 — Library + transaction (steps 16-18)

### Restore loaded shared libraries

`parallel.c:1460-1463` [verified-by-code]:

```c
libraryspace = shm_toc_lookup(toc, PARALLEL_KEY_LIBRARY, false);
StartTransactionCommand();
RestoreLibraryState(libraryspace);
CommitTransactionCommand();
```

The leader records every shared library it has loaded; the
worker walks the list and `load_external_function`s each one.
This happens **inside a transaction** because some library
init code might do catalog access (custom GUC registration
via `DefineCustomXxxVariable` needs `pg_authid` etc.).

The transaction is committed before the parallel-worker
transaction starts; library state must be globally consistent
before we can reasonably restore GUCs (which may include
extension-defined GUCs).

The comment at lines 1456-1458 [from-comment]:

> Load libraries that were loaded by original backend.  We
> want to do this before restoring GUCs, because the libraries
> might define custom variables.

### Start the parallel-worker transaction

`parallel.c:1466-1467` [verified-by-code]:

```c
tstatespace = shm_toc_lookup(toc, PARALLEL_KEY_TRANSACTION_STATE, false);
StartParallelWorkerTransaction(tstatespace);
```

This is not a regular `StartTransactionCommand`.  Parallel
workers participate in the **leader's** transaction; they
don't have their own XID.  `StartParallelWorkerTransaction`
(in `xact.c`) reconstructs the leader's transaction state
(top XID, subxact stack, command ID, etc.) into the worker's
`CurrentTransactionState`.

Workers can't:
- Allocate their own XID.
- Modify the catalog.
- Commit / abort the transaction.
- Do anything that would invalidate the leader's snapshot.

They **can**:
- Read with the leader's snapshot.
- Take heavyweight locks (via the lock group).
- Update non-shared local state (per-worker caches).
- Write WAL for index/sort spills if the caller (e.g.
  parallel index build) coordinates explicitly.

### Restore the four "catalog-affecting" states

`parallel.c:1475-1483` [verified-by-code]:

```c
pendingsyncsspace = shm_toc_lookup(toc, PARALLEL_KEY_PENDING_SYNCS,
                                   false);
RestorePendingSyncs(pendingsyncsspace);
relmapperspace = shm_toc_lookup(toc, PARALLEL_KEY_RELMAPPER_STATE, false);
RestoreRelationMap(relmapperspace);
reindexspace = shm_toc_lookup(toc, PARALLEL_KEY_REINDEX_STATE, false);
RestoreReindexState(reindexspace);
combocidspace = shm_toc_lookup(toc, PARALLEL_KEY_COMBO_CID, false);
RestoreComboCIDState(combocidspace);
```

Four subsystems, each describing some piece of "what the
catalog looks like to me right now" that the worker must
match:

#### `PendingSyncs`

The list of files the current transaction has created.  Used
by `RelationNeedsWAL` to decide whether a relation needs WAL
or just an fsync at commit.  Workers reading from new tables
need this so they don't accidentally WAL-log reads.

#### `RelationMap`

The pg_class.relfilenode → filenode mapping that survives
across catalog truncation.  Used by mapped relations (shared
catalogs like pg_class itself).  Workers must see the same
mapping so they read the same physical files.

#### `ReindexState`

The list of indexes currently being REINDEXed (those for
which we should skip insertion).  CONCURRENT reindexes
specifically.

#### `ComboCIDState`

The map from combo CIDs to (cmin, cmax) pairs.  Combo CIDs
are created when a single tuple is written and then updated/
deleted within the same transaction; the cmin and cmax don't
fit in 4 bytes so they get a "combo" pointer.  Workers
reading rows the leader has self-updated need this map.

### Attach to the session DSM

`parallel.c:1486-1488` [verified-by-code]:

```c
session_dsm_handle_space =
    shm_toc_lookup(toc, PARALLEL_KEY_SESSION_DSM, false);
AttachSession(*(dsm_handle *) session_dsm_handle_space);
```

The session DSM holds shared per-session state — most
importantly the **RECORD typmod registry**.  Anonymous
record types get typmods assigned as they're encountered;
both leader and workers must agree on typmod assignments so
they can exchange tuples.

`AttachSession` is the worker side of `GetSessionDsmHandle`
(seen in [[parallel-context-and-dsm]]).

## Phase 4 — Snapshot restoration (step 20)

`parallel.c:1502-1508` [verified-by-code]:

```c
asnapspace = shm_toc_lookup(toc, PARALLEL_KEY_ACTIVE_SNAPSHOT, false);
tsnapspace = shm_toc_lookup(toc, PARALLEL_KEY_TRANSACTION_SNAPSHOT, true);
asnapshot = RestoreSnapshot(asnapspace);
tsnapshot = tsnapspace ? RestoreSnapshot(tsnapspace) : asnapshot;
RestoreTransactionSnapshot(tsnapshot,
                           fps->parallel_leader_pgproc);
PushActiveSnapshot(asnapshot);
```

The comment at lines 1490-1500 [from-comment] is the
authoritative explanation:

> If the transaction isolation level is REPEATABLE READ or
> SERIALIZABLE, the leader has serialized the transaction
> snapshot and we must restore it. At lower isolation levels,
> there is no transaction-lifetime snapshot, but we need
> TransactionXmin to get set to a value which is less than or
> equal to the xmin of every snapshot that will be used by
> this worker. The easiest way to accomplish that is to install
> the active snapshot as the transaction snapshot.

Three things:

1. **`tsnapspace` may be NULL** — `shm_toc_lookup(.., true)`
   returns NULL if the key is absent.  At Read Committed,
   no transaction snapshot was serialized; we fall back to
   `asnapshot` for both purposes.
2. **`RestoreTransactionSnapshot(snap, leader_pgproc)`** sets
   `TransactionXmin = snap->xmin` and registers the
   dependency on the leader.  See
   [[snapshot-export-historic-parallel]].
3. **`PushActiveSnapshot(asnapshot)`** makes the active
   snapshot the current snapshot — workers can do
   `GetActiveSnapshot` from here and get the same answer the
   leader would.

The leader's transaction snapshot must outlive every worker;
this is guaranteed because workers are in the leader's lock
group and the leader's commit waits for all workers to exit.

### Invalidate caches after snapshot change

`parallel.c:1514` [verified-by-code]:

```c
InvalidateSystemCaches();
```

The worker's catcache/relcache had whatever state it had at
`InitPostgres` time — likely empty.  But after pushing the
leader's snapshot, the worker now has a specific catalog
visibility model that may differ from a fresh backend's
default.  Invalidating the caches forces them to rebuild
against the new snapshot.

## Phase 5 — Final state restoration (step 22)

### GUC restoration

`parallel.c:1523-1524` [verified-by-code]:

```c
gucspace = shm_toc_lookup(toc, PARALLEL_KEY_GUC, false);
RestoreGUCState(gucspace);
```

The comment at lines 1517-1521 [from-comment]:

> We can't do this earlier, because GUC check hooks that do
> catalog lookups need to see the same database state as the
> leader.  Also, the check hooks for session_authorization and
> role assume we already set the correct role OIDs.

GUC restoration runs every variable's `assign_hook` (and
sometimes `check_hook`).  Some of these — like
`search_path`'s namespace lookup, or
`default_text_search_config`'s catalog probe — need catalog
access to validate values.  So GUCs come **after** the
catalog state is restored and the snapshot is pushed.

### User ID + sec context — second pass

`parallel.c:1534` [verified-by-code]:

```c
SetUserIdAndSecContext(fps->current_user_id, fps->sec_context);
```

This is the **current user** (different from session/authn/
role set earlier).  The security context bits capture things
like "SECURITY_RESTRICTED_OPERATION" (from a `LOCAL` SET in
a function) — workers must inherit these so privilege checks
match the leader's.

Comes after GUCs because `session_authorization` and `role`
GUC assign hooks would complain about a mismatched
`CurrentUserId`; we set them in the safe order.

### Temp namespace

`parallel.c:1537-1538` [verified-by-code]:

```c
SetTempNamespaceState(fps->temp_namespace_id,
                      fps->temp_toast_namespace_id);
```

If the leader has a temp namespace (created on first temp-table
use), the worker adopts its OID.  This is what makes
`SELECT * FROM pg_temp.tab` work the same in workers as in
the leader.

### Uncommitted enums

`parallel.c:1541-1543` [verified-by-code]:

```c
uncommittedenumsspace = shm_toc_lookup(toc, PARALLEL_KEY_UNCOMMITTEDENUMS,
                                       false);
RestoreUncommittedEnums(uncommittedenumsspace);
```

Enum values added by `ALTER TYPE ... ADD VALUE` mid-transaction
aren't visible to other backends until commit, but the
leader's parallel workers need to see them.  This restores
the in-transaction enum modifications.

### Client connection info + system user

`parallel.c:1546-1556` [verified-by-code]:

```c
clientconninfospace = shm_toc_lookup(toc, PARALLEL_KEY_CLIENTCONNINFO,
                                     false);
RestoreClientConnectionInfo(clientconninfospace);

if (MyClientConnectionInfo.authn_id)
    InitializeSystemUser(MyClientConnectionInfo.authn_id,
                         hba_authname(MyClientConnectionInfo.auth_method));
```

`ClientConnectionInfo` carries auth method, SSL cert info,
external authenticated identity, etc.  Functions like
`session_user_id()` and `pg_stat_ssl` need this to give the
right answers in worker contexts.

`InitializeSystemUser` sets `SYSTEM_USER` accordingly — a
relatively recent addition for auditing.

### Attach to serializable transaction

`parallel.c:1559` [verified-by-code]:

```c
AttachSerializableXact(fps->serializable_xact_handle);
```

For SERIALIZABLE isolation, the worker joins the SSI
machinery — sharing the leader's `SERIALIZABLEXACT` so
predicate locks accumulate centrally.

## Phase 6 — Run user code

`parallel.c:1565-1577` [verified-by-code]:

```c
InitializingParallelWorker = false;
EnterParallelMode();

entrypt(seg, toc);

ExitParallelMode();
PopActiveSnapshot();
EndParallelWorkerTransaction();
DetachSession();
pq_putmessage(PqMsg_Terminate, NULL, 0);
```

The user code (`entrypt(seg, toc)`) gets the DSM segment and
TOC; from there it looks up its own caller-defined keys
(typically per-worker tuple queues for parallel-aware nodes).

`EnterParallelMode` flags the worker as in-parallel-mode so
assertion-protected operations (catalog modification, XID
allocation, etc.) fire if user code tries them.

After user code returns:

1. `ExitParallelMode` lets us safely pop the active snapshot.
2. `PopActiveSnapshot` matches our earlier `PushActiveSnapshot`.
3. `EndParallelWorkerTransaction` is the parallel-mode
   transaction cleanup (does *not* commit — the leader will).
4. `DetachSession` releases the session DSM reference.
5. `pq_putmessage(PqMsg_Terminate)` is the clean-exit signal.

## `ParallelWorkerShutdown` — the abnormal-exit path

`parallel.c:1621-1647` [verified-by-code].  Runs as a
`before_shmem_exit` callback if the worker exits via
`proc_exit` (signal, FATAL, etc.).  Two main actions:

1. **Notify the leader** via SIGUSR1 to the leader's PID, so
   it wakes up and processes the terminating worker's last
   error queue messages.
2. **Detach the DSM** explicitly (some platforms benefit
   from this on EXEC_BACKEND).

Combined with the elog/ereport machinery's automatic flush
to the error queue, this ensures the leader always learns
about worker exits — clean (via `PqMsg_Terminate` in the
mainline) or unclean (via the shutdown handler).

## `ParallelWorkerReportLastRecEnd` — WAL flush coordination

`parallel.c:1593+` [verified-by-code]:

```c
void
ParallelWorkerReportLastRecEnd(XLogRecPtr last_xlog_end)
{
    Assert(MyFixedParallelState != NULL);

    SpinLockAcquire(&MyFixedParallelState->mutex);
    if (MyFixedParallelState->last_xlog_end < last_xlog_end)
        MyFixedParallelState->last_xlog_end = last_xlog_end;
    SpinLockRelease(&MyFixedParallelState->mutex);
}
```

Workers that generated WAL (parallel index build's
`_bt_parallel_build_main` for example) call this at exit to
publish their final `XactLastRecEnd`.  The leader's
`WaitForParallelWorkersToFinish` reads the spinlocked field
and updates its own `XactLastRecEnd`.  This is the
sync-replication-friendly path: the leader's commit waits
for the workers' WAL too.

## What's NOT serialized

A non-exhaustive list of state that the worker creates fresh,
rather than inheriting:

- **`MyProc`** — each worker has its own PGPROC slot.
- **Per-process memory contexts** (`TopMemoryContext`,
  `CacheMemoryContext`, etc.) — created by `InitPostgres`.
- **Local buffer caches** — each worker has its own.
- **Cached plans / prepared statements** — workers don't see
  the leader's plan cache.
- **`PortalContext` and the portal stack** — workers don't
  have portals; they're entered via `ParallelWorkerMain`,
  not via a SQL command.
- **`SPI` connections** — workers can call SPI but the
  connection is fresh.

The principle: **state visible to other backends doesn't
propagate; transaction-local state does** (mostly).

## Invariants worth remembering

1. **`InitializingParallelWorker = true` covers the bootstrap
   sequence.**  Cleared just before `entrypt` runs.  Some
   guards check it to relax checks during init.
2. **`BecomeLockGroupMember` must precede any heavyweight
   lock acquisition.**  Otherwise undetected deadlock.
3. **Identity restoration is "blind adopt"** — no validation.
   Leader already validated.
4. **Library load happens before GUC restore** — extensions
   may define GUCs.
5. **GUC restore happens after catalog state + snapshot** —
   GUC check hooks may do catalog lookups.
6. **`SetUserIdAndSecContext` is the LAST identity step** —
   it would trip GUC assign hooks if done earlier.
7. **`InvalidateSystemCaches` after snapshot install** —
   caches must rebuild against the new visibility.
8. **`tsnapspace` may be NULL at Read Committed** — fall
   back to `asnapshot`.
9. **Workers don't allocate XIDs and can't modify the
   catalog.**  Asserts in `xact.c` enforce this when
   `IsParallelWorker() && IsInParallelMode()`.
10. **`pq_redirect_to_shm_mq` makes `elog` transparent.**
    User code doesn't need to know it's in a worker.
11. **Workers exit by `pq_putmessage(PqMsg_Terminate)`** plus
    natural `proc_exit`.  The `before_shmem_exit` callback
    handles abnormal exits.
12. **`ParallelWorkerReportLastRecEnd` is spinlock-protected.**
    Multiple workers may publish concurrently.

## Useful greps

```bash
# The worker bootstrap entrypoint
grep -n "ParallelWorkerMain\|ParallelWorkerShutdown" \
    source/src/backend/access/transam/parallel.c

# Restore* sites
grep -rn "RestoreLibraryState\|RestoreGUCState\|RestoreComboCIDState\|RestorePendingSyncs\|RestoreRelationMap\|RestoreReindexState\|RestoreUncommittedEnums\|RestoreClientConnectionInfo" \
    source/src/backend/

# Start/End parallel-worker transaction
grep -n "StartParallelWorkerTransaction\|EndParallelWorkerTransaction\|SerializeTransactionState" \
    source/src/backend/access/transam/xact.c

# Lock group join
grep -rn "BecomeLockGroupMember\|BecomeLockGroupLeader\|lockGroupLeader\|lockGroupMembers" \
    source/src/backend/storage/lmgr/

# Identity propagation
grep -n "SetAuthenticatedUserId\|SetSessionAuthorization\|SetCurrentRoleId\|SetUserIdAndSecContext\|SetTempNamespaceState\|SetParallelStartTimestamps" \
    source/src/backend/

# WAL coordination
grep -n "ParallelWorkerReportLastRecEnd\|last_xlog_end" \
    source/src/backend/access/transam/parallel.c
```

## Call sites
<!-- callsites:auto -->

*Auto-extracted from `source/<path>:<line>` cites in this doc's prose (bullets and free text).*
*Refresh via `scripts/populate-idiom-callsites.py` — edits inside this block are overwritten.*

| File | Line | Role |
|---|---:|---|
| [`src/backend/access/transam/parallel.c`](../files/src/backend/access/transam/parallel.c.md) | 1300 | ParallelWorkerMain |
| [`src/backend/storage/lmgr/proc.c`](../files/src/backend/storage/lmgr/proc.c.md) | — | BecomeLockGroupMember |
| [`src/backend/utils/cache/relmapper.c`](../files/src/backend/utils/cache/relmapper.c.md) | — | Restore RelationMap |
| [`src/backend/utils/misc/guc.c`](../files/src/backend/utils/misc/guc.c.md) | — | GUC serialize/restore |

<!-- /callsites:auto -->

## Scenarios that use me
<!-- scenarios:auto -->

*Auto-derived from direct references + transitive file-overlap.*
*Refresh via `scripts/build-scenario-idiom-matrix.py`.*

- [`add-new-guc`](../scenarios/add-new-guc.md)
- [`add-new-plan-node`](../scenarios/add-new-plan-node.md)
- [`add-new-protocol-message`](../scenarios/add-new-protocol-message.md)

<!-- /scenarios:auto -->
## Cross-references

- [[parallel-context-and-dsm]] — the leader-side serialization
  that this doc's restorations consume.
- [[parallel-worker-launch-wait-and-errors]] — launch / wait /
  error machinery surrounding `ParallelWorkerMain`.
- [[snapshot-export-historic-parallel]] — `SerializeSnapshot`
  / `RestoreSnapshot` / `RestoreTransactionSnapshot`.
- [[guc-variables]] — GUC state serialization works because
  each variable knows its own marshal/unmarshal.
- [[locking]] — heavyweight lock groups are the cornerstone
  of safe lock sharing between leader and workers.
- [[commit-transaction-sequence]] —
  `StartParallelWorkerTransaction` reconstructs the leader's
  `TransactionState` chain.
- [[memory-contexts]] — the "Parallel worker" memory context
  becomes `CurrentMemoryContext` at boot.
- [[syscache-invalidation-flow]] — `InvalidateSystemCaches`
  forces a refresh after snapshot install.
- [[bgworker-and-extensions]] — `BackgroundWorkerInitializeConnectionByOid`
  + `BACKGROUND_WORKER_BYPASS_*` flags.
