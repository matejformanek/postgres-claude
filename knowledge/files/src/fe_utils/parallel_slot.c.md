# `src/fe_utils/parallel_slot.c`

- **File:** `source/src/fe_utils/parallel_slot.c` (562 lines)
- **Last verified commit:** `4b0bf0788b066a4ca1d4f959566678e44ec93422` (2026-06-04)

## Purpose

A small connection-pool abstraction for frontend tools that fan a workload of
independent commands out over N database connections using libpq's async API
(`PQsendQuery` issued by callers, results drained here via `PQgetResult`).
Used by `reindexdb` and `vacuumdb` (`--jobs`) to run maintenance commands in
parallel. The core data type is `ParallelSlotArray` (a flexible-array struct
of `ParallelSlot`); the dispatcher hands out an idle slot to a caller, who
fires an async query on it, and the array blocks on `select()` when all slots
are busy. `:1-13`, `:30-32` `[verified-by-code]` `[from-comment]`

## Public symbols

| Symbol | Line | Role |
|---|---|---|
| `ParallelSlotsGetIdle` | :369 | Return a ready slot for the given dbname; blocks on `select()` until one frees if all busy. Returns NULL on error/cancel. |
| `ParallelSlotsSetup` | :426 | Allocate + init an array of `numslots` slots; stores cparams/progname/echo/initcmd. No connections opened yet. |
| `ParallelSlotsAdoptConn` | :458 | Hand an already-open `PGconn` to the array for reuse, filling the first unconnected slot. |
| `ParallelSlotsTerminate` | :477 | Disconnect every connected slot. |
| `ParallelSlotsWaitCompletion` | :499 | Drain all in-flight results synchronously; return false if any error. |
| `TableCommandResultHandler` | :537 | Stock `ParallelSlotResultHandler`: OK for `PGRES_COMMAND_OK`, tolerates "undefined table" (42P01), fatal on anything else. |

`ParallelSlotSetIdle` and `ParallelSlotSetHandler` are inline helpers declared
in `fe_utils/parallel_slot.h` (used at `:272`, `:511`). `[inferred]`

## Internal landmarks

### Slot-selection ladder (`ParallelSlotsGetIdle`, `:369`)

Four tiers, tried in order each loop iteration:

1. `find_matching_idle_slot` `:134` — idle slot already connected to `dbname`
   (or any db if `dbname == NULL`); reused as-is. `:380`
2. `find_unconnected_slot` `:158` — idle slot with no connection; opened via
   `connect_slot`. `:388`
3. `find_any_idle_slot` `:178` — idle slot on the *wrong* db; disconnected and
   reconnected. `:397-404`
4. Otherwise all slots are busy → `wait_on_slots` `:195` blocks until one
   frees, then loop. `:412-413` `[verified-by-code]`

### Async result machine

- **`wait_on_slots`** `:195` — rebuilds an `fd_set` from each slot's
  `PQsocket` every call (`:203-229`), picks the first valid conn as the
  cancel target, runs `select_loop`, then for each readable socket calls
  `PQconsumeInput` and drains with the `!PQisBusy` / `PQgetResult` loop. A
  NULL result marks the slot idle via `ParallelSlotSetIdle`. `:246-276`
  `[verified-by-code]`
- **`select_loop`** `:79` — the `select(2)` wrapper. Retries on `EINTR`,
  returns -1 on real error or `CancelRequested`. On Windows it uses a 1s
  timeout to poll for cancels (no signal-driven interruption). `:88-126`
  `[verified-by-code]` `[from-comment]`
- **`processQueryResult`** `:38` / **`consumeQueryResult`** `:57` — invoke the
  slot's handler; handler returning false means "problem". On success the
  *caller here* owns and `PQclear`s the result (`:48`); on failure the handler
  is contracted to have freed it already (`:43`). `[from-comment]`
- **`connect_slot`** `:285` — opens via `connectDatabase`, temporarily
  overriding `cparams->override_dbname`, runs `initcmd` if set, and enforces
  the `FD_SETSIZE` ceiling. `[verified-by-code]`

## Invariants & gotchas

- **`select()`-based, so FD_SETSIZE is a hard limit.** `connect_slot` calls
  `exit(1)` if a new socket fd is `>= FD_SETSIZE` (POSIX) or if `slotno >=
  FD_SETSIZE` (Windows, where FD_SETSIZE counts members not fd values). The
  long comment at `:297-312` explains the Windows fd-numbering hazard; the
  hint is "Try fewer jobs." `:313-331` `[verified-by-code]` `[from-comment]`
- **Result ownership is split by handler return value.** Success path frees in
  `processQueryResult`; failure path requires the handler to have freed. A
  handler that returns false *without* freeing leaks the `PGresult`. `:43-49`
  `[from-comment]`
- **Cancel target is transient.** `SetCancelConn`/`ResetCancelConn` bracket
  each blocking section (`:63-69`, `:238-240`); the cancel conn is whichever
  slot was scanned first that iteration, not a fixed one. `[verified-by-code]`
- **Setup uses `palloc0`, not bare malloc.** The array is zeroed, so all slots
  start `inUse=false`, `connection=NULL`. cparams/progname/initcmd are stored
  by pointer and must outlive the array. `:436-443` `[from-comment]`
- **`TableCommandResultHandler` deliberately swallows 42P01.** Tables can
  vanish between list-build and command time; a missing-table error is logged
  but processing continues. Any other error logs and returns false (fatal to
  the run). `:518-535`, `:547-559` `[from-comment]` `[verified-by-code]`

## Cross-references

- `source/src/bin/scripts/reindexdb.c`, `vacuumdb.c` — primary callers of the
  `ParallelSlots*` API. `[inferred]`
- `source/src/fe_utils/connect_utils.c` — `connectDatabase`,
  `disconnectDatabase`, `executeCommand` (used at `:294`, `:335`, `:400`).
- `source/src/fe_utils/cancel.c` — `SetCancelConn`, `ResetCancelConn`,
  `CancelRequested` (`fe_utils/cancel.h` at `:24`).
- `knowledge/files/src/fe_utils/connect_utils.c.md`

## Potential issues

- **[ISSUE-leak: connection on a failed `initcmd` / mid-setup error]**
  `parallel_slot.c:333-335` — `connect_slot` stores the new connection in the
  slot before `executeCommand` runs the `initcmd`. `executeCommand` itself
  exits on failure, so no live leak in the current call graph, but if a future
  error path between `connectDatabase` and slot bookkeeping returned instead
  of exiting, the just-opened conn would be orphaned. Defensive note only.
  (maybe)
- **[ISSUE-undocumented-invariant: handler must free on failure]**
  `parallel_slot.c:43` — the "free the result yourself on NULL/false return"
  contract lives only in a comment; a non-conforming `ParallelSlotResultHandler`
  leaks every failed `PGresult`. The in-tree `TableCommandResultHandler` does
  `PQclear` before its false return at `:556`, satisfying it. (nit)

## Confidence tag tally

- `[verified-by-code]` × 8
- `[from-comment]` × 7
- `[inferred]` × 2
