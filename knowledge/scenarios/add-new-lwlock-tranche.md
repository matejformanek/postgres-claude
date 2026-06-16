---
scenario: add-new-lwlock-tranche
when_to_use: I want to add a new LWLock tranche — either a built-in entry in `src/include/storage/lwlocklist.h` (predefined `PG_LWLOCK` slot or `PG_LWLOCKTRANCHE` group) or an extension tranche via `RequestNamedLWLockTranche` (shmem-preloaded fixed pool) or `LWLockNewTrancheId` (dynamic, name-with-id).
companion_skills: ["locking"]
related_scenarios: ["add-new-shared-memory-region","add-new-index-am"]
canonical_commit: da952b415f4
last_verified_commit: e18b0cb7344
---

# Scenario — Add a new LWLock tranche

## Scope — what's in / out

**In scope:**
- A **built-in predefined LWLock** living in `MainLWLockArray`: one
  `PG_LWLOCK(<id>, <Name>)` line appended to `lwlocklist.h`, the matching
  doc entry in `wait_event_names.txt`, and the use-site code that calls
  `LWLockAcquire(&MainLWLockArray[<Name>Lock].lock, …)` (or via the
  generated `<Name>Lock` macro). `[verified-by-code]`
  (`src/include/storage/lwlocklist.h:34-91`,
  `src/backend/utils/activity/wait_event_names.txt:312-385`).
- A **built-in LWLock tranche** (group of LWLocks sharing a single
  tranche ID, e.g. buffer mapping partitions): one
  `PG_LWLOCKTRANCHE(<ID>, <Name>)` line appended to `lwlocklist.h`,
  matching `wait_event_names.txt` entry under the post-"END OF
  PREDEFINED LWLOCKS" block, plus the shmem-alloc + `LWLockInitialize`
  loop at the use site. `[verified-by-code]`
  (`src/include/storage/lwlocklist.h:93-142`,
  `src/include/storage/lwlock.h:158-173`).
- An **extension tranche** allocated at postmaster startup via
  `RequestNamedLWLockTranche(name, num)` from `shmem_request_hook`, then
  retrieved with `GetNamedLWLockTranche(name)` in every backend that
  uses it. `[verified-by-code]`
  (`src/backend/storage/lmgr/lwlock.c:608-664`,
  `src/test/modules/test_lwlock_tranches/test_lwlock_tranches.c:30-46`).
- A **dynamic extension tranche** allocated mid-flight via
  `LWLockNewTrancheId(name)` — modern API where the name is registered
  atomically with the ID (no separate `LWLockRegisterTranche` per
  backend; the tranche-name table lives in shmem so all backends see
  it). The caller then calls `LWLockInitialize(lock, tranche_id)` on
  each `LWLock` it owns. `[verified-by-code]`
  (`src/backend/storage/lmgr/lwlock.c:561-605`,
  `src/backend/storage/ipc/dsm_registry.c:319`,
  `src/backend/access/transam/slru.c:288-293`).

**Out of scope:**
- Carving a brand-new shmem region to hold the lock array — see
  `add-new-shared-memory-region.md`. The two scenarios union when an
  extension needs both a new shmem chunk *and* a fresh tranche.
- Adding a new heavyweight (`lock.c`) lock method or `LOCKTAG` —
  different subsystem entirely; no scenario yet.
- A new wait-event class (e.g. a brand-new `WaitEventLWLock`
  sibling) — that's a `wait_event_names.txt` Section change, not a
  tranche change.
- Renaming or removing a built-in lock — leave a numbered gap (see the
  `/* 0 is available; was formerly BufFreelistLock */` comment in
  `lwlocklist.h:34`) for DTrace / external script stability.
  `[from-comment]` (`src/include/storage/lwlocklist.h:22-32`).

## Pre-flight

- **Companion skills:** load `locking` — covers the LWLock acquisition
  protocol, rank discipline (no out-of-order acquire across tranches
  without explicit justification), the predefined-vs-tranche
  distinction, and the `LWLockAcquire` / `LWLockRelease` /
  `LWLockHeldByMe` API. `[verified-by-code]`
  (`.claude/skills/locking/SKILL.md`).
