# copyfuncs.c

- **Source:** `source/src/backend/nodes/copyfuncs.c` (213 lines hand-written + generated)
- **Last verified commit:** `ef6a95c7c64`
- **Depth:** skim

## Purpose

Implementation of `copyObject(p)` — deep copy of any node tree. Most
of the body is `#include "copyfuncs.funcs.c"` — that file is generated
by `gen_node_support.pl` from the canonical header list. The file
itself only contains:

1. The field-copy helper macros (`COPY_SCALAR_FIELD`,
   `COPY_NODE_FIELD`, `COPY_BITMAPSET_FIELD`, `COPY_STRING_FIELD`,
   `COPY_ARRAY_FIELD`, `COPY_POINTER_FIELD`, `COPY_LOCATION_FIELD`)
   that the generated code uses. `:29-62` `[verified-by-code]`
2. The `#include "copyfuncs.funcs.c"` insertion point. `:65`
3. Hand-written copy functions for nodes marked
   `pg_node_attr(custom_copy_equal)`: `_copyConst`, `_copyA_Const`,
   `_copyExtensibleNode`, `_copyBitmapset`. `:72-167`
4. `copyObjectImpl` — the public dispatcher; `#include "copyfuncs.switch.c"`
   provides the big switch over `T_*` tags. `:176-212` `[verified-by-code]`

## Special cases

- `_copyConst` handles by-value vs by-ref Datums (calls `datumCopy`
  for by-ref non-null values). `:72-105`
- `_copyA_Const` switches on the embedded value's tag
  (`T_Integer`/`T_Float`/`T_Boolean`/`T_String`/`T_BitString`) and
  copies the appropriate union member. `:107-144`
- `_copyExtensibleNode` looks up the extension-registered
  `nodeCopy` callback. `:146-161`
- `_copyBitmapset` defers to `bms_copy`. `:163-167`
- **List dispatch is hand-written in `copyObjectImpl`**: `T_List`
  goes through `list_copy_deep` (recursive node-copy); `T_IntList` /
  `T_OidList` / `T_XidList` use shallow `list_copy` since the cells
  hold raw integers, not pointers. `:191-203` `[verified-by-code]`

## Stack-overflow guard

`check_stack_depth()` is called at the top of `copyObjectImpl` to
prevent unbounded recursion on pathological trees. `:185`
`[verified-by-code]`

## `copyObject` macro magic (`nodes.h:228-233`)

With `HAVE_TYPEOF_UNQUAL`, the macro casts the result back to the
argument type via `typeof_unqual(*(obj)) *` so callers don't need
to write `(Foo *) copyObjectImpl(...)`.

## Cross-references

- Generator: `source/src/backend/nodes/gen_node_support.pl`
- Companion: `equalfuncs.c`, `outfuncs.c`, `readfuncs.c`,
  `queryjumblefuncs.c` — all follow the same hand-written-macros +
  generated-bodies + dispatcher pattern.

## Synthesized by
<!-- backlinks:auto -->
- [subsystems/optimizer.md](../../../../subsystems/optimizer.md)

## Appears in scenarios

<!-- scenarios:auto:begin -->

- [Scenario — Add a new Node type](../../../../scenarios/add-new-node-type.md)

<!-- scenarios:auto:end -->
