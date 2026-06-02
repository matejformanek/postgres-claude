# Review: SearchSysCache1 under ProcArrayLock LW_SHARED — is this OK?

**No. The patch is wrong, and the commit-message justification is misleading.** Multiple things are broken; "LWLocks are error-safe" is a true but incomplete sentence that masks the real problems.

## (a) The "error-safe" claim is technically true but irrelevant

It is true that `ereport(ERROR)` while holding an LWLock auto-releases it — the cleanup runs in the LWLock release-all path during xact abort (`source/src/backend/storage/lmgr/lwlock.c`; skill §2.2). But "the lock is released on error" is not the bar for "this is OK to do". The bar is also: (i) does this nest correctly under existing lock-ordering invariants, (ii) does it deadlock with other ProcArrayLock holders, (iii) is the hold time bounded.

So the commit-message reasoning is a non-sequitur. Error safety prevents *leaking* the lock; it does nothing about deadlocks or hold-time problems.

## (b) Implicit lock-ordering claim — the real bug

`SearchSysCache1` is **not** a leaf operation. On a syscache miss it:

1. Opens the catalog relation (acquires `AccessShareLock` on `pg_authid`, a **heavyweight lock**).
2. Begins a heap scan / index scan, which acquires **buffer pins and content locks** (LWLocks on `BufferDesc.content_lock`, plus a `BufMapping` partition LWLock for the lookup).
3. May trigger relcache/catcache invalidation processing, which can take `SInvalReadLock` / `SInvalWriteLock`.
4. May allocate (palloc) in `CacheMemoryContext`.

So this patch claims that the following lock order is safe:

```
ProcArrayLock (LWLock)
  → LOCKTAG_RELATION on pg_authid (heavyweight)
  → BufMapping partition LWLock
  → BufferDesc.content_lock (LWLock)
  → SInvalReadLock (LWLock)
```

Skill §3 rule 1 (partitioned-LWLock ordering) and the general "pick one global order" smell test (§5) both apply: if **any other code path** takes `ProcArrayLock` *after* a buffer content lock, or after a BufMapping partition lock — and many paths do — you have a silent LWLock deadlock waiting to trigger.

ProcArrayLock is one of the most-contended locks in the system; it's taken on every snapshot acquisition, every transaction commit, every backend startup/exit. The invariant *throughout the backend* is that ProcArrayLock is taken **early** — before catalog access, before buffer locks — and held briefly. This patch inverts that.

The skill warns against this exact pattern in §5: "I'm holding an LWLock and calling something that does I/O — fine for correctness… but bad for throughput. Consider releasing first." Syscache lookup is much worse than I/O: it can take other LWLocks and a heavyweight lock.

## (c) CHECK_FOR_INTERRUPTS / cancel interaction

Skill §2.2: "Don't hold across long waits. 'It is therefore not a good idea to use LW locks when the wait time might exceed a few seconds.' (`source/src/backend/storage/lmgr/README:43-45`) — query-cancel is held off while waiting."

A syscache miss can:
- Wait on a BufMapping partition LWLock that another backend is holding while doing I/O.
- Wait on the heavyweight `pg_authid` `AccessShareLock` (which conflicts with `AccessExclusiveLock` taken by `REVOKE`/`DROP ROLE`).

Each of those waits is **uncancellable** while holding ProcArrayLock. So a user issuing `pg_cancel_backend()` against the stuck backend has no effect — the backend cannot return to `CHECK_FOR_INTERRUPTS` until it releases ProcArrayLock, which it cannot do until the wait clears. Meanwhile every other backend trying to take a snapshot or commit is also waiting on ProcArrayLock. This is a system-wide stall, not a single-backend issue.

This is exactly the "LWLock with `pg_cancel_backend()` won't help" pattern flagged in `README:39-45` and the overview.

## (d) MAX_SIMUL_LWLOCKS

Skill §2.2: "Cap your simultaneous holdings under `MAX_SIMUL_LWLOCKS = 200`."

`SearchSysCache1` on a miss can acquire several LWLocks transiently (buffer content locks, BufMapping partition, SInval). Each acquire+release nets to zero, so the *peak* increment is small (maybe 3-5). MAX_SIMUL_LWLOCKS = 200 is unlikely to be exceeded by this patch alone.

However, the *meaningful* version of this concern is: ProcArrayLock + N transient LWLocks taken inside the syscache lookup means the held-set is larger and harder to reason about during deadlock analysis (which is on you, since LWLocks have no detector — skill §3 rule "silent LWLock deadlock"). So MAX_SIMUL_LWLOCKS is a non-issue numerically, but it's a symptom of "you are taking too many locks at once."

## (e) Does LW_EXCLUSIVE change anything?

It makes everything *worse*, not better:

- **Contention**: LW_EXCLUSIVE on ProcArrayLock blocks every snapshot acquisition, every commit, every backend startup, in addition to other writers. With this patch, every one of those waits during the syscache I/O.
- **Deadlock surface**: same as LW_SHARED but now the ordering violation against any other path that takes ProcArrayLock LW_SHARED inside catalog access is symmetric — both directions deadlock.
- **The error-safety argument is identical** — auto-release on `ereport(ERROR)` is independent of mode.

The qualitative bug is the same; the magnitude is larger.

## What the developer should do

- **Hoist the syscache lookup out of the ProcArrayLock section.** Copy the relevant fields out under the lock, release, then do the syscache work. If the syscache result has to influence what's done under the lock, do it in two phases: prefetch under no lock, take ProcArrayLock, check that the cached value is still consistent, act.
- If a per-PGPROC field needs to be added that requires catalog data to compute, compute it in the backend's own context (no shared lock at all) and publish to PGPROC under ProcArrayLock as a single store.

## Citations

- `source/src/backend/storage/lmgr/README:23-26` — LWLock error-safe release.
- `source/src/backend/storage/lmgr/README:39-45` — query-cancel held off during LWLock wait; don't use LWLock when wait may exceed seconds.
- `source/src/backend/storage/lmgr/lwlock.c` — `MAX_SIMUL_LWLOCKS = 200`, error-cleanup path.
- `source/src/include/storage/proc.h` — ProcArrayLock semantics.
- `source/src/backend/storage/ipc/procarray.c` — note brief hold times in existing call sites.
- `source/src/backend/utils/cache/catcache.c` / `syscache.c` — `SearchSysCache1` is not a leaf operation.
- Skill `.claude/skills/locking/SKILL.md` §2.2, §3 rules 1 and 7, §5 smell tests.
