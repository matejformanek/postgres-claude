---
scenario: add-new-shared-memory-region
when_to_use: New named shmem area sized at postmaster start — extension wants a persistent cross-backend struct or hash table.
companion_skills: ["memory-contexts"]
related_scenarios: ["add-new-lwlock-tranche","add-new-bgworker"]
canonical_commit: 283e823f9dc
last_verified_commit: e18b0cb7344
---

# Scenario — Add a new shared-memory region (extension or built-in subsystem)

## Scope — what's in / out

**In scope:**
- Adding a new named shmem area that lives for the lifetime of the
  postmaster: a `palloc`'d-into-shared-memory C struct or a fixed-size
  `HTAB` hash table, accessible from every backend, autovac worker, and
  bgworker.
- Both the **modern API** (`RegisterShmemCallbacks` + `ShmemRequestStruct`
  / `ShmemRequestHash` + per-stage `request_fn` / `init_fn` / `attach_fn`)
  added in `283e823f9dc` [verified-by-code](source/src/backend/storage/ipc/shmem.c:873), and the **legacy
  hook-pair API** (`shmem_request_hook` + `shmem_startup_hook` +
  `RequestAddinShmemSpace` + `ShmemInitStruct`) still supported for
  out-of-tree extensions [verified-by-code](source/src/backend/storage/ipc/shmem.c:105-119).
- Wiring the extension into `shared_preload_libraries` so the hooks fire
  in the postmaster, not later in a backend.
- Bundling the LWLocks that protect the new area — usually one tranche
  via `RequestNamedLWLockTranche()` (see `add-new-lwlock-tranche`).

**Out of scope:**
- **Dynamic** shared memory — `dsm.c` / `dsm_registry.c` and the
  `GetNamedDSMSegment()` API. That's for areas allocated after
  postmaster startup, sized at runtime. Use it when your size depends
  on a GUC the user can SIGHUP-reload, or when you don't want to be in
  `shared_preload_libraries`. See `knowledge/subsystems/storage-ipc.md`
  and `knowledge/files/src/backend/storage/ipc/dsm_registry.c.md`.
- **Per-parallel-query DSM** — `ParallelContext` / `shm_toc`; that's the
  parallel-worker scenario, not this one.
- The LWLock-tranche-only case (no shmem area of your own) — that's
  covered by `add-new-lwlock-tranche`.
- Adding shmem to a **built-in subsystem** following the new
  `subsystemlist.h` registry — same shape as the extension path, but
  with the additional step of editing `src/include/storage/subsystemlist.h`
  to register the `PG_SHMEM_SUBSYSTEM(...)` entry. Noted in the
  checklist below; full builtin-subsystem-conversion guidance is out of
  scope.

## Pre-flight

- **Companion skills:** load `memory-contexts`. Shared memory is *not*
  a memory context — `ShmemInitStruct` / `ShmemAlloc` allocations live
  in the postmaster shmem segment, NOT a `MemoryContext`, and must
  never be `pfree`'d. Mixing the two (e.g. storing a `palloc`'d pointer
  inside a shmem struct, or treating a shmem pointer as freeable) is
  the textbook bug in this change-class [from-comment](source/src/backend/storage/ipc/shmem.c:80-95).
- **Canonical commit:** `283e823f9dc` — *Introduce a new mechanism for
  registering shared memory areas*. Read it before starting; it
  establishes the `ShmemCallbacks` struct and the request / init /
  attach state machine that all new code should use. Companion commits
  worth reading: `1fc2e9fbc0a` (built-in subsystem registry via
  `subsystemlist.h`), `9b5acad3f40` (bulk conversion of in-tree
  subsystems — exemplifies the migration pattern), and
  `contrib/pg_stat_statements/pg_stat_statements.c` (the canonical
  extension example using the new API) [verified-by-code](source/contrib/pg_stat_statements/pg_stat_statements.c:267-475).
