---
scenario: add-startup-hook
when_to_use: Hook into the PostmasterMain / PostgresMain / InitPostgres lifecycle so an extension can run code at a specific startup phase (shmem sizing, pre-auth, post-auth, etc.).
companion_skills: ["bgworker-and-extensions"]
related_scenarios: ["add-new-bgworker","add-new-hook","add-new-shared-memory-region"]
canonical_commit: 4f2400cb3f1
last_verified_commit: e18b0cb7344
---

# Scenario — Add a startup-lifecycle hook

## Scope — what's in / out

**In scope:**
- Picking the correct slot in the postmaster / backend startup ring for the
  state your extension needs (no DB yet vs. shmem ready vs. user known).
- Adding a NEW lifecycle hook variable to core (typedef + global + call
  site + header export) when none of the existing slots fits.
- Installing into an EXISTING lifecycle hook (`shmem_request_hook`,
  `shmem_startup_hook`, `ClientAuthentication_hook`,
  `process_shared_preload_libraries_hook`) from an extension's
  `_PG_init`, with the standard prev-hook chaining idiom.
- The `process_shared_preload_libraries_in_progress` / `_done` guard
  pattern that gates "may only be called from a preloaded library."

**Out of scope:**
- Registering a background worker — that's its own ring slot
  (`RegisterBackgroundWorker` runs only in `process_shared_preload_libraries`).
  See `scenarios/add-new-bgworker.md`.
- Allocating a shared-memory region — that's the typical *user* of
  `shmem_request_hook` + `shmem_startup_hook`, with its own file
  checklist. See `scenarios/add-new-shared-memory-region.md`.
- Extension hooks fired *during query execution*
  (`planner_hook`, `ExecutorStart_hook`, `ProcessUtility_hook`, etc.).
  See `scenarios/add-new-hook.md`.
- Per-backend session lifecycle inside the executor (search-path,
  client-encoding) — not a hook surface, just `InitializeSession()`
  call order.

## Pre-flight

- **Companion skills:** load `bgworker-and-extensions` — covers
  `_PG_init`, `shared_preload_libraries`, and the prev-hook chaining
  idiom every preload extension uses.
- **Canonical commit:** `4f2400cb3f1` — *Add a new shmem_request_hook
  hook.* This is the textbook example of *adding* a new lifecycle hook:
  typedef in `miscadmin.h`, definition + `process_shmem_requests()`
  wrapper in `miscinit.c`, call site woven into `PostmasterMain` between
  `process_shared_preload_libraries` and `CreateSharedMemoryAndSemaphores`,
  plus the `process_shmem_requests_in_progress` invariant guard in
  `RequestAddinShmemSpace` [verified-by-code](source/src/backend/storage/ipc/ipci.c:40-50).
  Read it before designing a new slot.
- **Common pitfalls (one-line each):**
  - Picked the wrong ring slot — code runs but the state it needs
    (shmem, user identity, DB connection) isn't initialized yet. See
    "ring map" below.
  - Forgot the `prev_hook = hook; hook = my_hook;` chain — clobbers any
    other extension that installed before you, and tools like
    `pg_stat_statements` silently stop firing [verified-by-code](source/contrib/pg_stat_statements/pg_stat_statements.c:390).
  - Called `RequestAddinShmemSpace` / `RequestNamedLWLockTranche`
    outside `shmem_request_hook` — `FATAL`s with "cannot request
    additional shared memory outside shmem_request_hook"
    [verified-by-code](source/src/backend/storage/ipc/ipci.c:47-48).
  - New hook added but `_PG_init` example / docs missing — third-party
    extensions can't discover it. See `knowledge/issues/postmaster.md`.

### The startup ring — pick the right slot

The postmaster main process runs through `PostmasterMain` once; each
backend then runs `BackendStartup` → fork → child `BackendMain` →
`InitPostgres`. Three canonical lifecycle slots, each at a different
invariant:

