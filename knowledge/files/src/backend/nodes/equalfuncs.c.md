# equalfuncs.c

- **Source:** `source/src/backend/nodes/equalfuncs.c` (~265 lines + generated)
- **Last verified commit:** `ef6a95c7c64`
- **Depth:** skim

## Purpose

Implementation of `equal(a, b)` — deep structural comparison of node
trees. Same pattern as `copyfuncs.c`: hand-written macros + generated
body + dispatcher. `:1-25` `[from-comment]`

## Key invariant

**Parse-location fields are intentionally ignored.** `COMPARE_LOCATION_FIELD`
expands to `((void) 0)`. The rationale: a Var "x" at offset 5 should be
equal() to another Var "x" at offset 20 in the same query.
`:6-9`, `:79-81` `[verified-by-code]`

CoercionForm fields are also ignored (`COMPARE_COERCIONFORM_FIELD` =
no-op) — they're cosmetic display info, not semantically meaningful.
`:83-85` `[verified-by-code]`

## Macros (used by generated code)

- `COMPARE_SCALAR_FIELD(fldname)` — `if (a->f != b->f) return false;`
- `COMPARE_NODE_FIELD` — recurses via `equal()`
- `COMPARE_BITMAPSET_FIELD` — defers to `bms_equal`
- `COMPARE_STRING_FIELD` — null-safe `strcmp`
- `COMPARE_ARRAY_FIELD` — `memcmp` over inline array
- `COMPARE_POINTER_FIELD(f, sz)` — `memcmp` over palloc'd object
- `COMPARE_LOCATION_FIELD` / `COMPARE_COERCIONFORM_FIELD` — no-ops

`:26-86` `[verified-by-code]`

## Custom equal functions

- `_equalConst` (`:95-114`): compares scalar fields then uses
  `datumIsEqual` for the actual Datum; both NULL Consts of the same
  type are considered equal.
- `_equalExtensibleNode` (`:116-131`): looks up the registered
  `nodeEqual` callback.
- `_equalA_Const` (`:133-144`): in-line val field with special handling.
- `_equalBitmapset` (`:146-150`): defers to `bms_equal`.
- `_equalList` (`:155-215`): switches on list type, uses `forboth` over
  the two lists; rejects fast on differing length or tag.

## Dispatcher

`equal(const void *a, const void *b)` `:222-264`:
1. `a == b` → true (pointer identity).
2. Either NULL → false.
3. `nodeTag(a) != nodeTag(b)` → false.
4. `check_stack_depth()` guard.
5. Big switch over `nodeTag(a)`: `#include "equalfuncs.switch.c"`.
6. List family falls through to `_equalList`.

## Cross-references

- Generator: `source/src/backend/nodes/gen_node_support.pl`
- Companions: `copyfuncs.c`, `outfuncs.c`, `readfuncs.c`.

## Synthesized by
<!-- backlinks:auto -->
- [subsystems/optimizer.md](../../../../subsystems/optimizer.md)

## Appears in scenarios

<!-- scenarios:auto:begin -->

- [Scenario — Add a new Node type](../../../../scenarios/add-new-node-type.md)

<!-- scenarios:auto:end -->
