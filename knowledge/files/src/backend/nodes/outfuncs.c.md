# outfuncs.c

- **Source:** `source/src/backend/nodes/outfuncs.c` (~700 lines hand-written + generated)
- **Last verified commit:** `ef6a95c7c64`
- **Depth:** skim

## Purpose

Serializes a node tree to a Lisp-ish text form (`nodeToString`). Used
to:

- Store parse trees in catalogs (e.g. `pg_rewrite.ev_action`,
  `pg_proc.proargdefaults`, `pg_index.indexprs`).
- Ship `PlannedStmt` to parallel workers via shared memory.
- Provide a `_OUT` form for `EXPLAIN (VERBOSE)` and debug printers
  (`pprint`, `elog_node_display` in `print.c`).

## Wire format

A node is written as `{NODELABEL :field1 value1 :field2 value2 ...}`.
Lists become `(item1 item2 ...)`. Strings are quoted with `"` and
backslash-escaped via `outToken`. Special tokens like `<>` for
empty/NULL.

## Hand-written infrastructure

- The field-write macros: `WRITE_NODE_TYPE`, `WRITE_INT_FIELD`,
  `WRITE_UINT_FIELD`, `WRITE_INT64_FIELD`, `WRITE_UINT64_FIELD`,
  `WRITE_OID_FIELD`, `WRITE_LONG_FIELD`, `WRITE_CHAR_FIELD`,
  `WRITE_ENUM_FIELD`, plus `WRITE_FLOAT_FIELD`, `WRITE_BOOL_FIELD`,
  `WRITE_STRING_FIELD`, `WRITE_NODE_FIELD`, `WRITE_BITMAPSET_FIELD`,
  `WRITE_ATTRNUMBER_ARRAY` etc. (continuation of the block starting at
  `:40`).
- Location-field handling driven by `write_location_fields` GUC state
  — locations are normally skipped (irrelevant outside the original
  query text), but `nodeToStringWithLocations` flips the flag on for
  debug paths. `:28-29` `[verified-by-code]`
- `outChar`, `outDouble` static helpers for tricky scalars. `:31-32`
- `#include "outfuncs.funcs.c"` brings in the per-node-type
  generated bodies.
- Custom-out functions for nodes marked `pg_node_attr(custom_read_write,
  special_read_write)` — `Const`, `A_Const`, `Bitmapset`, the value
  nodes, `ExtensibleNode`.

## Public entries

- `outNode(StringInfo, const void *obj)` — write any node into a
  StringInfo (recursive via the dispatch switch).
- `nodeToString(const void *obj)` — palloc'd C string. Locations
  omitted.
- `nodeToStringWithLocations` — debug variant that keeps location
  fields (for `debug_write_read_parse_plan_trees` round-trip testing).
- `bmsToString(const Bitmapset *)` — convenience for individual
  bitmapsets.
- `outBitmapset`, `outToken`, `outDatum` — pieces exposed to other
  callers via `nodes.h`.

## Cross-references

- Generator: `source/src/backend/nodes/gen_node_support.pl`
- Companion: `readfuncs.c` is the inverse.
- Consumers: `src/backend/utils/cache/plancache.c`,
  `src/backend/rewrite/rewriteSupport.c`,
  `src/backend/access/transam/parallel.c` (PlannedStmt over DSM).

## Synthesized by
<!-- backlinks:auto -->
- [subsystems/optimizer.md](../../../../subsystems/optimizer.md)
