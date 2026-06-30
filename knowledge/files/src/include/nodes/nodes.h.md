# nodes.h

- **Source:** `source/src/include/nodes/nodes.h` (444 lines)
- **Last verified commit:** `f0a4f280b4d3` (2026-06-25; clean re-pin, all enum/macro cites hold ±2)
- **Depth:** deep-read

## Purpose

The root header of the Node taxonomy. Defines:

- `Node` (just `NodeTag type;`) and the `NodeTag` enum.
- `makeNode` / `newNode` / `nodeTag` / `IsA` / `castNode` /
  `NodeSetTag` macros.
- The `pg_node_attr(...)` macro and its full documented attribute set
  (consumed by `gen_node_support.pl`).
- Public prototypes for `outNode`, `nodeToString`, `stringToNode`,
  `copyObjectImpl`, `equal`.
- A handful of cross-cutting typedefs and enums that don't fit
  cleanly in parsenodes.h or plannodes.h: `ParseLoc`, `Selectivity`,
  `Cost`, `Cardinality`, `CmdType`, `JoinType`, `AggStrategy`,
  `AggSplit`, `SetOpCmd`, `SetOpStrategy`, `OnConflictAction`,
  `LimitOption`.

## NodeTag enum

```c
typedef enum NodeTag {
    T_Invalid = 0,
#include "nodes/nodetags.h"
} NodeTag;
```

`:26-31`. `nodetags.h` is **generated** by `gen_node_support.pl` from
the canonical input-file list. Order is stable for a given commit but
inserting a new node renumbers later tags. `:21-24` `[from-comment]`

## Core macros

| Macro | Definition | Purpose |
|---|---|---|
| `nodeTag(p)` | `((const Node*)(p))->type` | read the tag |
| `newNode(size, tag)` | inline: palloc0 + set type | building block |
| `makeNode(T)` | `((T *) newNode(sizeof(T), T_##T))` | the usual constructor |
| `NodeSetTag(p, t)` | overwrite tag (rare) | |
| `IsA(p, T)` | `nodeTag(p) == T_##T` | runtime type test |
| `castNode(T, p)` | type-asserting downcast (Assert when `USE_ASSERT_CHECKING`, plain cast otherwise) | safer than raw cast |

`:139-183` `[verified-by-code]`. **There is no separate `nodes.c`** —
`newNode`/`makeNode` are inline; the heavy machinery lives in
`copyfuncs.c`, `equalfuncs.c`, `outfuncs.c`, `readfuncs.c`,
`queryjumblefuncs.c`.

## `pg_node_attr` attribute catalog `:43-125`

### Node-level

- `abstract` — supertype only, no tag emitted
- `custom_copy_equal` — hand-written copy + equal
- `custom_read_write` — hand-written out + read
- `custom_query_jumble` — hand-written jumbler
- `no_copy` / `no_equal` / `no_copy_equal`
- `no_query_jumble` / `no_read`
- `nodetag_only` — no funcs at all, just a tag
- `special_read_write` — special treatment in `outNode`/`nodeRead`
- `nodetag_number(VALUE)` — pin a tag value (used in stable branches
  to add nodes without renumbering)

Inheritance: the `no_*` attributes are inherited from a supertype that
appears as the first field. `nodetag_only` is **not** inherited.
`:79-85` `[from-comment]`

### Field-level

- `array_size(OTHERFIELD)` — dynamic array length tracked by another
  field (scalar or list-length)
- `copy_as(VALUE)`, `copy_as_scalar`
- `equal_as_scalar`, `equal_ignore`, `equal_ignore_if_zero`
- `query_jumble_ignore`, `query_jumble_squash`,
  `query_jumble_location`
- `read_as(VALUE)`, `read_write_ignore`
- `write_only_relids`, `write_only_nondefault_pathtarget`,
  `write_only_req_outer` — Path-struct special handling

## Cross-cutting enums (kept here to avoid header cycles)

- `CmdType` `:272-284` — SELECT/INSERT/UPDATE/DELETE/MERGE/UTILITY/NOTHING
- `JoinType` `:297-332` — INNER/LEFT/FULL/RIGHT/SEMI/ANTI/RIGHT_SEMI/
  RIGHT_ANTI/UNIQUE_OUTER/UNIQUE_INNER. `IS_OUTER_JOIN` macro
  `:348-354` excludes INNER, SEMI, RIGHT_SEMI, and the planner-only
  UNIQUE_* proxies.
- `AggStrategy` `:362-368` — PLAIN/SORTED/HASHED/MIXED
- `AggSplit` `:384-392` — SIMPLE/INITIAL_SERIAL/FINAL_DESERIAL
  (bitmask of `AGGSPLITOP_*`)
- `SetOpCmd` `:406-412`, `SetOpStrategy` `:414-418`
- `OnConflictAction` `:426-432` — NONE/NOTHING/UPDATE/SELECT
- `LimitOption` `:440-444` — COUNT / WITH_TIES

## Public function prototypes (FRONTEND ifdef'd out for value.h)

- `outNode`, `outToken`, `outBitmapset`, `outDatum`
- `nodeToString`, `nodeToStringWithLocations`, `bmsToString`
- `stringToNode`, `stringToNodeWithLocations` (debug)
- `readBitmapset`, `readDatum`, `readBoolCols`, `readIntCols`,
  `readOidCols`, `readAttrNumberCols`
- `copyObjectImpl` (wrapped by the `copyObject` macro at `:228-233`)
- `equal`

## Cross-references

- Generator: `source/src/backend/nodes/gen_node_support.pl`
- Generated: `nodes/nodetags.h`, `copyfuncs.funcs.c`, etc.
- Idiom doc: `knowledge/idioms/node-types-and-lists.md`

## Synthesized by
<!-- backlinks:auto -->
- [idioms/node-types-and-lists.md](../../../../idioms/node-types-and-lists.md)
- [idioms/aggregate-partial-finalize.md](../../../../idioms/aggregate-partial-finalize.md)

## Appears in scenarios

<!-- scenarios:auto:begin -->

- [Scenario — Add a new Node type](../../../../scenarios/add-new-node-type.md)

<!-- scenarios:auto:end -->

