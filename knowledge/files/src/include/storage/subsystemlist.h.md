# `src/include/storage/subsystemlist.h`

- **Last verified commit:** `e18b0cb7344`
- **Lines:** ~91
- **Source:** `source/src/include/storage/subsystemlist.h`

The **canonical ordered list** of every built-in subsystem that has
shared-memory state, encoded as a guard-less, repeated-include header
in the classic PG X-macro pattern. Each line is
`PG_SHMEM_SUBSYSTEM(name)`; the caller defines `PG_SHMEM_SUBSYSTEM` to
do whatever it wants (extern declaration, registration, manifest
dump for tooling). PG18-era infrastructure that replaced the old
hand-coded `CreateSharedMemoryAndSemaphores` calls. [verified-by-code]
[from-comment] [inferred]

## API / declarations

Not a header in the conventional sense — every line is a single
`PG_SHMEM_SUBSYSTEM(<symbol>)` macro invocation. The list (in
order) is:

- **Locks first:** `LWLockCallbacks`. (Other inits may use LWLocks;
  even if startup is single-threaded.) [from-comment]
- **DSM:** `dsm_shmem_callbacks`, `DSMRegistryShmemCallbacks`.
- **XLOG + clog + buffers:** `VarsupShmemCallbacks`,
  `XLOGShmemCallbacks`, `XLogPrefetchShmemCallbacks`,
  `XLogRecoveryShmemCallbacks`, `CLOGShmemCallbacks`,
  `CommitTsShmemCallbacks`, `SUBTRANSShmemCallbacks`,
  `MultiXactShmemCallbacks`, `BufferManagerShmemCallbacks`,
  `StrategyCtlShmemCallbacks`, `BufTableShmemCallbacks`.
- **Lock + predicate:** `LockManagerShmemCallbacks`,
  `PredicateLockShmemCallbacks`.
- **Process table:** `ProcGlobalShmemCallbacks`,
  `ProcArrayShmemCallbacks`, `BackendStatusShmemCallbacks`,
  `TwoPhaseShmemCallbacks`, `BackgroundWorkerShmemCallbacks`.
- **Shared-inval:** `SharedInvalShmemCallbacks`.
- **Signaling:** `PMSignalShmemCallbacks`,
  `ProcSignalShmemCallbacks`.
- **Background daemons / replication:** `CheckpointerShmemCallbacks`,
  `AutoVacuumShmemCallbacks`, `ReplicationSlotsShmemCallbacks`,
  `ReplicationOriginShmemCallbacks`, `WalSndShmemCallbacks`,
  `WalRcvShmemCallbacks`, `WalSummarizerShmemCallbacks`,
  `PgArchShmemCallbacks`, `ApplyLauncherShmemCallbacks`,
  `SlotSyncShmemCallbacks`.
- **Other shared-state owners:** `BTreeShmemCallbacks` (vacuum work),
  `SyncScanShmemCallbacks`, `AsyncShmemCallbacks` (LISTEN/NOTIFY),
  `StatsShmemCallbacks`, `WaitEventCustomShmemCallbacks`,
  `InjectionPointShmemCallbacks` (only `#ifdef USE_INJECTION_POINTS`),
  `WaitLSNShmemCallbacks`, `LogicalDecodingCtlShmemCallbacks`,
  `DataChecksumsShmemCallbacks`.
- **AIO last:** `AioShmemCallbacks` (delegates to method-specific
  callbacks per-platform). [verified-by-code]

## Notable invariants / details

- The X-macro is consumed by at least two callers:
  - `subsystems.h` defines `PG_SHMEM_SUBSYSTEM(x)` as
    `extern const ShmemCallbacks x;` to forward-declare every symbol.
  - `ipci.c:RegisterBuiltinShmemCallbacks` redefines it to
    `RegisterShmemCallbacks(&(x));` to actually register each. [verified-by-code]
- **Order matters** (head comment line 19-21). LWLocks first; AIO
  last; everything in between has implicit ordering through which
  subsystem's init may consult which other subsystem's already-
  initialized state. Reordering is a silent-corruption-class change.
  [from-comment]
  [ISSUE-undocumented-invariant: subsystem ordering is load-bearing
  but only the LWLock-first and AIO-last constraints are documented
  inline; the rest of the order encodes dep edges nowhere
  written down (maybe)]
- The "X-macro" pattern enables tooling — the head comment names
  "automatic tools" as the reason for the file split. `headerscheck`
  is already special-cased to skip this file (`headerscheck:136`)
  because it isn't a normal header. [from-comment] [verified-by-code]
- `#ifdef USE_INJECTION_POINTS` is the only conditional entry; all
  others compile unconditionally even on builds that never use them
  (e.g. WalSummarizer on a single-node primary). [verified-by-code]

## Potential issues

- Lines 24-26. The LWLock-first comment says "Nothing else can be
  running during startup, so they don't need to do any locking yet,
  but we nevertheless allow it." That "we nevertheless allow it" is
  load-bearing — extension code registered into this flow with
  `SHMEM_CALLBACKS_ALLOW_AFTER_STARTUP` may legitimately need LWLocks
  during init, so LWLocks really must be first. Not just historical
  caution. [from-comment]
  [ISSUE-undocumented-invariant: LWLock-first is required for
  post-startup extension registrations (see
  `SHMEM_CALLBACKS_ALLOW_AFTER_STARTUP` in `shmem.h:167`), not just
  for built-in startup (nit)]
- Entire file. No tooling that I can spot guards the list against
  the matching `init_fn`/`request_fn`/`attach_fn` triple actually
  existing in the named `ShmemCallbacks` struct. Adding a
  `PG_SHMEM_SUBSYSTEM(FooCallbacks)` entry without supplying a
  matching `const ShmemCallbacks FooCallbacks` produces a link error
  at build time, but no friendlier message. [verified-by-code]
  [ISSUE-api-shape: misspelling a subsystem name here surfaces only
  as an obscure link error; could be a `StaticAssertDecl` in
  `subsystems.h` (nit)]
- Lines 82-84. `InjectionPointShmemCallbacks` is the only
  `#ifdef`-gated entry. If future opt-in subsystems (custom AM
  preregistration, distributed log shipping, etc.) take the same
  approach, the linear list becomes a maze of `#ifdef`s; might be
  worth pre-emptively documenting the convention. [inferred]
  [ISSUE-style: pattern for `#ifdef`-gated entries not documented in
  head comment (nit)]

## Cross-references

<!-- issues:auto:begin -->
- [Issue register — `include-storage`](../../../../issues/include-storage.md)
<!-- issues:auto:end -->
