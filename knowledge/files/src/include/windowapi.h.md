# `src/include/windowapi.h`

- **Last verified commit:** `e18b0cb7344`
- **Lines:** ~70
- **Source:** `source/src/include/windowapi.h`

The API for **user-written window functions** (extensions defining
custom window aggregates / window functions in C). The standard
calling convention does NOT apply: a window function does not
receive its arguments as normal fmgr args — it receives a
`WindowObject` (via `fcinfo->context`) from which it must explicitly
fetch arg values at specific row positions in the frame/partition.
[from-comment]

Strictness is irrelevant because args are not passed
(`windowapi.h:6-8`). The V1 calling convention IS required.
`PG_NARGS()` works, and `get_fn_expr_argtype()` /
`get_fn_expr_arg_stable()` still apply.

## API / declarations

### Seek-type constants (`windowapi.h:34-36`)

For positioning row references:
- `WINDOW_SEEK_CURRENT 0` — relative to the current row.
- `WINDOW_SEEK_HEAD 1` — relative to the head of the partition.
- `WINDOW_SEEK_TAIL 2` — relative to the tail of the partition.

### Type

- `typedef struct WindowObjectData *WindowObject` (`windowapi.h:39`) —
  the actual struct is private to `nodeWindowAgg.c`.
- `PG_WINDOW_OBJECT()` = `((WindowObject) fcinfo->context)`
  (`windowapi.h:41`) — fetch the WindowObject from the call.
- `WindowObjectIsValid(winobj)` (`windowapi.h:43-44`) — both
  non-NULL AND `IsA(winobj, WindowObjectData)`.

### Functions (declarations only; bodies in `nodeWindowAgg.c`)

- `WinCheckAndInitializeNullTreatment(winobj, allowNullTreatment,
  fcinfo)` (`windowapi.h:46-48`) — validates and stashes the
  `IGNORE NULLS` / `RESPECT NULLS` flag for null-treatment-aware
  window functions (lead/lag/first_value/last_value/nth_value).
- `WinGetPartitionLocalMemory(winobj, sz)` (`windowapi.h:50`) —
  zeroed per-partition palloc; survives until the partition is
  done.
- `WinGetCurrentPosition(winobj)` (`windowapi.h:52`) — 0-based
  current row index within the partition.
- `WinGetPartitionRowCount(winobj)` (`windowapi.h:53`) — total rows
  in current partition; may not be known until partition end.
- `WinSetMarkPosition(winobj, markpos)` (`windowapi.h:55`) — tell
  the window machinery it's safe to discard rows before `markpos`
  (memory-management hint for tuplestore-backed frame).
- `WinRowsArePeers(winobj, pos1, pos2)` (`windowapi.h:57`) — are
  those two rows in the same peer group per ORDER BY.
- `WinGetFuncArgInPartition(winobj, argno, relpos, seektype,
  set_mark, &isnull, &isout)` (`windowapi.h:59-61`) — evaluate
  argument expression `argno` at a position relative to the
  partition.
- `WinGetFuncArgInFrame(winobj, argno, relpos, seektype, set_mark,
  &isnull, &isout)` (`windowapi.h:63-65`) — same but within the
  current frame.
- `WinGetFuncArgCurrent(winobj, argno, &isnull)` (`windowapi.h:67-68`)
  — fetch argument at the current row.

## Notable invariants / details

- V1 calling convention is required (`PG_FUNCTION_INFO_V1`); window
  function code MUST start by checking `WindowObjectIsValid(
  PG_WINDOW_OBJECT())` (`windowapi.h:8-14`). [from-comment]
- Header redirects detail-readers to `nodeWindowAgg.c` for full
  semantics of each Wxxx API ("See the header comments for each
  WindowObject API function in nodeWindowAgg.c for details",
  `windowapi.h:15-19`). [from-comment]
- The 0/1/2 seek-type constants are passed by value into
  `WinGetFuncArgInPartition` / `WinGetFuncArgInFrame`. Mistyping
  silently uses CURRENT.
- `WinGetPartitionLocalMemory` is the canonical place to store
  per-partition cached state — survives across calls to the SAME
  window function within one partition, freed at partition
  boundary. Note: NOT freed at SRF call-end since window functions
  do not return SET. [inferred]
- `WinSetMarkPosition` is the only way to enable memory reclamation
  for old rows in the tuplestore; window functions that don't
  call it silently force the entire partition to stay buffered.
  [from-comment]
- `WinRowsArePeers` requires the window has ORDER BY; without it,
  every row in the partition is a peer (the whole partition is one
  peer group).

## Potential issues

- `windowapi.h:46-48` — `WinCheckAndInitializeNullTreatment` is a
  recent addition for NULL TREATMENT support; older extension
  window functions never call it and silently misbehave on `IGNORE
  NULLS` syntax. [ISSUE-api-shape: NULL TREATMENT support requires
  explicit window-function opt-in (likely)]
- `windowapi.h:59-65` — both `WinGetFuncArgInPartition` and
  `WinGetFuncArgInFrame` use bare `int seektype`; the SEEK_* enum
  pattern would be safer. [ISSUE-style: window seek type is bare int
  not enum (nit)]
- `windowapi.h:55` — `WinSetMarkPosition` is a memory-management
  *hint*; failing to call it doesn't fail correctness but silently
  inflates memory. Extensions like lead/lag that always need a
  bounded window MUST call it. [ISSUE-undocumented-invariant:
  WinSetMarkPosition usage is performance-only, not correctness;
  hidden hazard (likely)]
- `windowapi.h:39` — `WindowObjectData` is opaque; extensions that
  want to introspect frame mode (RANGE/ROWS/GROUPS) have no
  header-level access. Must call `nodeWindowAgg.c` helpers.
  [ISSUE-api-shape: window-frame mode opaque to extensions (likely)]
- `windowapi.h:50` — `WinGetPartitionLocalMemory(winobj, sz)` returns
  zeroed memory, but the size is a contract between calls — the
  same `sz` must be passed on subsequent calls for the same purpose.
  No header-level enforcement. [ISSUE-api-shape: per-partition memory
  size contract (nit)]
- `windowapi.h:6-19` — overall the file delegates almost all
  documentation to `nodeWindowAgg.c`. Extension authors must read
  source. [ISSUE-documentation: windowapi.h delegates almost all
  semantic docs to .c file (nit)]

## Cross-references

<!-- issues:auto:begin -->
- [Issue register — `include-misc`](../../../issues/include-misc.md)
<!-- issues:auto:end -->
