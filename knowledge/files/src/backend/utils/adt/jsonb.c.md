# `src/backend/utils/adt/jsonb.c`

- **File:** `source/src/backend/utils/adt/jsonb.c` (2036 lines)
- **Header:** `source/src/include/utils/jsonb.h`
- **Last verified commit:** `ef6a95c7c64de07dff4dd1f1da88ffae7b086ef3` (2026-06-01)

## Purpose

I/O routines for the `jsonb` data type: text → binary (`jsonb_in`), binary
→ text (`jsonb_out`, `JsonbToCString[Indent]`), recv/send wire format,
plus a large family of cast-to/from operators and the JSON
constructor / aggregate machinery (`to_jsonb`, `jsonb_build_object`,
`jsonb_build_array`, `jsonb_agg`, `jsonb_object_agg`). The
manipulation primitives (iterator, deep-contains, hash, comparator,
on-disk encoder/decoder) live in `jsonb_util.c`. Top-of-file
comment is just `"I/O routines for jsonb type"` (`jsonb.c:3-4`
[from-comment]).

## Top of file (verbatim)

```
 * jsonb.c
 *      I/O routines for jsonb type
```
(`:1-12` [from-comment])

## Public surface (selected, fmgr entry points)

- `jsonb_in` / `jsonb_out` / `jsonb_recv` / `jsonb_send`
  (`:63, 98, 79, 114`) — type I/O. recv prefixes a 1-byte version
  number; only version 1 exists (`:75-77, 87-90` [from-comment]).
- `jsonb_typeof` (`:220`) — returns text `"object" / "array" /
  "string" / "number" / "boolean" / "null"` via `JsonbTypeName` (`:172`).
- `JsonbToCString` (`:465`) / `JsonbToCStringIndent` (`:474`) — exported
  pretty/compact serializers shared with jsonpath, jsonfuncs, etc.
- `to_jsonb` (`:1093`), `jsonb_build_object`/`_array` (`:1182, 1242`)
  plus `_noargs` zero-arg shortcuts (`:1202, 1263`), `jsonb_object` two
  forms (`:1284, 1384`).
- `jsonb_agg_transfn` / `_strict_transfn` / `_finalfn`
  (`:1534, 1543, 1549`) — aggregate state machine; uses
  `JsonbInState`. The `_strict_` variant skips NULL inputs.
- `jsonb_object_agg_transfn` + 4 variants (`:1673, 1683, 1692, 1701`)
  — combos of strict (skip nulls) × unique_keys (reject duplicate
  keys). The unique-keys version is what `JSON_OBJECTAGG ... WITH
  UNIQUE KEYS` SQL/JSON syntax desugars to.
- Cast entries: `jsonb_bool, jsonb_numeric, jsonb_int2/int4/int8,
  jsonb_float4/float8` (`:1820–~1990`) — convert a jbvBool / jbvNumeric
  scalar jsonb to the named SQL type or raise
  `cannot_cast_jsonb_value` via `cannotCastJsonbValue` (`:1789`).

## Key types

- **`JsonbInState`** (declared in header, used here) — combined
  output buffer + parse-state stack + soft-error context. Callers
  zero-init and may set `outcontext` / `escontext` (`jsonb.h:326-339`
  [from-comment]).
- **`JsonbAggState`** (local, `:28-35`) — per-aggregate state: a
  `JsonbInState`, the key/value `JsonTypeCategory`, and cached output
  function OIDs (avoids re-resolving `outfunc` on every row).

## Key invariants

- **Raw scalar wrapping.** A naked scalar jsonb is stored on disk as
  a 1-element array with `JB_FSCALAR | JB_FARRAY` flags (`jsonb.h:99-101`
  [from-comment]). The output path skips the `[ ]` brackets when
  `v.val.array.rawScalar` is set (`:518-523, 575-579`
  [verified-by-code]).
