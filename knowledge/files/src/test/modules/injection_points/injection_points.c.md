---
path: src/test/modules/injection_points/injection_points.c
anchor_sha: e18b0cb7344
loc: 565
depth: read
---

# src/test/modules/injection_points/injection_points.c

## Purpose

The reference implementation of the **injection-point** test
infrastructure introduced in PG 17. Provides SQL-callable functions to
attach, detach, load, run, list, and `wait` on named code-path
checkpoints registered throughout the backend via the `INJECTION_POINT(name, arg)`
macro family. Ships three built-in callback bodies (`error` / `notice`
/ `wait`) that exercise the most common test scenarios, plus a private
DSM-backed shared state holding up to 8 active wait counters with a
shared `ConditionVariable`. Most isolation, recovery, and concurrency
tests in the modern tree depend on this module being preloaded.
`[verified-by-code]` `injection_points.c:1-15,40-69`

## Public symbols

| Symbol | Site | Notes |
|---|---|---|
| `_PG_init` | `:559` | Registers the `ShmemCallbacks` block (preload-only) |
| `injection_points_attach(name, action)` | `:292` | Attach with one of `"error"` / `"notice"` / `"wait"`; honors `set_local` |
| `injection_points_attach_func(name, lib, fn, private bytea)` | `:336` | Attach a custom callback by `(library, function)` name |
| `injection_points_load(name)` | `:375` | Pre-load the .so resolution + cache (for use in critical sections) |
| `injection_points_run(name, arg)` | `:392` | Trigger an injection point synchronously via `INJECTION_POINT(name, arg)` |
| `injection_points_cached(name, arg)` | `:414` | Trigger via `INJECTION_POINT_CACHED(name, arg)` |
| `injection_points_wakeup(name)` | `:436` | Increment the matching wait counter and `ConditionVariableBroadcast` |
| `injection_points_set_local()` | `:476` | Enable per-PID conditioning + register exit cleanup |
| `injection_points_detach(name)` | `:498` | Detach point; removes from local-list if tracked |
| `injection_points_list() returns setof (name, library, function)` | `:523` | List all attached points via `InjectionPointList` |
| `injection_error` / `injection_notice` / `injection_wait` | `:194,210,227` | The three built-in callback bodies; `PGDLLEXPORT` so attach-by-name works |

## Internal landmarks

- `InjectionPointSharedState` (`:56-69`) — spinlock-protected; carries
  8 wait slots (`name[INJ_NAME_MAXLEN]` + `wait_counts`) and a single
  shared `ConditionVariable`.
- `injection_init_shmem` (`:132`) — lazy attaches the named DSM segment
  `"injection_points"`; `GetNamedDSMSegment` calls the init callback
  exactly once across the cluster.
- Condition encoding via `InjectionPointCondition`
  (`:18-31` in `injection_points.h`) — passed as `private_data` to the
  callback. `INJ_CONDITION_PID` lets a test attach a point that only
  fires in its own backend, used heavily for parallel-test safety
  `[from-comment]` `:469-475`.
- `injection_wait` (`:227`) — finds a free slot, records the point's
  name, then loops on `ConditionVariableSleep(wait_point,
  WaitEventInjectionPointNew(name))` until the corresponding
  `wait_counts[index]` is bumped by `injection_points_wakeup`. Custom
  wait event names are not released — acceptable for short-lived test
  runs (`[from-comment]` `:241-244`).
- `injection_points_set_local` (`:476`) — enables the
  `injection_point_local` flag, registers a `before_shmem_exit`
  callback (`injection_points_cleanup`, `:175`) that detaches every
  point in `inj_list_local` so the test-author doesn't leak global
  state when a connection exits.
- `_PG_init` (`:559`) — only registers shmem callbacks when in
  preload; this also ensures the named-DSM and its init callback are
  available when the first `injection_init_shmem` call runs.

## Invariants & gotchas

- TEST MODULE — must be loaded via `shared_preload_libraries` for the
  shmem callbacks to register `[verified-by-code]` `:561`. Other
  attempts no-op silently.
- `INJ_MAX_WAIT = 8` — only 8 concurrent `injection_wait` calls
  cluster-wide; `injection_wait` ERRORs out if all slots are taken
  (`:263-265`).
- `injection_points_load(name)` is mandatory before triggering a point
  inside a critical section (because dlopen + dynahash work isn't
  critical-section-safe). The `test_aio` module relies on this.
- `injection_points_set_local` makes the calling backend's points
  PID-scoped — they will not fire in other backends. Without `set_local`,
  every attached point is process-global and persists across
  connections until `detach`ed.
- The custom wait event names allocated via `WaitEventInjectionPointNew`
  accumulate without bound across reuse — acceptable for test runs but
  documented as an issue (`[from-comment]` `:241-244`).
- `INJECTION_POINT` macros expand to no-ops unless built with
  `USE_INJECTION_POINTS` (configured via `meson setup -Dinjection_points=true`).

## Cross-refs

- `knowledge/files/src/test/modules/injection_points/injection_points.h.md`
  — the local `InjectionPointCondition` struct definition.
- `knowledge/files/src/test/modules/injection_points/regress_injection.c.md`
  — supplementary regression helpers.
- `source/src/include/utils/injection_point.h` — generic
  `INJECTION_POINT(name, arg)`, `INJECTION_POINT_CACHED`,
  `InjectionPointAttach`, `InjectionPointDetach`, `InjectionPointLoad`,
  `InjectionPointList`.
- `source/src/backend/utils/misc/injection_point.c` — the core
  registry behind the macro.
- `knowledge/files/src/test/modules/test_aio/test_aio.c.md` — heaviest
  client of the API.
