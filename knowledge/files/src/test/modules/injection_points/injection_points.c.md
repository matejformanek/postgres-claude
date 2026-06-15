# src/test/modules/injection_points/injection_points.c

**Pin:** `b78cd2bda5b1a306e2877059011933de1d0fb735`
**LOC:** 565
**Verification depth:** full read

## Role

This is the test-extension harness for PostgreSQL's injection-point framework: it provides the SQL-callable surface (`injection_points_attach`, `_run`, `_wait`, `_wakeup`, etc.) and the concrete callback bodies (`injection_error`, `injection_notice`, `injection_wait`) that test suites attach to `INJECTION_POINT(...)` macro sites scattered across the backend. The framework core lives elsewhere (`utils/injection_point.c`); this module wires SQL to it, plus a small shared-memory area for the wait/wakeup synchronization used to test race conditions deterministically. [verified-by-code] `source/src/test/modules/injection_points/injection_points.c:1` (header comment), `source/src/test/modules/injection_points/injection_points.c:316` (`InjectionPointAttach`). The module declares `PG_MODULE_MAGIC`. [verified-by-code] `source/src/test/modules/injection_points/injection_points.c:38`

## Public API

SQL-callable functions (each `PG_FUNCTION_INFO_V1`):

- `injection_points_attach(name, action)` — attaches a point; maps action string `error`/`notice`/`wait` to a callback function name; if local mode is on, records a PID condition and tracks for cleanup. [verified-by-code] `source/src/test/modules/injection_points/injection_points.c:292`
- `injection_points_attach_func(name, lib, func, private_data)` — lower-level attach naming an arbitrary library/function plus optional `bytea` private data. [verified-by-code] `source/src/test/modules/injection_points/injection_points.c:336`
- `injection_points_load(name)` — pre-loads a point into the local cache via `INJECTION_POINT_LOAD`. [verified-by-code] `source/src/test/modules/injection_points/injection_points.c:375`
- `injection_points_run(name, arg)` — fires a point via `INJECTION_POINT(name, arg)`. [verified-by-code] `source/src/test/modules/injection_points/injection_points.c:392`
- `injection_points_cached(name, arg)` — fires a point from cache via `INJECTION_POINT_CACHED`. [verified-by-code] `source/src/test/modules/injection_points/injection_points.c:414`
- `injection_points_wakeup(name)` — bumps the wait counter for `name` and broadcasts the CV to release a waiter. [verified-by-code] `source/src/test/modules/injection_points/injection_points.c:436`
- `injection_points_set_local()` — switches this backend into "local" mode (PID-conditioned points, auto-detached at exit). [verified-by-code] `source/src/test/modules/injection_points/injection_points.c:476`
- `injection_points_detach(name)` — detaches a point and removes it from the local list. [verified-by-code] `source/src/test/modules/injection_points/injection_points.c:498`
- `injection_points_list()` — SRF returning `(name, library, function)` rows for all attached points. [verified-by-code] `source/src/test/modules/injection_points/injection_points.c:523`
- `injection_error` / `injection_notice` / `injection_wait` — exported (`PGDLLEXPORT`) callback bodies attachable to points. [verified-by-code] `source/src/test/modules/injection_points/injection_points.c:74`
- `_PG_init` — registers shmem callbacks; only acts when in `shared_preload_libraries`. [verified-by-code] `source/src/test/modules/injection_points/injection_points.c:558`

## Invariants

