# value.c

- **Source:** `source/src/backend/nodes/value.c` (84 lines)
- **Last verified commit:** `ef6a95c7c64`
- **Depth:** read

## Purpose

Constructors for the value-wrapper node types in `value.h`:
`Integer`, `Float`, `Boolean`, `String`, `BitString`. These exist so
SQL literals can be put into a `List *` (which only holds Node
pointers / ints / OIDs). `:1-14`, `value.h:19-26` `[from-comment]`

## Functions

| Line | Function | Notes |
|---|---|---|
| 22 | `makeInteger(int i)` | `Integer{ival=i}` |
| 36 | `makeFloat(char *s)` | `Float{fval=s}`; caller must own palloc'd string |
| 48 | `makeBoolean(bool v)` | `Boolean{boolval=v}` |
| 62 | `makeString(char *s)` | `String{sval=s}`; caller must own palloc'd string |
| 76 | `makeBitString(char *s)` | `BitString{bsval=s}`; caller-owned |

Each just calls `makeNode(T)` + assigns one field. Float is
internally stored as text to avoid `double`-precision loss, since the
parser may later resolve it to `NUMERIC`. `value.h:36-46`
`[from-comment]`

## Accessor macros (`value.h:79-82`)

```c
#define intVal(v)   (castNode(Integer, v)->ival)
#define floatVal(v) atof(castNode(Float, v)->fval)
#define boolVal(v)  (castNode(Boolean, v)->boolval)
#define strVal(v)   (castNode(String, v)->sval)
```

`castNode` asserts the tag, so calling `strVal(v)` on an `Integer *`
trips under `USE_ASSERT_CHECKING`. `nodes.h:173-183`
`[verified-by-code]`

## Historical note

There used to be a single `Value` union node — hence the filename.
It was split into per-type structs to give each its own NodeTag and
clean up the read/write functions. `value.h:24-26` `[from-comment]`

## Cross-references

- Header: `source/src/include/nodes/value.h`
- Used by: `src/backend/parser/scan.l` (lexer literal output),
  `parsenodes.h` `A_Const`, anywhere a SQL literal flows in a List.