| Slot | Where invoked | State available | Use when … |
|---|---|---|---|
| `process_shared_preload_libraries` | `PostmasterMain` [verified-by-code](source/src/backend/postmaster/postmaster.c:936). Body runs every preloaded `.so`'s `_PG_init` with `process_shared_preload_libraries_in_progress = true` [verified-by-code](source/src/backend/utils/init/miscinit.c:1853-1861). | Postmaster process, before fork. No shmem yet. GUCs parsed. | Register a bgworker; install other lifecycle hooks; set GUCs. |
| `shmem_request_hook` | `process_shmem_requests()` in `PostmasterMain`, between preload and `CreateSharedMemoryAndSemaphores` [verified-by-code](source/src/backend/postmaster/postmaster.c:970). | Still postmaster, still no shmem allocated. Loadable modules may sum shmem needs + request LWLock tranches. | Sizing: `RequestAddinShmemSpace`, `RequestNamedLWLockTranche`. |
| `shmem_startup_hook` | End of `CreateSharedMemoryAndSemaphores` [verified-by-code](source/src/backend/storage/ipc/ipci.c:155-159), also from `AttachSharedMemoryStructs` in EXEC_BACKEND child [verified-by-code](source/src/backend/storage/ipc/ipci.c:107-112). | Shared memory exists. No DB connection. | `ShmemInitStruct` / `ShmemInitHash`; one-time init of the area. |
| `ClientAuthentication_hook` | `ClientAuthentication()` after pg_hba match, before `STATUS_OK` is returned [verified-by-code](source/src/backend/libpq/auth.c:665-666). | Fork done, port + role string known, no DB session yet. | Auth-time policy / logging (the `auth_delay` pattern). |
| Tail of `InitPostgres` | Just before `EmitConnectionWarnings()` [verified-by-code](source/src/backend/utils/init/postinit.c:1262-1284). | DB selected, user known, GUCs from `pg_db_role_setting` applied, search-path / client-encoding initialized, `InitializeSession()` ran. | "Run something the first time a session is fully alive." There is no dedicated hook here; you currently bolt on via a session-level GUC assign hook, `local_preload_libraries`, or by registering a callback that fires in a transaction-start hook. Adding a true `backend_startup_hook` is a hackers-list discussion; cite this row when proposing one. |

If the answer to "what state do I need?" is "shmem" → request_hook for
sizing, startup_hook for init. If "the role name" → ClientAuthentication.
If "MyDatabaseId + GUC settings" → tail of InitPostgres. If "literally
just _PG_init in the postmaster" → no hook needed; preload already
runs your code.

## File checklist (the FULL sweep)

This sweep covers **adding a NEW lifecycle hook variable** to the core
tree (the canonical-commit shape). For installing into an existing hook
from an extension, only rows 8-9 apply.

