# `src/backend/utils/adt/tid.c`

- **File:** `source/src/backend/utils/adt/tid.c` (463 lines)
- **Last verified commit:** `4b0bf0788b066a4ca1d4f959566678e44ec93422` (2026-06-03)

## Purpose

The `tid` type — `ItemPointerData` (block number + offset number) that
identifies a physical tuple. Surface SQL representation is `(blk, off)`.
(`tid.c:1-16` [from-comment])

Also hosts the `currtid_byrelname` "latest version of this CTID"
helper, used historically by some replication tools.

## Type role

- **Input:** `tidin` (`:51`) — parses `(block, offset)`. Uses
  `strtoul` with explicit overflow guards (`:74-95`, `:97-104`).
- **Output:** `tidout` (`:118`) — `snprintf("(%u,%u)", blk, off)`.
- **Binary I/O:** `tidrecv` / `tidsend` — int32 + int16 raw.
- **Comparison:** all via `ItemPointerCompare`.
- **Hash:** `hashtid` / `hashtidextended` — uses
  `sizeof(BlockIdData) + sizeof(OffsetNumber)` explicitly to avoid
  struct padding contamination (`:259-267` [from-comment]).
- **Extractors:** `tid_block` (`:288`) returns int8 (BlockNumber is
  uint32, exceeds int4 range); `tid_offset` (`:303`) returns int4.

## Phase D notes — input parsing

- **Block-number parse: 64-bit `unsigned long` → uint32 truncation
  check.** On `SIZEOF_LONG > 4` (most 64-bit Unixes), `strtoul` on
  `"4294967296,0"` would not set ERANGE (it fits in unsigned long), but
  the explicit `cvt != (unsigned long) blockNumber &&
  cvt != (unsigned long) ((int32) blockNumber)` check at `:88-95`
  rejects it. The second branch (`int32` cast equality) is for
  backwards compat — `(-1,0)` is accepted and stored as
  `InvalidBlockNumber` (4294967295). [verified-by-code]
- **Offset parse:** `cvt > USHRT_MAX` explicit upper bound (`:99`).
  `errno` is checked but cleared only **once** at `:74` for both
  strtoul calls — second strtoul (`:97`) implicitly inherits any error
  from the first… actually no, errno is process-state but ERANGE from
  the first call would have already been caught at `:76`. [verified-by-code]
- **Allows `InvalidBlockNumber` and `InvalidOffsetNumber`** because of
  the int32-cast backwards-compat branch; `tid_block`/`tid_offset` use
  `NoCheck` accessors (`:292, :307`) to handle this. [from-comment]
- The parser walks until `)` or `,`, then strtoul; there's no
  whitespace tolerance inside the parens, but leading `(` is found by
  the loop at `:64-66`. Input `"(  1, 2  )"` has been historically
  accepted via strtoul's own whitespace handling on the leading-space
  side.
- **NTIDARGS = 2** (`:42`); the input loop bounded explicitly. No
  unbounded recursion or backtracking. No DoS surface.

## `currtid_internal` / `currtid_byrelname`

`currtid_byrelname` (`:446`) is a SQL-callable function that takes a
relname + tid, opens the relation, ACL-checks SELECT, opens a snapshot,
and asks the tableam (`table_tuple_get_latest_tid`) for the latest
version. Handles views via `currtid_for_view` (`:366`), which only
supports trivial single-SELECT views that project a CTID column.

- **ACL check on every call** (`:333-337` [verified-by-code]).
- **`AccessShareLock`** taken at `:455`; this is a SQL-callable function
  exposed to all users, so a malicious user could cycle through table
  names to probe what tables they have SELECT on. Standard catalog
  visibility surface.
- **Tableams that don't support `table_tuple_get_latest_tid`** would
  presumably elog; partition tables and toast tables would be filtered
  out by the `RELKIND_HAS_STORAGE` check at `:342`.

## Potential issues

- `[ISSUE-undocumented-invariant: tidin accepts InvalidBlockNumber via
  '(-1, 0)' through the int32-cast backwards-compat branch (:88-95);
  matters for callers that expect tidin output ranges to be valid
  positions (low).]`
- `[ISSUE-stale-todo: NOTES "input routine largely stolen from boxin()"
  (:14) — boxin() has since been refactored; this code is now its own
  thing. (info)]`
- `[ISSUE-stale-todo: comment "Perhaps someday we should output this as
  a record" (:128) — long-standing TODO (info).]`
- `[ISSUE-info-disclosure: currtid_byrelname leaks existence of
  relations the user lacks SELECT on (via ACL error message), but only
  one that's visible in their search_path. Standard PG behavior (info).]`

## Cross-references

- `source/src/include/storage/itemptr.h` — `ItemPointerData`,
  `ItemPointerCompare`, `*NoCheck` accessors.
- `source/src/backend/access/heap/heapam.c` — `table_tuple_get_latest_tid`
  implementation for heap.
- `source/src/backend/access/table/tableamapi.c` — tableam dispatch.

## Confidence tag tally

- `[verified-by-code]` × 4
- `[from-comment]` × 3