- **Common pitfalls (one-line each):**
  - Forgot to add the library to `shared_preload_libraries` — hooks
    never fire, `RequestAddinShmemSpace` from `_PG_init` of a
    LOAD-on-demand library hits `elog(FATAL,
    "cannot request additional shared memory outside shmem_request_hook")`
    [verified-by-code](source/src/backend/storage/ipc/ipci.c:47-48).
  - `init_fn` not idempotent — under EXEC_BACKEND, every backend
    re-enters the attach path; under crash-and-restart of a single
    backend, the postmaster keeps the segment but children re-init via
    the request callback. If you write "if first time, set value = 0",
    do not also assert "value == 0" on subsequent enters.
  - Pointer not stored before init — `*options->ptr` is set BEFORE the
    `init_fn` runs, so `init_fn` can dereference it; but only if you
    passed the `.ptr` option. If you forgot, the global pointer stays
    NULL and `init_fn` segfaults.
  - Mixed legacy/modern — calling `ShmemInitStruct` from inside a
    `RegisterShmemCallbacks` `init_fn` works (since SRS_INITIALIZING
    is in the allowed-states assert at `shmem.c:1020-1022`
    [verified-by-code](source/src/backend/storage/ipc/shmem.c:1020-1022)) but defeats the point. Pick one
    style per area.
  - Tranche allocated without `RequestNamedLWLockTranche` — see
    `add-new-lwlock-tranche.md` pitfalls. Bare `LWLockNewTrancheId()` in
    `init_fn` works, but the tranche name then has to be re-registered
    in every backend via `LWLockRegisterTranche` for `wait_event` /
    `pg_stat_activity` to show the name.

## File checklist (the FULL sweep)

This scenario assumes a contrib- or test-modules-style extension. For
adding shmem to a built-in subsystem, swap the "extension entry point"
rows for an edit to `src/include/storage/subsystemlist.h` plus a new
`ShmemCallbacks` definition in your subsystem's `.c` file.