| # | File | Why | Per-file doc | Companion skill |
|---|---|---|---|---|
| 1 | `src/include/<area>.h` — typically `miscadmin.h` or `storage/ipc.h` | Add `typedef void (*xxx_hook_type) (...);` + `extern PGDLLIMPORT xxx_hook_type xxx_hook;` declaration. `PGDLLIMPORT` is mandatory so extensions on Windows can link against it [verified-by-code](source/src/include/miscadmin.h:543-544). | [miscadmin.h.md](../files/src/include/miscadmin.h.md) / [ipc.h.md](../files/src/include/storage/ipc.h.md) | bgworker-and-extensions |
| 2 | `src/backend/<owning subsystem>/<file>.c` | Definition: `xxx_hook_type xxx_hook = NULL;` at file scope. Convention is to define it in the source file whose function will call it (e.g. `shmem_request_hook` lives in `miscinit.c` because `process_shmem_requests()` is there [verified-by-code](source/src/backend/utils/init/miscinit.c:1791); `shmem_startup_hook` lives in `ipci.c` because `CreateSharedMemoryAndSemaphores` is there [verified-by-code](source/src/backend/storage/ipc/ipci.c:31)). | — | bgworker-and-extensions |
| 3 | `src/backend/<owning subsystem>/<file>.c` (call site) | The line that actually invokes the hook. The standard pattern is `if (xxx_hook) xxx_hook(args);` placed at the *exact* lifecycle phase where the invariant holds. Examples: shmem_startup at [verified-by-code](source/src/backend/storage/ipc/ipci.c:158-159); shmem_request via wrapper at [verified-by-code](source/src/backend/utils/init/miscinit.c:1884-1885); ClientAuthentication at [verified-by-code](source/src/backend/libpq/auth.c:665-666). | — | bgworker-and-extensions |
| 4 | `src/backend/postmaster/postmaster.c` (or `tcop/postgres.c`, `utils/init/postinit.c`) | Weave the call site (or the wrapper-function call) into the right ring position. For shmem-class hooks, ordering relative to `process_shared_preload_libraries`, `RegisterBuiltinShmemCallbacks`, `ShmemCallRequestCallbacks`, and `CreateSharedMemoryAndSemaphores` is load-bearing [verified-by-code](source/src/backend/postmaster/postmaster.c:931-1018). Re-read the comments around the new hook's position; they explain the invariants. | [postmaster.c.md](../files/src/backend/postmaster/postmaster.c.md) | bgworker-and-extensions |
| 5 | `src/backend/utils/init/miscinit.c` (guard flag, OPTIONAL) | If the new hook *enforces* a "may only be called inside me" invariant (like shmem_request does), add a `bool xxx_in_progress = false;` and flip it around the call. Other API calls then `elog(FATAL, ...)` if invoked outside [verified-by-code](source/src/backend/utils/init/miscinit.c:1881-1887). Skip if the hook has no such invariant. | [miscinit.c.md](../files/src/backend/utils/init/miscinit.c.md) | bgworker-and-extensions |
| 6 | `doc/src/sgml/xfunc.sgml` (§"Shared Memory and LWLocks" or §"Writing C-Language Functions" subsections) | Document the new hook from the extension-author POV: what state is available, what to call, what NOT to call. The shmem_request_hook section at [verified-by-code](source/doc/src/sgml/xfunc.sgml:3786-3811) is the model. | — | extension-development |
| 7 | `src/test/modules/<name>/<name>.c` (NEW or extended) | Add or extend a test module that installs the hook to prove it fires. `test_lwlock_tranches` is the minimal example of the prev-hook chain + `shmem_request_hook` install [verified-by-code](source/src/test/modules/test_lwlock_tranches/test_lwlock_tranches.c:24-38). For ClientAuthentication-style hooks, `contrib/auth_delay` is the model. | — | testing |
| 8 | `<extension>/<name>.c` `_PG_init` (when *consuming* an existing hook) | Standard chain: `static xxx_hook_type prev_xxx_hook;` at file scope, then `prev_xxx_hook = xxx_hook; xxx_hook = my_xxx_hook;` in `_PG_init`. Inside `my_xxx_hook` always call `if (prev_xxx_hook) prev_xxx_hook(args);` first (or last — pick a convention and document it). Pattern in `pg_stat_statements` [verified-by-code](source/contrib/pg_stat_statements/pg_stat_statements.c:390). | — | bgworker-and-extensions |
| 9 | `<extension>/<name>.c` (gate on preload-progress) | If your `_PG_init` requires `shared_preload_libraries` (e.g. installs shmem-class hooks or registers bgworkers), guard with `if (!process_shared_preload_libraries_in_progress) return;` or `ereport(ERROR, ...)`. The flag is exported from `miscadmin.h` [verified-by-code](source/src/include/miscadmin.h:523-525). | — | bgworker-and-extensions |
| 10 | `src/test/modules/meson.build` (and `Makefile` if applicable) | Wire the new test module into the build. Required if row 7 is new. | — | testing |
| 11 | Reference companion — `process_shared_preload_libraries_in_progress` invariant | NOT a file edit; a discipline. If your hook adds a new `_in_progress` flag (row 5), update every public API that depends on "we're inside hook X" to check it. | — | — |

(`—` in the per-file doc column = genuinely-new file or no per-file doc
exists yet.)

## Phases — suggested split for `pg-feature-plan`

