# `src/backend/utils/adt/trigfuncs.c`

## Purpose

NOT trigonometric functions (those live in `float.c`). This file
holds **built-in trigger** support functions — currently just one:
`suppress_redundant_updates_trigger`, a generic BEFORE UPDATE row
trigger that returns NULL (suppresses the UPDATE) when the new tuple
payload is byte-identical to the old. 84 lines total.

## Key functions

- `suppress_redundant_updates_trigger` — `trigfuncs.c:28`. Validates
  trigger context (must be UPDATE / BEFORE / FOR EACH ROW), then
  compares `t_len`, `t_hoff`, `HeapTupleHeaderGetNatts`,
  `t_infomask & ~HEAP_XACT_MASK`, and finally `memcmp` of the tuple
  body. Returns `NULL` (suppress) on equality, otherwise returns the
  new tuple unchanged. `[verified-by-code]`

## Phase D notes

The `memcmp` (`:75-77`) compares raw on-disk tuple bytes. For
tuples containing TOASTed values, two semantically-equal rows can
have different on-disk representations (one inline, one out-of-line
TOAST pointer) — the trigger would treat them as different and
allow a redundant UPDATE through. This is acknowledged behavior
(the trigger is a performance optimisation, not a correctness
contract) but worth noting.

The `~HEAP_XACT_MASK` mask exclusion (`:73-74`) prevents transaction-
header differences (xmin/xmax/CID/CTID) from defeating the
comparison — important because OLD is the on-disk tuple and NEW is
under construction.

## Potential issues

- [ISSUE-correctness: TOAST representation differences cause
  semantically-equal tuples to be reported as differing — defeats
  the optimisation but does not cause data corruption. Documented
  behavior in user manual. (low)] — `trigfuncs.c:75-77`
- [ISSUE-undocumented-invariant: No handling for composite-type
  attribute changes that affect `t_hoff` (e.g. nulls bitmap added).
  These would also short-circuit the optimisation correctly via the
  `t_hoff` check at `:70`. Not a bug, just under-commented. (low)]

## Cross-references

<!-- issues:auto:begin -->
- [Issue register — `utils-adt`](../../../../../issues/utils-adt.md)
<!-- issues:auto:end -->