| # | File | Why | Per-file doc | Companion skill |
|---|---|---|---|---|
| 1 | `contrib/<name>/<name>.c` or `src/test/modules/<name>/<name>.c` (extension `.c`) | (NEW) Defines the shmem struct/HTAB, the `ShmemCallbacks` table with `request_fn` / `init_fn` / `attach_fn`, and calls `RegisterShmemCallbacks(&MyCallbacks)` from `_PG_init`. Canonical example: `src/test/modules/test_shmem/test_shmem.c:42-90` [verified-by-code](source/src/test/modules/test_shmem/test_shmem.c:42-90). | — | bgworker-and-extensions |
| 2 | `contrib/<name>/<name>.h` (optional) | (NEW) Public typedef for the shmem struct, if other extensions or the SQL-callable interface need to see it. | — | — |
| 3 | `contrib/<name>/<name>.control` or `src/test/modules/<name>/<name>.control` | (NEW) `comment`, `default_version`, **`shared_preload_libraries = '<name>'`** is set in the *postgresql.conf* of the user; the `.control` file itself does not declare this — but document the requirement in the comment. | — | extension-development |
| 4 | `contrib/<name>/<name>--1.0.sql` | (NEW) SQL-callable wrappers that read/write the shmem area; the extension is otherwise opaque to SQL. | — | extension-development |
| 5 | `contrib/<name>/Makefile` + `meson.build` | (NEW) Standard contrib / test-modules boilerplate; nothing shmem-specific. | — | build-and-run |
| 6 | `src/include/storage/shmem.h` (read-only reference) | NO EDIT. Source of truth for `ShmemCallbacks`, `ShmemStructOpts`, `ShmemHashOpts`, `SHMEM_CALLBACKS_ALLOW_AFTER_STARTUP`, `RequestAddinShmemSpace` [verified-by-code](source/src/include/storage/shmem.h:41-197). Read it before designing your callback table. | [shmem.h.md](../files/src/include/storage/shmem.h.md) | memory-contexts |
| 7 | `src/include/storage/ipc.h` (read-only reference) | NO EDIT. Declares the legacy `shmem_startup_hook` [verified-by-code](source/src/include/storage/ipc.h:22,78). Touch only if migrating an existing hook-based extension. | [ipc.h.md](../files/src/include/storage/ipc.h.md) | — |
| 8 | `src/include/miscadmin.h` (read-only reference) | NO EDIT. Declares the legacy `shmem_request_hook` and the `process_shmem_requests_in_progress` guard [verified-by-code](source/src/include/miscadmin.h:525,543-544). | [miscadmin.h.md](../files/src/include/miscadmin.h.md) | — |
| 9 | `src/backend/storage/ipc/shmem.c` (read-only reference) | NO EDIT. Lifecycle state machine `SRS_INITIAL → SRS_REQUESTING → SRS_INITIALIZING → SRS_ATTACHING → SRS_DONE` lives here (lines 175-214) [verified-by-code](source/src/backend/storage/ipc/shmem.c:175-214). Read the header comment at lines 50-127 — it's the design doc [from-comment](source/src/backend/storage/ipc/shmem.c:50-127). | [shmem.c.md](../files/src/backend/storage/ipc/shmem.c.md) | memory-contexts |
| 10 | `src/backend/storage/ipc/ipci.c` (read-only reference) | NO EDIT for extensions. `RequestAddinShmemSpace` is at line 45; `shmem_startup_hook` fires from `CreateSharedMemoryAndSemaphores` at line 158-159 and `AttachSharedMemoryStructs` (EXEC_BACKEND) at line 110-111 [verified-by-code](source/src/backend/storage/ipc/ipci.c:45-159). | [ipci.c.md](../files/src/backend/storage/ipc/ipci.c.md) | — |
| 11 | `src/backend/utils/init/miscinit.c` (read-only reference) | NO EDIT. `process_shmem_requests()` at lines 1880-1887 sets `process_shmem_requests_in_progress = true` and fires `shmem_request_hook` — this is the window during which `RequestAddinShmemSpace` and `RequestNamedLWLockTranche` are legal [verified-by-code](source/src/backend/utils/init/miscinit.c:1880-1887). | [miscinit.c.md](../files/src/backend/utils/init/miscinit.c.md) | — |
| 12 | `src/include/storage/subsystemlist.h` (built-in subsystems only) | If you are converting a built-in subsystem (NOT an extension), add `PG_SHMEM_SUBSYSTEM(<name>_shmem_callbacks)` here. `RegisterBuiltinShmemCallbacks()` in `ipci.c:168-180` iterates this list [verified-by-code](source/src/backend/storage/ipc/ipci.c:168-180). Extensions skip this row. | — | — |
| 13 | `contrib/<name>/<name>.conf` or postgresql.conf snippet in tests | The user MUST set `shared_preload_libraries = '<name>'`. For TAP tests, this lives in the `Cluster->append_conf('postgresql.conf', ...)` block. Pattern: `src/test/modules/test_shmem/t/001_late_shmem_alloc.pl` [verified-by-code](source/src/test/modules/test_shmem/t/001_late_shmem_alloc.pl). | — | testing |
| 14 | `contrib/<name>/sql/<name>.sql` + `contrib/<name>/expected/<name>.out` (SQL regress) | Standard contrib regression test for the SQL-callable surface. The shmem behavior usually needs TAP coverage (next row) because a fresh cluster + preload-libraries is required to exercise the request/init path. | — | testing |
| 15 | `contrib/<name>/t/001_<name>.pl` (TAP) | Required for any non-trivial shmem area: spins a cluster with the library preloaded, exercises the SQL surface, optionally tests restart-persistence (i.e. that the area survives a backend crash but not a postmaster restart). | — | testing |
| 16 | `doc/src/sgml/<name>.sgml` (contrib only) | Standard contrib doc page. **Must** state: "Add this library to `shared_preload_libraries` before use." Forgetting this is the #1 user-facing support ticket. | — | — |
| 17 | `doc/src/sgml/filelist.sgml` (contrib only) | Add `&<name>;` entity reference if you added a new sgml file in row 16. | — | — |

(Rows 6-11 are reference-only; they DO NOT change in this scenario.
They are in the checklist so the planner knows to point at them when
designing the callback table. Per-file docs already exist for each.)

## Phases — suggested split for `pg-feature-plan`

1. **Phase 1 — Skeleton + struct definition.** Files: [1, 2, 3, 5].
   Define the shmem C struct, the `ShmemCallbacks` table, stub
   `request_fn` / `init_fn` / `attach_fn`, register from `_PG_init`.
   No SQL surface yet. Phase-end check: `meson compile -C
   dev/build-debug` builds, `dev/install-debug/bin/postgres
   -D dev/data-debug` starts with the library preloaded and logs the
   request + init messages.
2. **Phase 2 — LWLock tranche + initialization logic.** Files: [1].
   In `request_fn`, call `ShmemRequestStruct` (or `ShmemRequestHash`)
   and `RequestNamedLWLockTranche` for any locks the area needs. In
   `init_fn`, call `LWLockInitialize` on each lock slot and set the
   initial struct values. Phase-end check: `SELECT * FROM
   pg_shmem_allocations WHERE name LIKE '<name>%'` shows the new area
   with the requested size [verified-by-code](source/src/backend/storage/ipc/shmem.c:1044-1080).
