# PGPROC — the per-backend shared-memory anchor

- **Source path:** `source/src/include/storage/proc.h`
- **Last verified commit:** `e18b0cb7344` (cites re-anchored 2026-06-12 by
  pg-quality-auditor; previously `ef6a95c7c64`)
- **Companion docs:** `knowledge/files/src/include/storage/proc.h.md`,
  `knowledge/files/src/backend/storage/lmgr/proc.c.md`,
  `knowledge/files/src/backend/storage/ipc/procarray.c.md`

## 1. What it is

Every running backend (and every aux process that takes a slot — most do,
syslogger does not) has exactly one `PGPROC` entry in shared memory. The
`PROC_HDR` struct in shmem holds the array; each backend caches its own
slot pointer in the global `MyProc` for the duration of its life.

`PGPROC` is the join point between five separate subsystems:

1. **Transaction visibility** — `xid`, `xmin`, `subxids[]` published here for
   `GetSnapshotData` to read.
2. **Lock manager** — heavyweight lock-holder identity; fast-path entries
   for relation locks.
3. **Sinval** — `ProcState.nextMsgNum` for cache-invalidation queue read
   position.
4. **Inter-backend signaling** — latches, condition variables, procsignal
   slot.
5. **Wait state for views** — `pg_stat_activity` reads PGPROC fields plus
   `BackendStatus` (separate, in shmem, set by the backend itself).

## 2. The fields, grouped

### Identity

```
ProcNumber          procNumber       // 0..MaxBackends-1
int                 pid              // OS pid
int                 pgxactoff        // offset into PROC_HDR.pgxacts[]
BackendType         backendType      // B_BACKEND, B_AUTOVAC_WORKER, ...
int                 databaseId       // current MyDatabaseId
Oid                 roleId           // session userid
```

### MVCC

```
TransactionId       xid              // my xact's xid (Invalid if none)
TransactionId       xmin             // floor below which I won't read
uint32              subxidStatus     // subxid array overflow flag bits
struct {                              // up to PGPROC_MAX_CACHED_SUBXIDS sub-xids
    TransactionId   subxidArray[64];  // cached here; overflow falls back to subtrans SLRU
    int             count;
} subxids;
```

`xid` and `xmin` are read by other backends building snapshots — they're
written by *me* and read by *anybody*. The procarray walks all PGPROCs to
build a snapshot. This is the bottleneck `xactCompletionCount` fast-path
exists to avoid (see `knowledge/subsystems/storage-ipc.md` §6).

### Heavyweight lock state

```
SHM_QUEUE           myProcLocks[NUM_LOCK_PARTITIONS];   // per-partition lock-holding chain
LOCKMASK            heldLocks;       // bitmap of lock-modes currently held by me
LOCK               *waitLock;        // lock I'm waiting on, if any
PROCLOCK           *waitProcLock;
int                 waitStatus;      // STATUS_OK / STATUS_WAITING / STATUS_ERROR
LOCKMODE            waitLockMode;
```

The waitLock/Lock-mode/Status fields are what `pg_stat_activity.wait_event`
reads via `pgstat`.

### Fast-path (relation locks only)

```
LWLock              fpInfoLock;           // protects per-backend fast-path state
uint64             *fpLockBits;           // lock modes held per fast-path slot
Oid                *fpRelId;              // slots for rel oids
bool                fpVXIDLock;           // holding a fast-path VXID lock?
LocalTransactionId  fpLocalTransactionId; // lxid for fast-path VXID lock
```

Fast-path lets a backend take a weak relation lock (AccessShareLock,
RowShareLock, RowExclusiveLock) without touching the main heavyweight lock
table. The slot is reserved when the lock is acquired, freed when released.
On contention with a strong lock, the strong-locker transfers all fast-path
entries to the main table — see `lock.c` `FastPathTransferRelationLocks`.

As of PG18 the slot arrays are dynamically sized (hence `fpLockBits`/`fpRelId`
are now pointers, not fixed C arrays): the per-backend count is
`FastPathLockSlotsPerBackend() = FP_LOCK_SLOTS_PER_GROUP (16) *
FastPathLockGroupsPerBackend`, where the group count scales with
`max_locks_per_transaction` up to `FP_LOCK_GROUPS_PER_BACKEND_MAX` (1024).

[verified-by-code `proc.h:329-335` (fields), `proc.h:101-104`
(`FastPathLockSlotsPerBackend`), `lock.c:2862-2954`
(`FastPathTransferRelationLocks`)]

### Signaling

```
sig_atomic_t        procSignalFlags[NUM_PROCSIGNALS];   // ProcSignalReason flags
Latch              *procLatch;       // the latch SetLatch sets via SIGURG
ConditionVariable  *cvWaitLink;      // CV linked-list node
```

