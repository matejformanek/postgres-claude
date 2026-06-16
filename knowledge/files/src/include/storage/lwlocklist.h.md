# `src/include/storage/lwlocklist.h`

- **Last verified commit:** `4b0bf0788b066a4ca1d4f959566678e44ec93422`
- **Lines:** 142

## Role

**The master list of predefined LWLocks and built-in tranches**,
designed to be `#included` multiple times with different
`PG_LWLOCK(id, name)` / `PG_LWLOCKTRANCHE(id, name)` macro
definitions — the **X-macro / INCLUDE-trick** pattern. Same source
text generates:

1. The `BuiltinTrancheIds` enum (via lwlock.h definitions)
2. The `MainLWLockArray` index positions
3. The tranche-name lookup table for `pg_stat_activity` and
   `pg_lwlock_acquire_locks` wait-event reporting
4. The `lwlocknames.h` constants via `generate-lwlocknames.pl`

[from-comment] `source/src/include/storage/lwlocklist.h:5-11`

## The current registry

- **Single LWLocks** (`PG_LWLOCK`): 47 active entries IDs 2..57
  (gaps at 0, 1, 10-12, 14-15, 26, 31, 38, 42, 45 mark removed
  locks — the comment instructs **NOT to reuse gap IDs** for
  external debugger compatibility). Examples:
  `OidGen(2)`, `XidGen(3)`, `ProcArray(4)`, `WALInsert(WAL_INSERT
  tranche)`, `ControlFile(9)`, `ReplicationSlotControl(37)`,
  `WaitLSN(54)`, `LogicalDecodingControl(55)`,
  `DataChecksumsWorker(56)`, `AioWorkerControl(57)` (PG18).
- **Tranches** (`PG_LWLOCKTRANCHE`): 43 entries. Buffer
  mapping, lock manager, predicate-lock manager, parallel
  hash-join, parallel btree scan, parallel append, AIO
  io_uring completion, PGSTATS DSA/hash/data, etc.

## The 3-edit rule for adding a new builtin LWLock

Per the comment at lines 22-31, adding a new built-in LWLock
requires **THREE coordinated edits**:

1. Append `PG_LWLOCK(N, FooName)` at the end of the single
   section (do NOT renumber existing IDs).
2. Update `WaitEventLWLock` section in
   `src/backend/utils/activity/wait_event_names.txt`.
3. Update `generate-lwlocknames.pl` driver expectation if
   names section format changes.

For tranches the same applies (lines 93-99).

## Invariants

- INV-1: gaps in the numbering are intentional and must be left
  alone — they correspond to removed locks but external DTrace
  scripts and version-independent debuggers still reference the
  IDs. [from-comment] lines 22-26.
- INV-2: names here do NOT include the `Lock` suffix; it's
  appended by the surrounding macro definitions. [from-comment]
  line 30.
- INV-3: WaitEvent reporting needs `wait_event_names.txt` to
  match; mismatch causes silent gaps in `pg_stat_activity`.
  [from-comment] line 27-28.

## Trust boundary (Phase D)

- LWLock IDs are internal; not user-visible. Wait-event NAMES
  are visible via `pg_stat_activity` — if a contrib adds a
  tranche with a sensitive name, that name leaks to any
  unprivileged role with view access. Cluster: A11/A14
  monitoring oracle.

## Cross-refs

- `knowledge/files/src/include/storage/lwlock.h.md` (existing)
- `knowledge/files/src/backend/storage/lmgr/lwlock.c.md`
  (if exists)
- `knowledge/idioms/x-macro-include-trick.md` (if exists; if
  not, candidate for creation — this is the canonical example)

## Issues

- ISSUE-PROCESS: silent inconsistency between
  `lwlocklist.h` IDs and `wait_event_names.txt` causes
  reporting bugs without compile-time error. A unit test that
  cross-checks the two would catch. (Low.)
- ISSUE-DOC: the "three edits" requirement isn't surfaced
  anywhere outside this header's comment + the
  PG hackers wiki. A skill (`gucs-bgworker-parallel` already
  covers some of this) should include lwlocklist edit
  procedure. (Informational.)

## Appears in scenarios

<!-- scenarios:auto:begin -->

- [Scenario — Add a new LWLock tranche](../../../../scenarios/add-new-lwlock-tranche.md)

<!-- scenarios:auto:end -->