- INV-1: The wait/wakeup machinery supports at most `INJ_MAX_WAIT` (8) concurrent waiting points; injection-point names truncate to `INJ_NAME_MAXLEN` (64). Exceeding 8 simultaneous waiters errors with "could not find free slot". [verified-by-code] `source/src/test/modules/injection_points/injection_points.c:41`, `:263`
- INV-2: All reads/writes of `inj_state->wait_counts[]` and `inj_state->name[]` must hold `inj_state->lock` (the spinlock). The wait loop reads the counter under the lock, releases, then sleeps on the CV. [verified-by-code] `source/src/test/modules/injection_points/injection_points.c:250`, `:273`, `:447`
- INV-3: A free wait slot is identified by `name[i][0] == '\0'`; releasing a slot zeroes the first byte. Wakeup matches by full `strcmp`. [verified-by-code] `source/src/test/modules/injection_points/injection_points.c:253`, `:285`, `:450`
- INV-4: Local-mode injection points are tracked in `inj_list_local` allocated in `TopMemoryContext` (survives the SQL call's per-query context) and detached on `before_shmem_exit`. [verified-by-code] `source/src/test/modules/injection_points/injection_points.c:324`, `:490`
- INV-5: Shared state may be initialized two ways — module load (preload + `ShmemRequestStruct`) or dynamically via `GetNamedDSMSegment`; both funnel through `injection_point_init_state`. A function that may run without preload must call `injection_init_shmem()` first (guarded by `inj_state == NULL`). [verified-by-code] `source/src/test/modules/injection_points/injection_points.c:96`, `:132`, `:234`

## Notable internals

- `InjectionPointSharedState` — spinlock + `wait_counts[8]` + `name[8][64]` + a `ConditionVariable`. The condition-variable wait loop is the standard PG CV idiom: `ConditionVariablePrepareToSleep` / loop checking the predicate (counter changed) / `ConditionVariableSleep` / `ConditionVariableCancelSleep`. [verified-by-code] `source/src/test/modules/injection_points/injection_points.c:56`, `:268`
- `injection_point_allowed()` — runtime gating: `INJ_CONDITION_PID` compares `MyProcPid` against the stored pid; `INJ_CONDITION_ALWAYS` always passes. Each callback checks this first and silently returns if disallowed. [verified-by-code] `source/src/test/modules/injection_points/injection_points.c:152`, `:199`
- `injection_wait` allocates a custom wait event per name via `WaitEventInjectionPointNew(name)`; the comment notes these are intentionally never released (short-lived test usage). [verified-by-code] `source/src/test/modules/injection_points/injection_points.c:240`
- `_PG_init` registers `injection_shmem_callbacks` (request + init functions) via `RegisterShmemCallbacks`. [verified-by-code] `source/src/test/modules/injection_points/injection_points.c:90`, `:564`

## Cross-refs

- `source/src/backend/utils/misc/injection_point.c` — framework core: `InjectionPointAttach`, `InjectionPointDetach`, `InjectionPointList`, the `INJECTION_POINT*` macros.
- `source/src/include/utils/injection_point.h` — macro + API declarations.
- `injection_points.h` (same dir) — `InjectionPointCondition` / `InjectionPointConditionType`.
- `source/src/backend/storage/lmgr/condition_variable.c` — CV primitives used by the wait/wakeup loop.
- `source/src/backend/storage/ipc/dsm_registry.c` — `GetNamedDSMSegment` for dynamic shmem.

## Potential issues

- **[ISSUE-leak: detach-list pstrdup'd name not freed]** `injection_points.c:513` — `injection_points_detach` builds a throwaway `makeString(name)` in `TopMemoryContext` to drive `list_delete`; the matched list node (and its `pstrdup`'d string from attach at `:325`) is removed from the list but the deleted `String` node / its contents are not explicitly `pfree`'d, and the transient `makeString(name)` lives in `TopMemoryContext`. In a long-lived backend repeatedly attaching/detaching local points this is a slow leak. Severity: nit (test-only module, bounded by test duration).
- **[ISSUE-doc-drift: cleanup comment vs no list reset]** `injection_points.c:174` — `injection_points_cleanup` detaches every local point at `before_shmem_exit` but does not clear `inj_list_local` / `injection_point_local`; harmless at process exit but the "Detach all the local points" path leaves stale list state. Severity: nit (runs only at shmem exit).
