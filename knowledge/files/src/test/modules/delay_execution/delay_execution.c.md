# src/test/modules/delay_execution/delay_execution.c

**Pin:** `b78cd2bda5b1a306e2877059011933de1d0fb735`
**LOC:** 96
**Verification depth:** full read

## Role

A small test module that inserts a controllable delay between the parsing/planning and the execution of a query, so isolation tests can reliably interleave another backend's action at that exact point. The delay is implemented not via an injection point but by taking and immediately releasing an advisory lock identified by a GUC: if another backend already holds that advisory lock, this backend blocks at plan-time until it's released. It works by chaining onto `planner_hook`. [verified-by-code] `source/src/test/modules/delay_execution/delay_execution.c:3` (header comment), `:56` (lock take/release). Declares `PG_MODULE_MAGIC`. [verified-by-code] `source/src/test/modules/delay_execution/delay_execution.c:31`

## Public API

- `_PG_init` — defines the GUC `delay_execution.post_planning_lock_id`, reserves the `delay_execution` prefix, and installs `delay_execution_planner` onto `planner_hook` (saving the previous hook). [verified-by-code] `source/src/test/modules/delay_execution/delay_execution.c:75`
- `delay_execution.post_planning_lock_id` — GUC (`PGC_USERSET`, int, range `0..INT_MAX`, default 0). The advisory lock ID to lock/unlock after planning; `0` disables the delay. [verified-by-code] `source/src/test/modules/delay_execution/delay_execution.c:79`

## Invariants

- INV-1: The planner hook must invoke the previous hook user if present, else `standard_planner` — the standard chained-hook idiom. Breaking this drops other modules' planner hooks. [verified-by-code] `source/src/test/modules/delay_execution/delay_execution.c:48`
- INV-2: The delay only fires when `post_planning_lock_id != 0`; the advisory lock is taken and released in immediate succession (the block, if any, happens during the take). [verified-by-code] `source/src/test/modules/delay_execution/delay_execution.c:57`
- INV-3: After the lock dance, `AcceptInvalidationMessages()` must be called explicitly because the advisory-lock functions don't process pending invalidations — without it, the delayed backend could miss catalog invalidations that arrived during the wait. [verified-by-code] `source/src/test/modules/delay_execution/delay_execution.c:64`
- INV-4: `prev_planner_hook` is captured at load time in `_PG_init` and restored implicitly by always calling through it; the module never unsets `planner_hook` (no `_PG_fini`). [verified-by-code] `source/src/test/modules/delay_execution/delay_execution.c:94`

## Notable internals

- The advisory lock is taken/released via `DirectFunctionCall1(pg_advisory_lock_int8 / pg_advisory_unlock_int8, ...)`, casting the int GUC to `int64`. [verified-by-code] `source/src/test/modules/delay_execution/delay_execution.c:59`
- `MarkGUCPrefixReserved("delay_execution")` guards against typo'd GUC names under the module's prefix. [verified-by-code] `source/src/test/modules/delay_execution/delay_execution.c:91`
- The planner hook signature here includes `ExplainState *es` — the modern (post-EXPLAIN-into-planner) `planner_hook_type`. [verified-by-code] `source/src/test/modules/delay_execution/delay_execution.c:42`

## Cross-refs

- `source/src/backend/optimizer/plan/planner.c` — `planner_hook`, `standard_planner`, `planner_hook_type`.
- `source/src/backend/utils/adt/lockfuncs.c` — `pg_advisory_lock_int8` / `pg_advisory_unlock_int8`.
- `source/src/backend/utils/cache/inval.c` — `AcceptInvalidationMessages`.
- `source/src/backend/utils/misc/guc.c` — `DefineCustomIntVariable`, `MarkGUCPrefixReserved`.

## Potential issues

None.
