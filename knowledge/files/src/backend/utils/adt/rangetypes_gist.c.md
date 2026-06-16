# `src/backend/utils/adt/rangetypes_gist.c`

- **File:** `source/src/backend/utils/adt/rangetypes_gist.c` (1798 lines)
- **Last verified commit:** `4b0bf0788b066a4ca1d4f959566678e44ec93422` (2026-06-03)

## Purpose

The **GiST opclass** support functions for range types. Provides the
seven required GiST entry points: `consistent`, `union`, `compress`,
`decompress`, `penalty`, `picksplit`, `same`, plus `distance` for
KNN-GiST. Also serves multirange via shared logic where applicable.

Range values are stored verbatim in leaf entries; internal nodes hold
the **bounding range** of their subtree's entries. Empty ranges are
treated as a separate class to avoid skewing splits.

## Key concepts

- Range class taxonomy (`:26-38`): `CLS_NORMAL`, `CLS_LOWER_INF`,
  `CLS_UPPER_INF`, `CLS_CONTAIN_EMPTY`, `CLS_EMPTY` — 9 combinations
  total (`CLS_EMPTY` doesn't combine with anything else). Drives
  picksplit segregation. [verified-by-code]
- Penalty constants: `INFINITE_BOUND_PENALTY` = 2.0,
  `CONTAIN_EMPTY_PENALTY` = 1.0, `DEFAULT_SUBTYPE_DIFF_PENALTY` = 1.0
  (`:46-49`). [verified-by-code]
- `LIMIT_RATIO` = 0.3 — minimum acceptable split balance within a
  same-class bucket (`:42`). [verified-by-code]

## Key functions

- `range_gist_consistent(PG_FUNCTION_ARGS)` (`:190+`) — leaf and
  inner-node match. Dispatches by strategy number to the appropriate
  range operator (`@>`, `<@`, `&&`, `<<`, `>>`, `-|-`, etc.).
  [verified-by-code]
- `range_gist_union(PG_FUNCTION_ARGS)` (`:244+`) — returns the
  bounding range covering all input entries. [verified-by-code]
- `range_gist_compress`/`decompress` (`:269+`, `:323+`) —
  no-op-ish for ranges (no lossy compression). [verified-by-code]
- `range_gist_penalty(PG_FUNCTION_ARGS)` (`:362-617`) — the
  cost-of-adding heuristic. Computes how much the bounding range
  must grow to include the new entry, with class-transition
  surcharges (`CONTAIN_EMPTY_PENALTY` etc.). The
  `subtype_diff_finfo` (per-range-type "distance between two
  bounds" function) is consulted if defined. [verified-by-code]
- `range_gist_picksplit(PG_FUNCTION_ARGS)` (`:619-776`) — the
  bucketize-by-class then split-by-median algorithm. First segregates
  into the 9 classes, then within each class picks the median bound
  to split on. Fallback to round-robin if median doesn't give
  `LIMIT_RATIO` balance. [verified-by-code]
- `range_gist_same` (`:777+`) — equality of two bounding entries
  (used for invariant detection during inner-node updates).

## Phase D notes

- Indexes consume *already-canonical* `RangeType` Datums produced by
  `range_in`/`make_range`. Garbage stored values would mis-cluster
  but cannot corrupt heap. [inferred]
- `picksplit` runtime is O(N) per split with a few passes; large
  pages don't degrade unexpectedly. [from-comment]

## Potential issues

- [ISSUE-undocumented-invariant: `CLS_COUNT = 9` is a magic number
  spread across `:26-38` and used in picksplit array sizing; a
  future class addition requires synchronized edits (maybe)]
- [ISSUE-correctness: when `subtype_diff_finfo` is undefined, penalty
  falls back to `DEFAULT_SUBTYPE_DIFF_PENALTY`, which may produce
  poorly-balanced trees for user-defined range types — documented but
  worth surfacing (info)]

## Cross-references

- `source/src/include/access/gist.h` — `GISTENTRY`, `GIST_SPLITVEC`.
- `source/src/backend/access/gist/gistproc.c` — generic GiST proc
  shapes (some shared idioms).
- `source/src/backend/utils/adt/rangetypes.c` — provides
  `range_serialize`/`range_deserialize`, `range_cmp_bounds`.

<!-- issues:auto:begin -->
- [Issue register — `utils-adt`](../../../../../issues/utils-adt.md)
<!-- issues:auto:end -->

## Confidence tag tally
- `[verified-by-code]` × 7
- `[from-comment]` × 1
- `[inferred]` × 1
