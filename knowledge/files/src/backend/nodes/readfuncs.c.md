# readfuncs.c

- **Source:** `source/src/backend/nodes/readfuncs.c` (~700 lines + generated)
- **Last verified commit:** `ef6a95c7c64`
- **Depth:** skim

## Purpose

Inverse of `outfuncs.c`. Implements `stringToNode(const char *str)`:
parse a Lisp-ish serialized node tree back into a node tree. Used by:

- The rewriter loading rules / views from `pg_rewrite`.
- Parallel workers receiving a `PlannedStmt` from the leader.
- Index-expression and partition-bound deserialization out of various
  catalogs.

## Top-of-file invariant `:13-24`

Parse-location fields, when read back, are normally set to `-1`
("unknown") — the stored value would be wrong for the current query's
text. The exception is `restore_location_fields`, used only by the
`debug_write_read_parse_plan_trees` test to verify round-trip
fidelity. `[from-comment]`

## Lexer

Tokens come from `pg_strtok` (defined in `read.c`). Each
`READ_*_FIELD(fldname)` macro consumes two tokens — the `:fldname`
label, then the value — and assigns into `local_node->fldname`. The
hand-written macros: `READ_INT_FIELD`, `READ_UINT_FIELD`,
`READ_INT64_FIELD`, `READ_UINT64_FIELD`, …  `:35-79`
`[verified-by-code]`

The companion file `read.c` provides `nodeRead` (the dispatcher),
`pg_strtok`, and primitive readers for booleans, datums, integer-array
columns (`readBoolCols`, `readIntCols`, `readOidCols`,
`readAttrNumberCols`).

## Field-init macros

- `READ_LOCALS_NO_FIELDS(T)` — declares `T *local_node = makeNode(T);`
- `READ_TEMP_LOCALS()` — `const char *token; int length;` for
  pg_strtok.
- `READ_LOCALS(T)` — both.

`:42-55` `[verified-by-code]`

## Dispatch

- `#include "readfuncs.funcs.c"` — the per-node-type bodies.
- The big switch in `nodeRead` (in `read.c`, not here) dispatches on
  the leading `T_*` label.

## Cross-references

- Generator: `source/src/backend/nodes/gen_node_support.pl`
- Companion: `outfuncs.c`.
- Lexer / dispatcher: `source/src/backend/nodes/read.c`.

## Synthesized by
<!-- backlinks:auto -->
- [subsystems/optimizer.md](../../../../subsystems/optimizer.md)
