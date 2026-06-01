# `src/backend/utils/adt/jsonb_util.c`

- **File:** `source/src/backend/utils/adt/jsonb_util.c` (2110 lines)
- **Header:** `source/src/include/utils/jsonb.h`
- **Last verified commit:** `ef6a95c7c64de07dff4dd1f1da88ffae7b086ef3` (2026-06-01)

## Purpose

Engine room for the jsonb type. Converts the in-memory `JsonbValue` tree
to/from the on-disk `Jsonb` varlena format, drives the streaming
`JsonbIterator`, implements deep-contains, hashing, scalar/container
comparison, and the `pushJsonbValue` builder used by parsers and SQL/JSON
constructors. The I/O layer (`jsonb.c`) and the operators
(`jsonb_op.c`) are thin wrappers over routines defined here.

## Top of file (verbatim)

```
 * jsonb_util.c
 *    converting between Jsonb and JsonbValues, and iterating.
```
(`:1-12` [from-comment])

## Public surface

- **Builder:** `JsonbValueToJsonb` (`:96`), `pushJsonbValue` (`:583`),
  `pushJsonbValueScalar` (`:663`), `convertToJsonb` (`:1675`).
- **Iterator:** `JsonbIteratorInit` (`:935`), `JsonbIteratorNext` (`:973`).
- **Random access:** `getJsonbOffset` (`:137`), `getJsonbLength` (`:162`),
  `findJsonbValueFromContainer` (`:348`), `getKeyJsonValueFromContainer`
  (`:402`), `getIthJsonbValueFromContainer` (`:472`).
- **Compare/contain/hash:** `compareJsonbContainers` (`:194`),
  `JsonbDeepContains` (`:1189`), `JsonbHashScalarValue` (`:1443`),
  `JsonbHashScalarValueExtended` (`:1486`).

## Key types

- **`JsonbContainer`** (`jsonb.h:192-199`) — on-disk array/object: a
  `uint32 header` (count + JB_F* flags) followed by a `JEntry` array and
  the payload bytes.
- **`JEntry`** (`jsonb.h:138-150`) — 32-bit per-child header. Low 28
  bits are *either* the length of the child *or* its end-offset from
  the start of the variable-length section; high bit (JENTRY_HAS_OFF)
  selects which (`jsonb.h:113-136` [from-comment]).
- **`JsonbValue`** (`jsonb.h:255-297`) — in-memory tagged union used
  during construction, comparison, and SQL/JSON evaluation. Tag
  `jbvBinary` wraps an already-serialized container in place.
- **`JsonbParseState`** (`jsonb.h:346-353`) — single frame of the
  builder stack; tracks one container under construction plus
  `unique_keys`/`skip_nulls` flags.

## Key invariants

- **Offset stride.** Every `JB_OFFSET_STRIDE` (= 32) child stores an
  offset; the rest store length (`jsonb.h:173-180` [from-comment]).
  This keeps random access O(1) while staying compressible by TOAST.
  Callers must not assume which encoding a given JEntry uses — go
  through `getJsonbOffset` / `getJsonbLength` (`:137, 162`
  [verified-by-code]).
- **Object key ordering.** `uniqueifyJsonbObject` sorts pairs by
  `(key.len, memcmp)` then collapses duplicates last-wins
  (`:2022-2059`). The sort is *not* collation-aware; this is what
  makes jsonb's key ordering stable but non-Unicode (`:2024-2030`
  [verified-by-code]).
- **Container size limits.** Element count must fit in `JB_CMASK`
  (28 bits) AND total `JsonbValue` count must fit in `MaxAllocSize`
  (`:31-38` [from-comment]). `JSONB_MAX_ELEMS` / `JSONB_MAX_PAIRS`
  encode this.
- **Comparison order is type-first.** `compareJsonbContainers` compares
  by `jbvType` ordinal before by content; an Object always compares as
  greater than an Array which is greater than any scalar
  (`:194-345` [verified-by-code]). This is what the btree opclass
  registered in `jsonb_op.c` depends on.
- **Hashing folds container type.** `JsonbHashScalarValue` rotates the
  scalar hash and XORs with the type tag so `42::jsonb` and `"42"::jsonb`
  hash differently (`:1443-1484` [verified-by-code]).

## Functions of note

- **`JsonbValueToJsonb`** (`:96`) — top-level flattener. If the input
  is a raw scalar it wraps it in the `JB_FSCALAR | JB_FARRAY` pseudo
  array (`:103-116`); otherwise dispatches to `convertToJsonb`
  (`:1675`) which walks the in-memory tree and emits a
  4-byte-aligned varlena via a `StringInfo`.
- **`JsonbIteratorNext`** (`:973`) — single-step state machine
  returning `WJB_*` tokens. Object iteration alternates KEY/VALUE
  using the dual cursors `curDataOffset` / `curValueOffset`
  (`jsonb.h:386-390`); the `skipNested` flag lets callers fast-skip
  nested containers without descending. This is the central API every
  other consumer (output, comparison, contains) uses.
- **`JsonbDeepContains`** (`:1189`) — implements `@>`. For objects it
  pulls out the contained object's keys, binary-searches each in the
  containing object, then recurses on the matching value. For arrays
  with scalar elements it uses a sort + linear scan; for arrays with
  container elements it nests-iterates. The asymmetry between
  arrays-of-scalars and arrays-of-objects is the reason GIN
  `jsonb_path_ops` opclass exists.
- **`pushJsonbValue`** (`:583`) — the SAX-style builder. State machine:
  `WJB_BEGIN_{OBJECT,ARRAY}` pushes a new `JsonbParseState` frame,
  `WJB_KEY` / `WJB_VALUE` / `WJB_ELEM` append, `WJB_END_*` pops and
  optionally uniqueifies an object. Used by `jsonb_in`, all `to_jsonb`
  variants, and the SQL/JSON aggregates.
- **`compareJsonbContainers`** (`:194`) — runs two `JsonbIterator`s in
  lockstep. Same-token comparisons descend; mismatched composite
  tokens use the type rank fallback. Asserts that both iterators
  reach `WJB_DONE` simultaneously when equal (`:339-344`
  [verified-by-code]).
- **`uniqueifyJsonbObject`** (`:2022`) — invoked at every `WJB_END_OBJECT`.
  If `unique_keys=true` (from SQL/JSON `WITH UNIQUE KEYS`) it raises
  `duplicate JSON object key value` instead of silently last-wins-ing.

## Cross-references

- `source/src/backend/utils/adt/jsonb.c` — text I/O, casts, agg machinery.
- `source/src/backend/utils/adt/jsonb_op.c` — operators bound to these
  comparators / contains.
- `source/src/backend/utils/adt/jsonb_gin.c` — GIN opclass that
  leverages the iterator + hash.
- `source/src/common/jsonapi.c` — the SAX lexer that feeds
  `pushJsonbValue` indirectly via `jsonb_from_cstring`.

## Open questions

- The `JB_OFFSET_STRIDE` constant (32) is hard-coded; comment in
  `jsonb.h:133-136` notes it could have lived in the container header
  for future tunability. Has anyone benchmarked alternative strides?
  `[unverified]`
- `JsonbDeepContains`'s array-of-objects path is documented as
  potentially quadratic; is there a fallback to sort? `[unverified]`

## Confidence tag tally

- `[verified-by-code]` × 6
- `[from-comment]` × 4
- `[unverified]` × 2

## Synthesized by
<!-- backlinks:auto -->
- [subsystems/optimizer.md](../../../../../subsystems/optimizer.md)