- **Canonical commit:** `da952b415f4` — *"Rework lwlocknames.txt to
  become lwlocklist.h"* (Álvaro Herrera, 2024). The patch that folded
  the old `lwlocknames.txt` into the header-as-x-macro `lwlocklist.h`
  consumed by both `BuiltinTrancheIds` (via `PG_LWLOCKTRANCHE`) and
  `generate-lwlocknames.pl` (which still produces the `<Name>Lock`
  macros). It also wired the `wait_event_names.txt` cross-check that
  fails the build if the two lists drift. Read it before adding a
  predefined `PG_LWLOCK` or `PG_LWLOCKTRANCHE` entry. For the extension
  path, the older `c1772ad9225` *"Change the way that LWLocks for
  extensions are allocated"* is the reference. `[verified-by-code]`
  (`git -C source show da952b415f4`).
- **Common pitfalls (one-line each):**
  - Forgetting the `wait_event_names.txt` entry — `generate-lwlocknames.pl`
    cross-checks the two lists and the build dies with "predefined lwlocks
    do not match". `[verified-by-code]`
    (`src/backend/storage/lmgr/generate-lwlocknames.pl:28-32`,
    `src/backend/utils/activity/wait_event_names.txt:317-322`).
  - Putting the new `PG_LWLOCK` / `PG_LWLOCKTRANCHE` *not* at the end —
    breaks DTrace probes and external monitoring scripts that key off the
    numeric ID. `[from-comment]`
    (`src/include/storage/lwlocklist.h:22-28`).
  - Calling `RequestNamedLWLockTranche` outside `shmem_request_hook` —
    fatal `elog(FATAL, "cannot request additional LWLocks outside
    shmem_request_hook")`. `[verified-by-code]`
    (`src/backend/storage/lmgr/lwlock.c:625-626`).
  - Using `GetNamedLWLockTranche` for a tranche allocated with
    `LWLockNewTrancheId` — errors with "requested tranche was not
    registered with RequestNamedLWLockTranche()". The two APIs are
    deliberately separate. `[verified-by-code]`
    (`src/backend/storage/lmgr/lwlock.c:540-548`).
  - Calling `LWLockNewTrancheId` once per backend instead of once total
    — each call allocates a NEW id, so backends end up with different
    ids for the "same" tranche. Allocate once in the shmem-init path
    and stash the id where all backends can read it (typically in the
    shmem struct that holds the lock itself). `[verified-by-code]`
    (`src/backend/storage/ipc/dsm_registry.c:319`,
    `src/backend/access/transam/slru.c:288-293`).
  - Skipping `LWLockInitialize` for a non-`MainLWLockArray` lock —
    leaves `lock->tranche == 0` and any `LWLockAcquire` reports the
    wrong wait event. `[verified-by-code]`
    (`src/backend/storage/lmgr/lwlock.c:667-680`).

## File checklist (the FULL sweep)

The first table is the **built-in** path (predefined lock OR predefined
tranche). The second is the **extension** path (named-pool OR
dynamic). A real patch picks one path; composite work (e.g. new index
AM whose shmem hash uses its own tranche) unions both.

### Path A — built-in predefined LWLock or LWLock tranche

