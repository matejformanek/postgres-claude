# `src/backend/utils/adt/jsonpath.c`

- **File:** `source/src/backend/utils/adt/jsonpath.c` (1638 lines)
- **Header:** `source/src/include/utils/jsonpath.h`
- **Last verified commit:** `ef6a95c7c64de07dff4dd1f1da88ffae7b086ef3` (2026-06-01)

## Purpose

I/O for the `jsonpath` SQL/JSON path-language type plus binary-tree
flatten/unflatten and pretty-printing. Parsing happens in
`jsonpath_scan.l` + `jsonpath_gram.y` (yielding a `JsonPathParseItem`
linked-list tree); this file flattens that tree into the on-disk
binary format and provides the `jspGet*` accessors used by
`jsonpath_exec.c` during query evaluation. Also home to
`jspIsMutable` used by the planner to decide whether a jsonpath query
result depends on variables/locale/timezone.

## Top of file (verbatim)

```
 * jsonpath.c
 *   Input/output and supporting routines for jsonpath
 *
 * jsonpath expression is a chain of path items. First path item is $, $var,
 * literal or arithmetic expression. Subsequent path items are accessors
 * (.key, .*, [subscripts], [*]), filters (? (predicate)) and methods (.type(),
 * .size() etc).
 * ...
 * Binary encoding of jsonpath constitutes a sequence of 4-bytes aligned
 * variable-length path items connected by links. Every item has a header
 * consisting of item type (enum JsonPathItemType) and offset of next item
 * (zero means no next item). After the header, item may have payload
 * depending on item type.
```
(`:1-65` [from-comment])

## Public surface

- **I/O:** `jsonpath_in` / `jsonpath_out` / `jsonpath_recv` /
  `jsonpath_send` (registered in pg_proc; defined `:97-170` in this
  file via `PG_FUNCTION_INFO_V1`). Wire format prefixes a 1-byte
  version (currently `JSONPATH_VERSION = 1`, `jsonpath.h:30`).
- **Tree → binary:** `jsonPathFromCstring` (`:173`) calls
  `parsejsonpath`, then `flattenJsonPathParseItem` (`:239`) emits
  4-byte-aligned items connected by `nextPos` offsets.
- **Pretty-print:** `printJsonPathItem` (`:529`) — used by
  `jsonpath_out` and inside error contexts.
- **Item accessors (read binary):** `jspInit` (`:1058`),
  `jspInitByBuffer` (`:1068`), `jspGetNext` (`:1188`), `jspGetArg`
  (`:1167`), `jspGetLeftArg` (`:1263`), `jspGetRightArg` (`:1287`),
  `jspGetBool` (`:1311`), `jspGetNumeric` (`:1319`), `jspGetString`
  (`:1327`), `jspGetArraySubscript` (`:1339`), `jspOperationName`
  (`:905`).
- **Planner hook:** `jspIsMutable` (`:1381`) — returns true if any
  item in the path references a variable, calls `.datetime()` without
  format, or uses the current locale. Drives whether
  `jsonb_path_query(jb, '$.foo')` can be folded to const.

## Key types

- **`JsonPath`** (`jsonpath.h:22-27`) — on-disk varlena: header `uint32`
  carries version in low bits and the lax/strict flag in the high bit
  (`JSONPATH_LAX = 0x80000000`, `jsonpath.h:30`).
- **`JsonPathItem`** (`jsonpath.h:143-200`) — read-side cursor into one
  binary node. The `content` union has variants for binary-op,
  unary-op, array index list, anybounds (`.**{n,m}`), scalar value,
  and like_regex payload.
- **`JsonPathParseItem`** (`jsonpath.h:225-278`) — write-side
  intermediate produced by the bison grammar; flattened by
  `flattenJsonPathParseItem`.

## Key invariants

- **All items 4-byte aligned.** `flattenJsonPathParseItem` calls
  `alignStringInfoInt` before every item write (`:243+` and helper
  `:85` [verified-by-code]).
- **`nextPos == 0` ⇒ chain end.** `jspHasNext` macro
  (`jsonpath.h:202`).
- **Item-type ordinals are on-disk.** `jpiNull`, `jpiString`,
  `jpiNumeric`, `jpiBool` are deliberately aliased to the matching
  `jbvNull`/`jbvString`/... values so jsonpath scalar literals can be
  compared directly against jsonb scalars without translation
  (`jsonpath.h:64-67` [from-comment]). Adding new item kinds is
  append-only — order must not change for pg_upgrade
  (`jsonpath.h:54-60` [from-comment]).
- **`jspIsScalar(type)` is a range test** (`jsonpath.h:48`): valid
  iff jsonpath ItemType ordinals for scalar literals match jsonb
  scalar ordinals.

## Functions of note

- **`flattenJsonPathParseItem`** (`:239`) — recursive emit. Header is
  `JsonPathItemType` (4B) + `nextPos` (4B); body varies per item.
  For binary ops it reserves two `int32` slots
  (`reserveSpaceForItemPointer`, `:86`), recurses into left/right,
  then patches the slots with the actual offsets. This two-pass
  layout is what makes random in-place walking possible without a
  separate jump table.
- **`printJsonPathItem`** (`:529`) — single function ≈ 380 lines, one
  case per `JsonPathItemType`. Item-method names live here in
  string-table form (`jspOperationName`, `:905`); both must stay in
  sync when adding methods.
- **`jspIsMutableWalker`** (`:1402`) — returns a tri-state
  `JsonPathDatatypeStatus`; used by `jspIsMutable` to detect
  `.datetime()` with format strings (locale dep), `$varname`
  references, or `current_date`-like methods. The planner uses this
  to gate constant-folding of the jsonpath argument to
  `jsonb_path_*` functions.

## Cross-references

- `source/src/backend/utils/adt/jsonpath_exec.c` — runs the binary form.
- `source/src/backend/utils/adt/jsonpath_gram.y` — yacc grammar.
- `source/src/backend/utils/adt/jsonpath_scan.l` — flex lexer.
- `source/src/backend/utils/adt/jsonpath_internal.h` — shared parser
  types (not in include/).
- SQL/JSON spec — ISO/IEC 9075-2 §9.39.

## Open questions

- Item-method list has grown to 60+ ordinals (`jpiStringFunc`,
  `jpiStrSplitPart` …) — is there a code-generation plan to keep
  `printJsonPathItem` + `jspOperationName` + bison rules in sync?
  `[unverified]`
- `JSONPATH_VERSION` is hard-coded to 1; no recv-side check for newer
  versions beyond `jsonpath_recv` (`:152`) — would a bumped writer
  silently corrupt? `[unverified]`

## Confidence tag tally

- `[verified-by-code]` × 1
- `[from-comment]` × 5
- `[unverified]` × 2

## Synthesized by
<!-- backlinks:auto -->
- [subsystems/optimizer.md](../../../../../subsystems/optimizer.md)
