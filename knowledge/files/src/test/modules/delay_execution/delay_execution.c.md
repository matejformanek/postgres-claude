---
path: src/test/modules/delay_execution/delay_execution.c
anchor_sha: e18b0cb7344
loc: 96
depth: read
---

# src/test/modules/delay_execution/delay_execution.c

## Purpose

Race-condition harness. Layers a `planner_hook` that, immediately after
planning a query, takes-then-releases a configured advisory lock. If another
session is already holding that lock, the planner pauses until the lock is
released; otherwise the call is a no-op. This lets `isolationtester` scripts
inject a precisely-timed pause between **parse-analysis and execution** of a
target query so race conditions involving plan invalidation or concurrent DDL
can be reproduced deterministically. `[verified-by-code]`

## Public symbols

| Symbol | Site | Notes |
|---|---|---|
| `_PG_init` | `delay_execution.c:75` | Defines `delay_execution.post_planning_lock_id` GUC and installs `planner_hook` |
| `delay_execution_planner` (static) | `:41` | The hook body — invokes prev hook (or `standard_planner`), then take/release advisory lock if `post_planning_lock_id != 0` |

## Internal landmarks

- `prev_planner_hook` chain preserved (`:37`, `:49-54`, `:94`).
- The advisory lock is taken and released back-to-back via
  `DirectFunctionCall1(pg_advisory_lock_int8, …)` —
  `DirectFunctionCall1(pg_advisory_unlock_int8, …)` (`:59-62`). If another
  backend holds the lock, the `_lock_` call blocks; otherwise it returns
  immediately.
- `AcceptInvalidationMessages()` (`:68`) is called explicitly after release
  because the advisory-lock functions don't process inval messages; without
  it the pause would be useless for tests that need plan/catalog
  invalidation to land between planning and execution.

## Invariants & gotchas

- **Test module — never load in production.** Loading this with any non-zero
  `post_planning_lock_id` makes every query take a session-level lock,
  serialising the whole instance.
- GUC scope is `PGC_USERSET` so a regression test can set it for one
  session only.
- The mechanism only delays between **planning and execution**. Other
  injection points (e.g. between parsing and planning) need a different
  hook.

## Cross-refs

- `source/src/backend/optimizer/plan/planner.c` — `planner_hook` declaration.
- `source/src/backend/utils/adt/lockfuncs.c` — `pg_advisory_lock_int8` etc.
- `source/src/include/utils/inval.h` — `AcceptInvalidationMessages`.
