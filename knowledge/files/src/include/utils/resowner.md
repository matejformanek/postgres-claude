# `src/include/utils/resowner.h`

**Pin:** `4b0bf0788b066a4ca1d4f959566678e44ec93422`

## Role

Defines `ResourceOwner` — the query-lifespan tracker that owns
buffer pins, cache refs, dsm segments, files, locks, etc., and
releases them in the right order on commit / abort / portal drop
[from-comment: lines 5-9]. See `utils/resowner/README` for the
algorithm.

## Public API

### Well-known owners [verified-by-code: lines 33-36]

- `CurrentResourceOwner` — usually points to the active executor
  context; switched by callers temporarily.
- `CurTransactionResourceOwner` — owner for the current
  (sub)transaction.
- `TopTransactionResourceOwner` — for the top transaction.
- `AuxProcessResourceOwner` — for non-postmaster auxiliary procs.

### Release phases [verified-by-code: lines 38-77]

```c
typedef enum {
    RESOURCE_RELEASE_BEFORE_LOCKS = 1,
    RESOURCE_RELEASE_LOCKS,
    RESOURCE_RELEASE_AFTER_LOCKS,
} ResourceReleasePhase;
```

Three phases run in order. Within each, resources released by
ascending `ResourceReleasePriority` (uint32).

Built-in BEFORE_LOCKS priorities:
`BUFFER_IOS=100`, `BUFFER_PINS=200`, `RELCACHE_REFS=300`,
`DSMS=400`, `JIT_CONTEXTS=500`, `CRYPTOHASH_CONTEXTS=600`,
`HMAC_CONTEXTS=700`.

Built-in AFTER_LOCKS priorities:
`CATCACHE_REFS=100`, `CATCACHE_LIST_REFS=200`,
`PLANCACHE_REFS=300`, `TUPDESC_REFS=400`, `SNAPSHOT_REFS=500`,
`FILES=600`, `WAITEVENTSETS=700`.

`RELEASE_PRIO_FIRST=1`, `RELEASE_PRIO_LAST=UINT32_MAX`, `0` invalid.

Rationale [from-comment: lines 41-46]: BEFORE_LOCKS releases
externally visible resources (buffer pins) so that when locks are
released, other backends see us as "fully out". AFTER_LOCKS is
backend-internal cleanup.

### Kind descriptor [verified-by-code: lines 83-120]

```c
typedef struct ResourceOwnerDesc {
    const char *name;
    ResourceReleasePhase release_phase;
    ResourceReleasePriority release_priority;
    void  (*ReleaseResource)(Datum res);
    char *(*DebugPrint)(Datum res);
} ResourceOwnerDesc;
```

**Callbacks must not fail** [from-comment: lines 88-90] — they run
post-commit/post-abort and any error is unrecoverable.

`DebugPrint` is used to print a WARNING when a resource leaks (was
remembered but not forgotten before commit).

### Resource-release callback hook [verified-by-code: lines 126-130]

`ResourceReleaseCallback(phase, isCommit, isTopLevel, arg)` — dlls
can register/unregister hooks via
`RegisterResourceReleaseCallback` / `Unregister...` (lines 154-157).

### Core ops [lines 137-152]

- `ResourceOwnerCreate(parent, name)`
- `ResourceOwnerRelease(owner, phase, isCommit, isTopLevel)`
- `ResourceOwnerDelete(owner)`
- `ResourceOwnerGetParent`, `ResourceOwnerNewParent` (reparenting).
- `ResourceOwnerEnlarge(owner)` — ensure slot space; **must be
  called BEFORE the action that creates the resource**, so the
  remember-step cannot OOM and leak the resource.
- `ResourceOwnerRemember(owner, value, kind)`
- `ResourceOwnerForget(owner, value, kind)`
- `ResourceOwnerReleaseAllOfKind(owner, kind)`

### Special-cased fast paths

- Locks: `ResourceOwnerRememberLock` / `ForgetLock` take a
  `LOCALLOCK *` directly [lines 163-165].
- AIO: `ResourceOwnerRememberAioHandle` / `ForgetAioHandle` for
  `dlist_node` (added with the async IO subsystem) [lines 167-170].

### Aux-process [lines 159-160]

`CreateAuxProcessResourceOwner` / `ReleaseAuxProcessResources`.

## Invariants

- **INV-ENLARGE-BEFORE** [from common knowledge of API; comment line
  148 is terse but contract is well-known] Callers must call
  `ResourceOwnerEnlarge(owner)` BEFORE the operation that returns
  the resource; the subsequent `Remember` must not allocate (else
  the resource is held without being tracked).
- **INV-NO-FAIL-RELEASE** [from-comment: lines 88-90] Release
  callbacks must not throw. An `ereport(ERROR, ...)` from here is
  fatal because the caller has already committed/aborted.
- **INV-PHASE-ORDER** [from-comment: lines 41-46] BEFORE_LOCKS
  resources released first, then locks, then AFTER_LOCKS. Buffer
  pins MUST be in BEFORE_LOCKS or other backends see us holding a
  pin after we've released the relation lock.
- **INV-PRIORITY-ZERO** [verified-by-code: line 79] Priority 0 is
  invalid.

## Trust boundary (Phase D)

- Extensions ship their own `ResourceOwnerDesc` and call
  `ResourceOwnerRemember`. The chosen phase/priority determines
  ordering with respect to built-in cleanup. Mis-ordering (e.g.
  releasing a buffer pin in AFTER_LOCKS) breaks the BEFORE_LOCKS
  invariant and exposes other backends to stale pins after the lock
  is gone.
- `ResourceReleaseCallback` hook lets a loaded module observe
  every resource release on every transaction — broad surface,
  often used by debugging extensions, but a misbehaving hook can
  cause cluster-wide ERROR-on-cleanup PANIC.

## Cross-refs

- `utils/resowner/README` (source: `source/src/backend/utils/resowner/`)
  — the algorithm.
- `utils/portal.h` — every Portal owns one.
- `utils/snapmgr.h`, `utils/plancache.h`, `storage/bufmgr.h` —
  primary clients (use the *_REFS / *_PINS priorities).
- `storage/aio_*` — AIO handles since PG18.

## Issues

- [ISSUE-CONTRACT: `ResourceOwnerEnlarge` "must call before remember"
  contract is in the README, not in the header — easy to miss; lints
  don't catch it (medium)] — line 148.
- [ISSUE-INV: no compile-time check that an extension's chosen phase
  matches the resource's external visibility (e.g. buffer-like
  resources must be BEFORE_LOCKS) — left to author discipline (low)]
  — lines 41-46.