1. **Phase 1 — Declare + define the hook.** Files: [1, 2]. Add the
   typedef + extern in the header, define the global in the owning
   `.c`. Phase-end check: `meson compile -C dev/build-debug` succeeds
   (no callers yet — the symbol just exists).
2. **Phase 2 — Wire the call site + invariant guard.** Files: [3, 4, 5].
   Place the `if (hook) hook();` call at the exact lifecycle position;
   if relevant, flip the `_in_progress` flag and teach the gated API
   to FATAL outside the hook. Phase-end check: `initdb` + `pg_ctl
   start` still works (the hook is NULL by default; tree must behave
   identically when no extension installs it).
3. **Phase 3 — Test module that installs the hook.** Files: [7, 10].
   Build a minimal `test_<name>` that registers the hook in
   `_PG_init`, asserts it fires once, and exits. Add it as a TAP test.
   Phase-end check: `meson test -C dev/build-debug --suite setup
   --test test_<name>` is green.
4. **Phase 4 — Docs + invariants comment.** Files: [6]. Cross-reference
   the call-site comment from `xfunc.sgml`. Phase-end check: `meson
   compile -C dev/build-debug docs` is clean.

## Idioms invoked
<!-- idioms-invoked:auto -->

*Auto-derived from direct references + transitive file-overlap with idiom Call sites.*
*Refresh via `scripts/build-scenario-idiom-matrix.py`.*

| Idiom | Evidence |
|---|---|
| [`background-worker-startup`](../idioms/background-worker-startup.md) | direct reference |
| [`guc-variables`](../idioms/guc-variables.md) | direct reference |
| [`node-types-and-lists`](../idioms/node-types-and-lists.md) | shares files: `contrib/pg_stat_statements/pg_stat_statements.c` |
| [`parser-pipeline`](../idioms/parser-pipeline.md) | shares files: `contrib/pg_stat_statements/pg_stat_statements.c` |
| [`process-utility-hook-chain`](../idioms/process-utility-hook-chain.md) | direct reference |

<!-- /idioms-invoked:auto -->
## Pitfalls

- **Wrong ring slot = wrong invariants.** Calling `RequestAddinShmemSpace`
  from `shmem_startup_hook` is too late: shmem is already allocated.
  Calling it from `_PG_init` outside `process_shmem_requests` is too
  early in some builds (the postmaster issues FATAL via the
  `process_shmem_requests_in_progress` guard
  [verified-by-code](source/src/backend/storage/ipc/ipci.c:40-50)).
  The fix is to install `shmem_request_hook` in `_PG_init` and do the
  request inside the hook, not in `_PG_init` itself.
- **Forgot `PGDLLIMPORT`.** Hook variables MUST be marked
  `PGDLLIMPORT` in the header or Windows extensions fail to link
  [verified-by-code](source/src/include/miscadmin.h:544).
- **Forgot the prev-hook chain.** Two extensions installing into the
  same hook without chaining = whichever loaded last wins, silently.
  Every extension MUST stash the previous pointer and call it from
  within its own hook. The pattern is universal — see
  `contrib/pg_stat_statements` and `test_lwlock_tranches`.
- **Installing a postmaster-time hook from a non-preloaded extension.**
  If your extension is loaded via `LOAD` / `CREATE EXTENSION` inside a
  backend, `process_shared_preload_libraries_in_progress` is `false`
  and any attempt to install `shmem_request_hook` will be ineffective
  (postmaster has long passed `process_shmem_requests`). Guard with
  `if (!process_shared_preload_libraries_in_progress) ereport(ERROR,
  (errmsg("must be loaded via shared_preload_libraries")));`.
- **`InitPostgres` ordering trap.** The comment block at the top of
  `InitPostgres` explicitly warns "Be very careful with the order of
  calls" [from-comment](source/src/backend/utils/init/postinit.c:711-713).
  Any new code added inside `InitPostgres` (not a hook, just inline
  init) MUST be placed at a position where its required invariants
  already hold — e.g. `InitializeSession()` requires GUC settings, so
  it sits after `process_settings()` [verified-by-code](source/src/backend/utils/init/postinit.c:1245-1263).