3. **Phase 3 — SQL surface + tests.** Files: [4, 14, 15]. Expose
   read/write SQL functions, write regress + TAP. The TAP test is
   load-bearing: it's the only way to confirm the shared-preload path
   actually fires (regular regression runs against an already-started
   cluster). Phase-end check: `meson test -C dev/build-debug --suite
   <name>` is green; TAP shows postmaster log lines for request +
   init.
4. **Phase 4 — Docs + control.** Files: [3, 16, 17]. Write the SGML
   page, ensure the `shared_preload_libraries` requirement is
   prominent. Phase-end check: `meson compile -C dev/build-debug
   docs` clean.

## Pitfalls

- **Not in `shared_preload_libraries`.** The `_PG_init` of a
  LOAD-on-demand library runs in a backend, not the postmaster, after
  the `SRS_DONE` phase. `RegisterShmemCallbacks` without
  `SHMEM_CALLBACKS_ALLOW_AFTER_STARTUP` will `elog(ERROR)` — and
  even with that flag set, the area is only visible to *this one
  backend*, not the whole cluster [verified-by-code](source/src/include/storage/shmem.h:159-167). The TAP test is
  the only reliable way to catch this; document the requirement
  loudly in `<name>.sgml`.

- **Forgot to initialize the LWLock.** `LWLockInitialize(&area->lock,
  tranche_id)` MUST be called from `init_fn` (or `shmem_startup_hook`
  for legacy). Forgetting it leaves the lock in an invalid state and
  the first `LWLockAcquire` deadlocks or asserts. Pattern: see
  `contrib/pg_stat_statements/pg_stat_statements.c:550-552`
  [verified-by-code](source/contrib/pg_stat_statements/pg_stat_statements.c:550-552).

- **Idempotency / EXEC_BACKEND.** On Windows (no fork) every backend
  re-runs the request phase and the attach phase. The `init_fn` runs
  ONCE in the postmaster; the `attach_fn` runs once per backend. If
  you stuffed initialization into `attach_fn` it will run N times. If
  you wrote state in `init_fn` that `attach_fn` expects, it works on
  Linux (fork inherits memory) but breaks on Windows. The
  `test_shmem` module's assertion `if (attached_or_initialized)
  elog(ERROR, ...)` at lines 67-69, 80-82 is the discipline check
  [verified-by-code](source/src/test/modules/test_shmem/test_shmem.c:67-82).

- **Legacy `ShmemInitStruct` foundPtr check.** With the legacy API,
  `ShmemInitStruct` returns `foundPtr=false` only on the very first
  call. EXEC_BACKEND second-pass calls return `foundPtr=true` with the
  existing pointer. If your `shmem_startup_hook` always re-initializes
  fields regardless of `foundPtr`, you clobber the postmaster's state
  on each EXEC_BACKEND backend start [verified-by-code](source/src/backend/storage/ipc/shmem.c:1010-1041).

- **Sized at postmaster start.** The area is **fixed-size** for the
  lifetime of the cluster. Resizing requires a restart. If your size
  depends on a SIGHUP-reloadable GUC, you have two choices: (a)
  document that the GUC is PGC_POSTMASTER (cluster restart to take
  effect), or (b) use `dsm_registry` instead — that's the
  "out-of-scope" path mentioned above.

- **Race during request phase.** `RequestAddinShmemSpace` and
  `ShmemRequestStruct` are NOT thread-safe and assume single-threaded
  postmaster startup. The `process_shmem_requests_in_progress` guard
  enforces this — calling outside the request window hits
  `elog(FATAL)` at `ipci.c:48` [verified-by-code](source/src/backend/storage/ipc/ipci.c:47-48) and
  `lwlock.c:626` [verified-by-code](source/src/backend/storage/lmgr/lwlock.c:625-626).

- **Synchronization traps** (sibling files that must change together):
  - `request_fn` ↔ `init_fn` ↔ `attach_fn` (in the same C file): the
    sizes / hash-table parameters declared in `request_fn` must match
    what `init_fn` / `attach_fn` assume. The `ShmemRequestStruct`
    `size` cross-check at attach time will `elog(ERROR)` on mismatch
    unless you pass `SHMEM_ATTACH_UNKNOWN_SIZE` [verified-by-code](source/src/include/storage/shmem.h:48-51,69).
  - LWLock tranche request (Phase 2) ↔ `wait_event_names.txt` — only
    if you opted for a built-in tranche; for `RequestNamedLWLockTranche`
    the name appears in `pg_stat_activity.wait_event` automatically.
    See `add-new-lwlock-tranche.md` for the full discipline.
  - `<name>.control` ↔ user-facing `shared_preload_libraries`: the
    extension can't enforce this; only docs and TAP can.

## Verification (exact test invocations)

```bash
# Build (catches typos in the ShmemCallbacks struct initializer; -Wmissing-field-initializers
# warns when you forget request_fn / init_fn / attach_fn).
meson compile -C dev/build-debug

