# value.h

- **Source:** `source/src/include/nodes/value.h` (90 lines)
- **Last verified commit:** `ef6a95c7c64`
- **Depth:** read

## Purpose

Declares the five value-literal node types — `Integer`, `Float`,
`Boolean`, `String`, `BitString` — and their `makeFoo` constructors
and `intVal/floatVal/boolVal/strVal` accessors. The point of these
nodes (vs. a plain `int`/`char *`): they're Nodes, so they can live
inside a `List *`. `:19-23` `[from-comment]`

## Struct layout `:28-77`

Every value node is `pg_node_attr(special_read_write)` + `NodeTag
type;` + one payload field:

- `Integer.ival` — `int`
- `Float.fval` — `char *` (stored as text to avoid losing precision
  if it's later resolved to NUMERIC; lexer emits `T_Float` even for
  integer-looking strings too large to fit in `int`). `:36-46`
  `[from-comment]`
- `Boolean.boolval` — `bool`
- `String.sval` — `char *`
- `BitString.bsval` — `char *`

## Accessor macros `:79-82`

```c
#define intVal(v)   (castNode(Integer, v)->ival)
#define floatVal(v) atof(castNode(Float, v)->fval)
#define boolVal(v)  (castNode(Boolean, v)->boolval)
#define strVal(v)   (castNode(String, v)->sval)
```

`castNode` asserts the tag under `USE_ASSERT_CHECKING`.

## Constructors

`makeInteger(int)`, `makeFloat(char *)`, `makeBoolean(bool)`,
`makeString(char *)`, `makeBitString(char *)` — declared here,
defined in `value.c`. For Float/String/BitString, the caller owns
the palloc'd string and ownership transfers into the node.

## Historical note

There used to be a single `Value` union node — hence the filename.
It was split into per-type structs to give each its own NodeTag and
cleaner read/write functions. `:24-26` `[from-comment]`

## Cross-references

- Implementation: `source/src/backend/nodes/value.c`
- Idiom: `knowledge/idioms/node-types-and-lists.md` (Value-nodes
  section).

## Synthesized by
<!-- backlinks:auto -->
- [idioms/node-types-and-lists.md](../../../../idioms/node-types-and-lists.md)