| # | File | Why | Per-file doc | Companion skill |
|---|---|---|---|---|
| 1 | `src/include/storage/lwlocklist.h` | Append a new line at the end of the right section: `PG_LWLOCK(<next_id>, <Name>)` for a single predefined slot inside `MainLWLockArray` (gets a generated `<Name>Lock` macro), OR `PG_LWLOCKTRANCHE(<ID_SUFFIX>, <CamelName>)` for a group tranche (becomes `LWTRANCHE_<ID_SUFFIX>` in `BuiltinTrancheIds`). Always append; leave gaps for removed locks; do not renumber. `[verified-by-code]` (`src/include/storage/lwlocklist.h:22-142`). | [lwlocklist.h.md](../files/src/include/storage/lwlocklist.h.md) | locking |
| 2 | `src/backend/utils/activity/wait_event_names.txt` | Append the matching documentation line in the `WaitEventLWLock` section — *before* the `END OF PREDEFINED LWLOCKS` marker for a `PG_LWLOCK`, *after* it for a `PG_LWLOCKTRANCHE`. Must be in the same order as `lwlocklist.h` or `generate-lwlocknames.pl` fails the build. The string is the user-visible `pg_stat_activity.wait_event` value plus a one-sentence SGML-friendly description. `[verified-by-code]` (`src/backend/utils/activity/wait_event_names.txt:312-385`, `src/backend/storage/lmgr/generate-lwlocknames.pl:28-110`). | — | locking |
| 3 | `src/include/storage/lwlock.h` *(read-only — verifies generated names)* | The `BuiltinTrancheIds` enum sources `LWTRANCHE_<ID>` entries from `lwlocklist.h` via the `PG_LWLOCKTRANCHE` x-macro at `:166-170`. After regen, the new `LWTRANCHE_<ID>` symbol must be reachable from the use site. Do not edit this file unless changing the enum scaffolding itself. `[verified-by-code]` (`src/include/storage/lwlock.h:158-173`). | [lwlock.h.md](../files/src/include/storage/lwlock.h.md) | locking |
| 4 | `src/backend/storage/lmgr/lwlock.c` *(read-only — verifies tranche-name table)* | `BuiltinTrancheNames[]` (generated portion sourced from `lwlocklist.h` via the same x-macro) provides the name string `GetLWLockIdentifier` returns for `pg_stat_activity.wait_event`. No edit needed unless adding a name with non-standard formatting. `[verified-by-code]` (`src/backend/storage/lmgr/lwlock.c` around `GetLWLockIdentifier`). | [lwlock.c.md](../files/src/backend/storage/lmgr/lwlock.c.md) | locking |
| 5 | `src/include/storage/lwlocknames.h` *(generated — DO NOT edit)* | Regenerated by `src/backend/storage/lmgr/generate-lwlocknames.pl` from rows 1 + 2 during build. Produces the `<Name>Lock` macros (= `&MainLWLockArray[N].lock`) used at call sites. Verify post-build that the new macro exists. `[verified-by-code]` (`src/include/storage/meson.build:3-18`, `src/backend/storage/lmgr/Makefile:32-33`). | — | locking |
| 6 | Use-site `.c` (subsystem owner) | Acquire / release the new lock. For a `PG_LWLOCK`: `LWLockAcquire(<Name>Lock, LW_EXCLUSIVE)`. For a `PG_LWLOCKTRANCHE` group: in shmem init, allocate the `LWLock` array, then `for (i ...) LWLockInitialize(&array[i], LWTRANCHE_<ID>);`. Pick the rank carefully — see the `lwlock-rank-discipline` idiom. `[verified-by-code]` (`src/backend/access/transam/slru.c:288-310` for the tranche-array idiom). | — | locking |
| 7 | `src/backend/storage/lmgr/README` *(only for a structurally-novel lock)* | If the new lock introduces a new ordering rule against existing locks (e.g. "must be held before ProcArrayLock"), document it here. Pure additions in an existing rank slot don't need a README change. `[verified-by-code]` (`src/backend/storage/lmgr/README` exists at 39 KB). | — | locking |
| 8 | `doc/src/sgml/monitoring.sgml` *(auto-generated from row 2)* | The wait-event tables in monitoring.sgml are built from `wait_event_names.txt`; row 2's text drops into the docs at next build. Verify by grepping the rendered `monitoring.html`. `[verified-by-code]` (`src/backend/utils/activity/wait_event_names.txt:1-30` for the autogen header). | — | locking |
| 9 | `src/test/regress/sql/<area>.sql` *(only if the lock has observable SQL-level behavior)* | A regression test for a fresh built-in lock is rare — usually the subsystem's existing tests already exercise the new lock by virtue of using the code path. Add only if you can write a deterministic visibility check (e.g. via `pg_stat_activity.wait_event`). `[inferred]` from existing scenario convention. | — | testing |

### Path B — extension tranche (`RequestNamedLWLockTranche` OR `LWLockNewTrancheId`)

