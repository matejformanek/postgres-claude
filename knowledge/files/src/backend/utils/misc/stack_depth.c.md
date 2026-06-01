# `src/backend/utils/misc/stack_depth.c`

- **Last verified commit:** `ef6a95c7c64`
- **Lines:** ~200
- **Source:** `source/src/backend/utils/misc/stack_depth.c`

Cheap recursion guard used everywhere via `check_stack_depth()`. At
backend start, records `stack_base_ptr`; `check_stack_depth()` compares
the current frame's address against `stack_base_ptr ± max_stack_depth_bytes`
and `ereport(ERROR, "stack depth limit exceeded")` if exceeded — the
preferred way to bound recursive operators (planner expression walk,
JSON/XPath recursion, regex compilation, etc.) without infinite
recursion crashing the postmaster.

- `set_stack_base()` — called from `PostgresMain` after the new backend's
  stack frame is set up.
- `stack_is_too_deep()` — non-error variant returning bool, used by code
  paths that want to bail without ereport.
- GUC check/assign hooks for `max_stack_depth` clamp against
  `getrlimit(RLIMIT_STACK)` minus a safety margin so the SIGSEGV from a
  real stack overflow never beats `check_stack_depth`. [from-comment]