- **Object key sort order.** Keys are de-duplicated and sorted by
  length then bytewise (`jsonb_util.c:2026-2044`
  [verified-by-code]) — *not* by collation. This is why jsonb's key
  ordering is stable across locales but does *not* match standard
  Unicode ordering.
- **String length check.** Both keys and string values must fit
  in `JENTRY_OFFLENMASK` (≈ 256 MB); enforced by `checkStringLen`
  (`:269`) which raises `string too long to represent as jsonb
  string`.
- `JsonbToCStringWorker` asserts `level == 0` on exit (`:594`
  [verified-by-code]) — i.e. all containers have been properly closed.

## Functions of note

- **`jsonb_from_cstring`** (`:240`) — installs the seven
  `JsonSemAction` callbacks (`jsonb_in_object_start`, etc.) and runs
  the streaming JSON lexer (`pg_parse_json`). On success the top
  `JsonbValue` is in `state.res`, flattened to a `Jsonb` varlena by
  `JsonbValueToJsonb`. `unique_keys=true` from the SQL/JSON syntax
  triggers per-object dedup checking inside `appendKey` (in
  `jsonb_util.c`).
- **`JsonbToCStringWorker`** (`:483`) — single recursive pass over a
  `JsonbContainer` driven by `JsonbIteratorNext`. The state machine
  handles the `WJB_KEY → WJB_VALUE` pair by issuing a second
  `JsonbIteratorNext`; if the value is itself a container, it sets
  `redo_switch = true` so the outer switch re-runs on the
  `WJB_BEGIN_*` token (`:551-565` [verified-by-code]). Used by both
  text output and any callable that needs a JSON string from a
  Jsonb.
- **`composite_to_jsonb`** (`:978`) — turns a HeapTuple/Datum row into
  a jsonb object by walking `TupleDescriptor` attributes, recursing on
  composite/array fields via `datum_to_jsonb_internal`. The dispatch
  on `JsonTypeCategory` matches what `to_jsonb` decides at top level.
- **`to_jsonb_is_immutable`** (`:1081`) — used by the planner to
  decide whether `to_jsonb(expr)` can be folded at plan time. Recurses
  through array/composite element categories; returns false if any
  element type's output function isn't immutable.
- **`jsonb_object_two_arg`** (`:1384`) — the `jsonb_object(keys[],
  values[])` constructor. Mirrors `jsonb_object`'s single-array form
  (`:1284`) which interprets the array as alternating key/value
  pairs.
- **`JsonbExtractScalar`** (`:1749`) — returns true iff the container
  is the raw-scalar pseudo-array; used by every `jsonb_*` cast (e.g.
  `jsonb_bool`) to pull the underlying scalar.
- **`cannotCastJsonbValue`** (`:1789`) — uniform error path used by
  every `jsonb_<sqltype>` cast when the scalar's `jbvType` doesn't
  match the SQL target type.

## Cross-references

- `source/src/backend/utils/adt/jsonb_util.c` — iterator, comparator,
  deep-contains, on-disk encoder.
- `source/src/backend/utils/adt/jsonb_op.c` — operators (`?`, `@>`,
  `<`, `=`, hash) registered in pg_operator.
- `source/src/backend/utils/adt/jsonfuncs.c` — accessors (`->`, `->>`,
  `#>`, `jsonb_set`, `jsonb_path_query`, etc.).
- `source/src/backend/utils/adt/json.c` — the *text* json type
  (jsonb's lazy cousin; just stores normalized text).
- `source/src/common/jsonapi.c` — the shared streaming JSON lexer that
  drives both `json_in` and `jsonb_in`.

## Open questions

- The agg variants table (4× `jsonb_object_agg_*`) duplicates a lot of
  boilerplate; is there a planned consolidation? `[unverified]`
- `jsonb_recv` always passes `unique_keys=false` (`:92`); SQL/JSON
  binary format doesn't carry uniqueness flag — does this matter for
  logical replication? `[unverified]`

## Confidence tag tally

- `[verified-by-code]` × 6
- `[from-comment]` × 4
- `[unverified]` × 2