| # | File | Why | Per-file doc | Companion skill |
|---|---|---|---|---|
| B1 | `<extension>/<extname>.c` — `_PG_init` + `shmem_request_hook` | If using `RequestNamedLWLockTranche`: install a `shmem_request_hook` from `_PG_init` that calls `RequestNamedLWLockTranche("<extname>_<purpose>", N)`. Calling it anywhere else (or from any later phase) hits the `process_shmem_requests_in_progress` guard and FATALs. `[verified-by-code]` (`src/backend/storage/lmgr/lwlock.c:625-626`, `src/test/modules/test_lwlock_tranches/test_lwlock_tranches.c:30-46`). | — | locking |
| B2 | `<extension>/<extname>.c` — shmem-startup or per-use site | If using `RequestNamedLWLockTranche`: every backend that touches the lock calls `GetNamedLWLockTranche("<extname>_<purpose>")` once (cache the `LWLockPadded *` in a process-local global to avoid the lookup per acquire). If using `LWLockNewTrancheId`: the `shmem_startup_hook` (or whatever bootstraps your shmem region under the `AddinShmemInitLock`) calls `LWLockNewTrancheId("<name>")` *exactly once*, stashes the returned `int` into the shared struct, and the per-backend init reads it from there. `[verified-by-code]` (`src/backend/storage/lmgr/lwlock.c:519-555` for `GetNamedLWLockTranche`, `:561-605` for `LWLockNewTrancheId`). | — | locking |
| B3 | `<extension>/<extname>.c` — `LWLockInitialize` per lock | For `LWLockNewTrancheId`: in the shmem-init code path that creates the actual `LWLock` storage, call `LWLockInitialize(&shmem->lock, shmem->tranche_id)` once per lock. The `RequestNamedLWLockTranche` path skips this — the postmaster does the init for you in the main array before any backend forks. `[verified-by-code]` (`src/backend/storage/lmgr/lwlock.c:667-680`, `src/backend/storage/ipc/dsm_registry.c:319` for the canonical "register-then-stash" idiom). | — | locking |
| B4 | The C struct living in shmem | Holds the `LWLock` (embed, do not pointer-indirect — `LWLOCK_PADDED_SIZE` alignment matters for cache-line behavior, see `src/include/storage/lwlock.h:52-72`) plus the `int tranche_id` if you used `LWLockNewTrancheId`. For `RequestNamedLWLockTranche`, the tranche lives in `MainLWLockArray` and your struct just remembers the `LWLockPadded *` base. `[verified-by-code]` (`src/include/storage/lwlock.h:41-72`). | — | locking |
| B5 | `<extension>/Makefile` or `<extension>/meson.build` | No tranche-specific build wiring beyond ordinary extension build — `RequestNamedLWLockTranche` works because the extension is `shared_preload_libraries`'d, which the test harness handles via `<extname>.conf` referenced in the `regress_args`. `[verified-by-code]` (`src/test/modules/test_lwlock_tranches/meson.build:23-32`, `:test_lwlock_tranches.conf`). | — | extension-development |
| B6 | `<extension>/<extname>.conf` *(test module only)* | If the extension MUST be in `shared_preload_libraries` to call `RequestNamedLWLockTranche` (it MUST), the test config has `shared_preload_libraries = '<extname>'` and the test's meson entry adds `--temp-config` pointing at it. `[verified-by-code]` (`src/test/modules/test_lwlock_tranches/test_lwlock_tranches.conf`, `:meson.build:32`). | — | extension-development |
| B7 | `<extension>/<extname>.control` + `--1.0.sql` | Ordinary extension manifest plus the SQL wrappers exposing the locks (or the operations that take them) to regression tests. `[verified-by-code]` (`src/test/modules/test_lwlock_tranches/test_lwlock_tranches.control`, `--1.0.sql`). | — | extension-development |
| B8 | `<extension>/sql/<test>.sql` + `expected/<test>.out` | Cover: (a) the tranche name surfaces in `pg_stat_activity.wait_event` (or via a SQL-callable `GetLWLockIdentifier` wrapper); (b) acquire/release round-trips don't deadlock; (c) negative paths — null name, name ≥ `NAMEDATALEN`, `GetNamedLWLockTranche("bogus")`, exhausting `MAX_USER_DEFINED_TRANCHES`. `[verified-by-code]` (`src/test/modules/test_lwlock_tranches/sql/test_lwlock_tranches.sql:1-60`). | — | testing |

## Phases — suggested split for `pg-feature-plan`

1. **Phase 1 — Pick path + plumbing.** Files: Path A [1, 2] or Path B
   [B1, B5, B6, B7]. Decide built-in vs extension, append to
   `lwlocklist.h` + `wait_event_names.txt` (built-in) or wire the
   `shmem_request_hook` + control file (extension). Phase-end check:
   `meson compile -C dev/build-debug` succeeds — for the built-in path
   this proves `generate-lwlocknames.pl` accepted the two lists and
   regenerated `lwlocknames.h`.
2. **Phase 2 — Wire the use site.** Files: Path A [6] or Path B [B2, B3,
   B4]. For built-in, call `LWLockAcquire(<Name>Lock, …)` at the
   actual decision site; for tranche groups, allocate the
   `LWLockPadded` array in shmem and `LWLockInitialize` each slot. For
   extension, populate the shmem struct in `shmem_startup_hook` and
   start using the locks. Phase-end check: smoke-run the subsystem
   path; `SELECT wait_event_type, wait_event FROM pg_stat_activity`
   under load shows the new identifier (or it stays NULL because no
   contention — both are correct).
