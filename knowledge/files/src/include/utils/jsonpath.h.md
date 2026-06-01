# `src/include/utils/jsonpath.h`

- **File:** `source/src/include/utils/jsonpath.h` (318 lines)
- **Last verified commit:** `ef6a95c7c64de07dff4dd1f1da88ffae7b086ef3` (2026-06-01)

## Purpose

Defines the on-disk and in-memory representations of the
SQL/JSON `jsonpath` type: the varlena header, the
`JsonPathItemType` enum (whose ordinals are on-disk), the
binary `JsonPathItem` cursor used by the executor, the
write-side `JsonPathParseItem` tree produced by the bison
grammar, regex-flag bits, and the SQL/JSON query function
prototypes.

## Top of file (verbatim)

```
 * jsonpath.h
 *  Definitions for jsonpath datatype
```
(`:1-11` [from-comment])

## Public surface

- **Datum macros:** `DatumGetJsonPathP[Copy]`,
  `PG_GETARG_JSONPATH_P[_COPY]`, `PG_RETURN_JSONPATH_P` (`:33-47`).
- **Version / flags:** `JSONPATH_VERSION` (`0x01`, `:29`),
  `JSONPATH_LAX` (`0x80000000`, `:30`), `JSONPATH_HDRSZ` (`:31`).
- **Item type enum:** `JsonPathItemType` (`:62-126`) — 60+
  ordinals; first four (`jpiNull`/`jpiString`/`jpiNumeric`/`jpiBool`)
  deliberately alias `jbvNull`/`jbvString`/etc.
- **Regex flag bits:** `JSP_REGEX_ICASE/DOTALL/MLINE/WSPACE/QUOTE`
  (`:129-133`).
- **`jspIsScalar(type)`** macro (`:48`) — range test for literal
  items.
- **`jspHasNext(jsp)`** macro (`:202`).
- **Reader API:** `jspInit`, `jspInitByBuffer`, `jspGetNext`,
  `jspGetArg`, `jspGetLeftArg`, `jspGetRightArg`, `jspGetNumeric`,
  `jspGetBool`, `jspGetString`, `jspGetArraySubscript`,
  `jspIsMutable`, `jspOperationName` (`:204-217`).
- **Parser entry:** `parsejsonpath` (`:286`),
  `jspConvertRegexFlags` (`:289`).
- **SQL/JSON query:** `JsonPathExists` (`:307`), `JsonPathQuery`
  (`:308-310`), `JsonPathValue` (`:311-313`).
- **JSON_TABLE:** `JsonbTableRoutine` PGDLLIMPORT (`:316`).

## Key types

- **`JsonPath`** (`:22-27`) — `int32 vl_len_; uint32 header;
  char data[FLEX]`. Header carries `JSONPATH_VERSION` in low bits
  and `JSONPATH_LAX` in the MSB.
- **`JsonPathItemType`** (`:62-126`) — *order is on-disk*; new
  values must be appended (`:54-60` [from-comment]).
- **`JsonPathItem`** (`:143-200`) — read-side cursor: `type`,
  `nextPos`, `base`, and a `content` union with `args` (binary op),
  `arg` (unary), `array` (subscripts), `anybounds` (`.**` depth),
  `value` (scalars), `like_regex`.
- **`JsonPathParseItem`** (`:225-278`) — write-side tree; has a
  `next` pointer for chain links plus matching union variants.
- **`JsonPathParseResult`** (`:280-284`) — `expr` tree + `lax`
  flag, returned by `parsejsonpath`.
- **`JsonPathVariable`** (`:295-303`) — passed in by callers of
  `JsonPathExists/Query/Value` to bind `$varname` references.

## Key invariants

- **On-disk header layout.** `header` low byte = version (must be
  1), MSB = lax flag (`:29-31` [from-comment]).
- **`jpiNull..jpiBool` ordinals match `jbvNull..jbvBool`.** Required
  so jsonpath scalar literals can be compared against jsonb scalars
  directly without translation (`:64-67`, `:48`
  [from-comment]).
- **Item type ordinals are on-disk forever.** "To preserve
  pg_upgradability, the order must not be changed, and new values
  must be added at the end" (`:54-60` [from-comment]).
- **`nextPos == 0` means end of chain.** Used by `jspHasNext`
  (`:202`) and by `jspGetNext` to halt iteration.
- **`JsonPathParseItem` is parse-only.** Discarded after
  flattening; never seen by the executor.

## Cross-references

- `source/src/backend/utils/adt/jsonpath.c` — flatten /
  pretty-print / accessor implementations.
- `source/src/backend/utils/adt/jsonpath_exec.c` — runs binary
  form, consumes `JsonPathItem` and `JsonPathVariable`.
- `source/src/backend/utils/adt/jsonpath_internal.h` — parser
  internal types (`JsonPathString`).
- `source/src/include/utils/jsonb.h` — `jbvType` alignment.

## Open questions

- Header reserves 23 bits between version (8?) and lax flag (1) —
  effectively wasted today, but no clear reservation comment.
  `[inferred]`
- `JsonPathItem.content.like_regex` keeps `pattern` and
  `patternlen` but no flag whether compilation cache is hot — the
  compiled regex lives somewhere else. `[unverified]`

## Confidence tag tally

- `[from-comment]` × 5
- `[inferred]` × 1
- `[unverified]` × 1