Setting a process's procLatch sends SIGURG to the OS pid. The signal is
delivered to a `signalfd` registered in `WaitEventSetWait`'s epoll set —
see `knowledge/subsystems/storage-ipc.md` §6.

### Sinval

The `ProcState` array (in SISeg shmem, NOT in PGPROC) carries per-backend
sinval read positions. PGPROC just holds the `pgprocno`/`procNumber`
identity used to index into ProcState.

### Group-locking (parallel query)

```
PGPROC             *lockGroupLeader;     // leader's PGPROC, NULL if not in a group
dlist_head          lockGroupMembers;    // leader-only: list of member PGPROCs
dlist_node          lockGroupLink;       // my member link, if I'm a member
```

Lock-group members are considered as one "logical xact" by the heavyweight
lock mgr — they don't block each other. Used by parallel workers to share
relation locks with the leader. Members are linked via `lockGroupLink` into
the leader's `lockGroupMembers` dlist (not a `List *` of pgprocnos).
[verified-by-code `proc.h:304-306`]

### Auxiliary process slot (non-backend)

The aux-process subset of PGPROC slots is `PROC_HDR.allProcs[MaxBackends..NumAllSlots)`.
Aux processes (checkpointer, walwriter, bgwriter, etc.) use the same struct
but most fields are unused — only the latch, identity, and signaling
machinery matter.

## 3. The shmem layout

```
PROC_HDR
├── freeProcs              (linked list of unused PGPROC slots)
├── numActiveProcs
├── allProcs[]              (array of PGPROC, length = MaxBackends + NumAuxProcs)
├── allPgXact[]             (parallel array of PGXACT for hot fields)
└── ...
```

A separate `PGXACT[]` array used to hold the most-snapshot-hot fields
(xid, xmin, vacuumFlags) in a cache-friendly contiguous block — refactored
into PGPROC in PG14 when the procarray fast path became atomics-based.
Older docs may reference PGXACT; ignore them and read current proc.h.

## 4. Common bugs touching PGPROC

- **Writing to your own PGPROC fields without a memory barrier when the
  field is read lock-free by others** — `MyProc->xmin` updates need a
  `pg_write_barrier()` so readers see the new value before they see any
  later actions you take. Most callers go through `ProcArrayInstall*`
  helpers which handle this correctly.
- **Holding fpInfoLock across long operations** — it blocks every
  fast-path lock release for this backend. The strong-lock transfer
  protocol depends on being able to acquire it quickly.
- **Forgetting to clear `MyProc->xid` at xact end before clearing
  `MyProc->xmin`** — the MVCC ordering rule (`IsInProgress` before
  `DidCommit`) depends on `xid` being cleared AFTER pg_xact commit is
  recorded. The standard `xact.c` paths handle this.
- **Pinning a PGPROC pointer beyond your own xact** — PGPROC slots are
  reused; another backend may move in. The pgprocno (small int) is the
  stable identity, not the pointer.

## 5. Useful greps

```
# Where MyProc is read
grep -rn 'MyProc->' source/src/backend/

# Where the procarray walk happens
grep -n 'GetSnapshotData\|ProcArrayWalk' source/src/backend/storage/ipc/procarray.c

# Where group-locking is enforced
grep -n 'lockGroupLeader\|lockGroupMembers' source/src/backend/storage/lmgr/

# Where fast-path lock entries live
grep -n 'fpInfoLock\|fpRelId\|FAST_PATH' source/src/backend/storage/lmgr/lock.c
```

## 6. Glossary

- **PGPROC**: per-backend shmem struct. The "I exist" anchor.
- **PROC_HDR**: shmem header carrying the PGPROC array + freelist.
- **MyProc**: per-backend cached pointer into PROC_HDR.allProcs[].
- **procNumber / pgprocno**: stable small-int identity, distinct from OS pid.
- **Fast-path lock**: weak relation lock recorded in PGPROC.fpRelId[]
  instead of the main lock table. Slot count is dynamic since PG18
  (`FastPathLockSlotsPerBackend()`, 16 per group × group count scaling with
  `max_locks_per_transaction`); was a fixed 16 per backend in older releases.
- **Lock group**: leader + parallel workers sharing relation locks.
- **PGXACT**: legacy hot-field array; merged back into PGPROC in PG14.

## Call sites
<!-- callsites:auto -->

*Auto-extracted from `source/<path>:<line>` cites in this doc's prose (bullets and free text).*
*Refresh via `scripts/populate-idiom-callsites.py` — edits inside this block are overwritten.*

| File | Line | Role |
|---|---:|---|
| [`src/include/storage/proc.h`](../files/src/include/storage/proc.h.md) | — | Source path |

<!-- /callsites:auto -->
