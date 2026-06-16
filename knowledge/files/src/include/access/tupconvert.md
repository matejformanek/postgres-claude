# `access/tupconvert.h` — tuple conversion across TupleDesc

**Verified against source pin `4b0bf0788b0`** (path: `source/src/include/access/tupconvert.h`)

## Role
Convert a tuple from one TupleDesc to another. Used for: partitioned-table
row routing (parent → child or child → parent), composite-type rewrites,
and BEFORE-trigger result reshaping. Builds an attribute map once, applies
it to many tuples.

## Public API
- `TupleConversionMap` struct (`tupconvert.h:24`): `indesc` (source
  TupleDesc), `outdesc` (target TupleDesc), `attrMap` (AttrMap with 0
  meaning null), scratch arrays `invalues/inisnull/outvalues/outisnull`.
- `convert_tuples_by_position(indesc, outdesc, msg)` (`tupconvert.h:36`) —
  position-based mapping; `msg` used as ereport message prefix on mismatch.
- `convert_tuples_by_name(indesc, outdesc)` (`tupconvert.h:40`).
- `convert_tuples_by_name_attrmap(indesc, outdesc, attrMap)`
  (`tupconvert.h:42`) — caller-supplied map.
- `execute_attr_map_tuple(tuple, map)` (`tupconvert.h:46`).
- `execute_attr_map_slot(attrMap, in_slot, out_slot)` (`tupconvert.h:47`).
- `execute_attr_map_cols(attrMap, in_cols)` (`tupconvert.h:50`) — translate
  a Bitmapset of attnums.
- `free_conversion_map(map)` (`tupconvert.h:52`).

## Invariants
- `attrMap->attnums[i]` of 0 ⇒ produce NULL in output attr i. `[from-comment]`
  (`tupconvert.h:28`).
- `convert_tuples_by_position` returns NULL if no conversion is needed
  (e.g., identical descs). `[from-comment]` (verified in
  `src/backend/access/common/tupconvert.c`).
- `execute_attr_map_tuple` requires the map's scratch arrays be properly
  allocated — `convert_tuples_by_*` does this. `[from-comment]`.
- Caller must `free_conversion_map` (which `pfree`s scratch arrays and the
  AttrMap) to avoid leaks. `[inferred]`.

## Notable internals
- AttrMap stores `attnums` as a flat `AttrNumber *` array (see `attmap.h`,
  not in this slice).
- Conversion is per-position (`by_position`) or per-name (`by_name`).
  Position-based is faster but only safe across "shape-compatible" descs;
  name-based handles reordering.
- BEFORE-trigger usage: a trigger function may return a tuple in the
  natural rowtype; conversion ensures the executor sees the table's
  rowtype.

## Trust-boundary / Phase D surface

**[ISSUE-correctness: attrMap with attnum > indesc->natts is silent OOB read
(low)]** — `execute_attr_map_tuple` indexes `invalues[attnums[i] - 1]`. If
the AttrMap was built against a different `indesc` than the one passed at
execution time, this reads past the array. `convert_tuples_by_name_attrmap`
takes both `indesc` and `attrMap` from the caller (`tupconvert.h:42`); no
runtime cross-check that they're consistent. `[inferred]`.

**[ISSUE-api-shape: by_position vs by_name choice is the caller's
responsibility (informational)]** — Picking position when names disagree
silently misroutes columns. Documentation, not enforcement.
`tupconvert.h:36`-`44`.

**[ISSUE-memory: scratch arrays inside TupleConversionMap (low)]** — Live
in CurrentMemoryContext at construction; if the map outlives that context,
later use is use-after-free. `tupconvert.h:29`-`32`.

## Cross-refs
- `access/attmap.h` (not in this slice) — `AttrMap` definition.
- `knowledge/files/src/include/access/tupmacs.h` — fetchatt used in the
  conversion loop.
- `knowledge/files/src/include/access/htup.h` (not in this slice) —
  HeapTuple flavor.

<!-- issues:auto:begin -->
- [Issue register — `include-access`](../../../../issues/include-access.md)
<!-- issues:auto:end -->

## Issues
1. **[ISSUE-correctness: attrMap/indesc mismatch is silent OOB read (low)]**
   — `tupconvert.h:42`.
2. **[ISSUE-api-shape: by_position can silently misroute columns (informational)]**
   — `tupconvert.h:36`-`44`.
3. **[ISSUE-memory: scratch arrays tied to construction-time context (low)]**
   — `tupconvert.h:29`-`32`.