# Reinit cluster with the library preloaded (no catalog change, but the
# library must be in shared_preload_libraries from the start).
rm -rf dev/data-debug && dev/install-debug/bin/initdb -D dev/data-debug
echo "shared_preload_libraries = '<name>'" >> dev/data-debug/postgresql.conf
dev/install-debug/bin/pg_ctl -D dev/data-debug -l logfile start

# Smoke-test the area appears in the system view (the canonical
# "did my shmem actually allocate" check):
dev/install-debug/bin/psql -c "SELECT name, size, allocated_size FROM pg_shmem_allocations WHERE name LIKE '<name>%';"

# Extension regression
meson test -C dev/build-debug --suite <name>

# TAP — the load-bearing test for shared_preload_libraries behavior
meson test -C dev/build-debug --suite <name> --test 001_<name>

# Reference TAP for the new-API shape: late allocation after startup
meson test -C dev/build-debug --suite test_shmem --test 001_late_shmem_alloc

# Reference TAP for the canonical legacy + tranche shape
meson test -C dev/build-debug --suite test_lwlock_tranches

# Full check-world to make sure you didn't break anybody else's
# request/init ordering (you shouldn't have, but the SRS_* state
# machine is paranoid and asserts are dense).
meson test -C dev/build-debug
```

For a brand-new extension, model the TAP file on
`src/test/modules/test_shmem/t/001_late_shmem_alloc.pl` (modern API)
or `contrib/pg_stat_statements/` (modern API in a real contrib).

## Cross-refs

- Companion skills:
  - `.claude/skills/memory-contexts/SKILL.md` — discipline for *not*
    confusing shmem with palloc'd memory; shmem allocations never
    `pfree`.
  - `.claude/skills/bgworker-and-extensions/SKILL.md` — `_PG_init`
    lifecycle, `shared_preload_libraries` discipline, the
    library-load entry point that wires the callbacks.
  - `.claude/skills/extension-development/SKILL.md` — `.control` and
    `--1.0.sql` boilerplate.
- Related scenarios:
  - `scenarios/add-new-lwlock-tranche.md` — almost every new shmem
    area needs at least one tranche; the two scenarios are usually
    unioned.
  - `scenarios/add-new-bgworker.md` — a bgworker that owns or
    initializes a shmem area; same `_PG_init` + preload discipline.
  - `scenarios/add-new-extension.md` (contrib-style) and
    `scenarios/add-new-test-module.md` (test-modules-style) for the
    packaging boilerplate that wraps this change.
  - `scenarios/add-new-guc.md` — if the shmem area's size is
    user-tunable, the GUC must be `PGC_POSTMASTER` (read at
    postmaster start, before the shmem request phase).
- Idioms:
  - `knowledge/idioms/memory-contexts.md` — shmem vs palloc contract.
  - `knowledge/idioms/locking.md` (or `lwlock-rank-discipline.md`) —
    LWLock acquisition order across multiple shmem areas; deadlock
    avoidance.
- Subsystems:
  - `knowledge/subsystems/storage-ipc.md` — full architecture of the
    shmem subsystem and the lifecycle state machine.
  - `knowledge/files/src/backend/storage/ipc/shmem.c.md` — the
    allocator and the index.
  - `knowledge/files/src/backend/storage/ipc/ipci.c.md` — the
    postmaster-startup orchestration.
  - `knowledge/files/src/backend/storage/ipc/dsm_registry.c.md` — the
    "I want shmem but NOT at postmaster start" alternative.
- Issues: `knowledge/issues/storage-ipc.md` — prior traps with
  startup ordering, EXEC_BACKEND attach paths, and shmem-size
  miscalculations.
- Reference patch (canonical_commit): `git -C source show 283e823f9dc`
  for the new-API introduction. Also useful: `git -C source show
  1fc2e9fbc0a` (built-in subsystem registry), `git -C source show
  9b5acad3f40` (bulk migration of in-tree subsystems — the textbook
  before/after for the modern pattern), and
  `contrib/pg_stat_statements/pg_stat_statements.c` (live extension
  example).