- **EXEC_BACKEND path forgotten.** `shmem_startup_hook` fires twice in
  EXEC_BACKEND builds: once at postmaster startup, once per backend
  via `AttachSharedMemoryStructs` [verified-by-code](source/src/backend/storage/ipc/ipci.c:107-112).
  Idempotency on the second call is the extension's responsibility.
- **Synchronization traps** (sibling files that must change together):
  - Header `extern PGDLLIMPORT` declaration ↔ `.c` global definition
    (mismatched types cause a link error; missing `PGDLLIMPORT` fails
    on Windows only — CI catches it later than you want).
  - New `_in_progress` flag ↔ every public API that asserts the
    invariant (add the assertion in the same patch or extensions
    that misuse the API fail silently for a release).
  - Call-site comment ↔ `xfunc.sgml` — when a future patch moves the
    call site, both must move.

## Verification (exact test invocations)

```bash
# Build and confirm tree still works without any extension installed
meson compile -C dev/build-debug
rm -rf dev/data-debug && dev/install-debug/bin/initdb -D dev/data-debug
dev/install-debug/bin/pg_ctl -D dev/data-debug -l /tmp/pg.log start
dev/install-debug/bin/psql -c 'SELECT 1' && \
  dev/install-debug/bin/pg_ctl -D dev/data-debug stop

# Test module that installs the hook (existing pattern)
meson test -C dev/build-debug --suite setup --test test_lwlock_tranches

# Auth-time hook smoke (when adding/touching ClientAuthentication_hook)
meson test -C dev/build-debug --suite auth_delay

# Shmem-allocation extension smoke (when adding/touching shmem_*_hook)
meson test -C dev/build-debug --suite test_slru --test test_slru
meson test -C dev/build-debug --suite test_dsm_registry --test test_dsm_registry

# Full regression — confirms NULL-hook default path is unchanged
meson test -C dev/build-debug --suite regress

# Manual: confirm shared_preload_libraries gate fires
echo "shared_preload_libraries = 'my_ext'" >> dev/data-debug/postgresql.conf
dev/install-debug/bin/pg_ctl -D dev/data-debug restart
grep -i "my_ext" /tmp/pg.log     # extension's _PG_init log line should appear

# Negative path: load extension at session time and confirm it refuses
dev/install-debug/bin/psql -c "LOAD 'my_ext';"   # expect ERROR if it installs preload-only hooks
```

If the change adds a brand-new test module, register it in
`src/test/modules/meson.build` and add the suite name to the verification
list above.

## Cross-refs

- Companion skills: `.claude/skills/bgworker-and-extensions/SKILL.md`,
  `.claude/skills/extension-development/SKILL.md`,
  `.claude/skills/testing/SKILL.md`.
- Related scenarios:
  - `scenarios/add-new-bgworker.md` — registering a bgworker uses
    `process_shared_preload_libraries` as its ring slot; this scenario
    is the lifecycle-hook generalization.
  - `scenarios/add-new-shared-memory-region.md` — the typical *consumer*
    of `shmem_request_hook` + `shmem_startup_hook`; covers
    `RequestAddinShmemSpace` / `ShmemInitStruct` mechanics in detail.
  - `scenarios/add-new-hook.md` — extension hooks that fire during
    query execution (`planner_hook`, `ExecutorStart_hook`,
    `ProcessUtility_hook`), not at startup.
- Idioms: `knowledge/idioms/background-worker-startup.md`,
  `knowledge/idioms/process-utility-hook-chain.md` (the
  prev-hook-chaining idiom generalizes to startup hooks too),
  `knowledge/idioms/guc-variables.md` (GUCs read by `_PG_init` to
  parameterize the hook).
- Subsystems: `knowledge/subsystems/storage-ipc.md`,
  `knowledge/subsystems/main.md`, `knowledge/subsystems/libpq-backend.md`,
  `knowledge/subsystems/tcop.md`.
- Issues: `knowledge/issues/postmaster.md`,
  `knowledge/issues/storage-ipc.md`.
- Reference patch (canonical_commit): `git -C source show 4f2400cb3f1`.