3. **Phase 3 — Tests + docs.** Files: Path A [7, 9] or Path B [B8].
   Add the regression test that exercises the lock and asserts the
   wait-event name. Update README only if a new ordering rule was
   introduced. Phase-end check: `meson test -C dev/build-debug --suite
   regress` and (extension) `meson test … --suite <test-module-name>`
   pass.

## Pitfalls

- **List-order drift between `lwlocklist.h` and `wait_event_names.txt`**
  — `generate-lwlocknames.pl` walks both lists in parallel and bails
  if any entry mismatches; the resulting error is `predefined
  lwlocks do not match` from the generator, which surfaces as a build
  failure long before runtime. `[verified-by-code]`
  (`src/backend/storage/lmgr/generate-lwlocknames.pl:28-110`).
- **Renumbering a predefined `PG_LWLOCK`** — DTrace probes, external
  perf tools, and `pg_stat_activity` consumers all key off the numeric
  id; the file's own preamble explicitly forbids it. `[from-comment]`
  (`src/include/storage/lwlocklist.h:22-32`).
- **`RequestNamedLWLockTranche` outside `shmem_request_hook`** —
  hard FATAL via the `process_shmem_requests_in_progress` guard.
  `[verified-by-code]` (`src/backend/storage/lmgr/lwlock.c:625-626`).
- **`LWLockNewTrancheId` allocated per-backend** — each call burns
  one of the 256 `MAX_USER_DEFINED_TRANCHES` slots and returns a NEW
  id, so different backends get DIFFERENT ids for the "same" tranche.
  Allocate once during shmem init, persist the id in shmem, read it
  from every backend. `[verified-by-code]`
  (`src/backend/storage/lmgr/lwlock.c:581-588`,
  `src/backend/storage/ipc/dsm_registry.c:319`).
- **Forgetting `LWLockInitialize`** — `lock->tranche` stays zero and
  `pg_stat_activity.wait_event` shows the wrong name (or "???").
  `[verified-by-code]` (`src/backend/storage/lmgr/lwlock.c:667-680`).
- **Skipping `wait_event_names.txt`** — the lock works, but the wait
  event surfaces as `extension` (extension path) or the build dies
  (built-in path) because the cross-check noticed the gap.
  `[verified-by-code]` (`src/backend/utils/activity/wait_event_names.txt:317-322`).
- **Synchronization traps:** any change to
  `src/include/storage/lwlocklist.h` MUST be paired with a
  same-order change to
  `src/backend/utils/activity/wait_event_names.txt`. The two files
  ARE checked against each other at build time; there is no
  "compiles-but-misbehaves" failure mode for the order — only "won't
  compile". `[verified-by-code]`
  (`src/backend/storage/lmgr/generate-lwlocknames.pl:28-110`).

## Verification (exact test invocations)

```bash
# Built-in path: regression should still pass; if you added a SQL test, run it
meson test -C dev/build-debug --suite regress

# Extension path: the test_lwlock_tranches module is the worked example
meson test -C dev/build-debug --suite test_lwlock_tranches

# Quick smoke for either path — verify wait-event name surfaces
psql -c "SELECT name FROM pg_stat_activity WHERE wait_event_type = 'LWLock';"
# (run while the new code path is under load from a second session)

# Cross-check that the generator accepted the lists
ls dev/build-debug/src/include/storage/lwlocknames.h
grep '<NewName>Lock' dev/build-debug/src/include/storage/lwlocknames.h
```

If the change adds a new extension test module, name it explicitly
(e.g. `src/test/modules/<extname>/`) and wire it into `meson.build`
the same way `test_lwlock_tranches/meson.build:25-37` does.

## Cross-refs

- Companion skills: `.claude/skills/locking/SKILL.md`.
- Related scenarios: `scenarios/add-new-shared-memory-region.md`
  (union when the new tranche lives in a brand-new shmem region),
  `scenarios/add-new-index-am.md` (index AMs that need their own
  shmem hash table commonly want a private tranche).
- Idioms: `knowledge/idioms/lwlock-rank-discipline.md` (acquisition
  ordering rules across tranches), `knowledge/idioms/locking-overview.md`
  (the LWLock big picture).
- Subsystems: `knowledge/subsystems/storage-lmgr.md` (the lock-manager
  layer), `knowledge/subsystems/storage-ipc.md` (where extension
  shmem requests live).
- Issues: `knowledge/issues/storage-ipc.md` (extension shmem traps).
- Reference patch (canonical_commit): `git -C source show da952b415f4`
  (built-in lwlocklist.h rework); `git -C source show c1772ad9225` for
  the extension-tranche allocation reshape.
