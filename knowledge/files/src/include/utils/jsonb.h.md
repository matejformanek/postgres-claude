# `src/include/utils/jsonb.h`

- **File:** `source/src/include/utils/jsonb.h` (467 lines)
- **Last verified commit:** `ef6a95c7c64de07dff4dd1f1da88ffae7b086ef3` (2026-06-01)

## Purpose

Defines the on-disk and in-memory representations of the `jsonb`
type, the binary-iterator state machine token enum, GIN opclass
strategy numbers, all `Datum`↔`Jsonb` macros, and the public
prototype surface implemented by `jsonb.c` and `jsonb_util.c`.

## Top of file (verbatim)

```
 * jsonb.h
 *    Declarations for jsonb data type support.
```
(`:1-11` [from-comment])

## Public surface

- **Iterator tokens:** `JsonbIteratorToken` enum (`:19-29`) —
  `WJB_DONE/KEY/VALUE/ELEM/BEGIN_ARRAY/END_ARRAY/BEGIN_OBJECT/END_OBJECT`.
- **GIN strategies:** `JsonbContainsStrategyNumber` (7),
  `JsonbExistsStrategyNumber` (9), `JsonbExistsAnyStrategyNumber`
  (10), `JsonbExistsAllStrategyNumber` (11),
  `JsonbJsonpathExistsStrategyNumber` (15),
  `JsonbJsonpathPredicateStrategyNumber` (16) (`:32-37`).
- **GIN encoding flags:** `JGINFLAG_KEY/NULL/BOOL/NUM/STR`,
  `JGINFLAG_HASHED`, `JGIN_MAXLENGTH` (`:62-68`) — the prefix-byte
  layout used by the `jsonb_ops` opclass.
- **JEntry constants:** `JENTRY_OFFLENMASK` (0x0FFFFFFF),
  `JENTRY_TYPEMASK`, `JENTRY_HAS_OFF`, plus the type values
  `JENTRY_ISSTRING/NUMERIC/BOOL_FALSE/BOOL_TRUE/NULL/CONTAINER`
  (`:140-150`).
- **Container header flags:** `JB_CMASK`, `JB_FSCALAR`, `JB_FOBJECT`,
  `JB_FARRAY` (`:202-205`) and the `JsonContainer*` /
  `JB_ROOT_*` macros.
- **Datum macros:** `DatumGetJsonbP[Copy]`, `JsonbPGetDatum`,
  `PG_GETARG_JSONB_P[_COPY]`, `PG_RETURN_JSONB_P` (`:400-420`).
- **Support functions:** `JsonbValueToJsonb`, `JsonbIteratorInit`,
  `JsonbIteratorNext`, `compareJsonbContainers`,
  `JsonbDeepContains`, `JsonbHashScalarValue[Extended]`,
  `findJsonbValueFromContainer`, `getKeyJsonValueFromContainer`,
  `getIthJsonbValueFromContainer`, `pushJsonbValue`,
  `JsonbToCString[Indent]`, `JsonbUnquote`, `JsonbExtractScalar`,
  `JsonbTypeName`, `jsonb_set_element`, `jsonb_get_element`,
  `to_jsonb_is_immutable`, `jsonb_build_object_worker`,
  `jsonb_build_array_worker` (`:422-465`).

## Key types

- **`Jsonb`** (`:213-218`) — varlena: `int32 vl_len_` + a
  `JsonbContainer root`. The root has no JEntry of its own — its
  type comes from `JB_F*` bits in `root.header`
  (`:93-101` [from-comment]).
- **`JsonbContainer`** (`:192-199`) — `uint32 header` (count + flags)
  + FAM `JEntry children[]`. Object stores all keys before all
  values for cache friendliness (`:187-190` [from-comment]).
- **`JEntry`** (`:138`) — `typedef uint32`. See § Key invariants.
- **`enum jbvType`** (`:227-247`) — `jbvNull, jbvString, jbvNumeric,
  jbvBool, jbvArray, jbvObject, jbvBinary, jbvDatetime`. Ordinal
  order matters: it's the comparison rank used by
  `compareJsonbContainers`.
- **`JsonbValue`** (`:255-297`) — tagged union with variants for
  `numeric`, `boolean`, `string{len,val}`, `array{nElems,elems,
  rawScalar}`, `object{nPairs,pairs}`, `binary{len,data}`,
  `datetime{value,typid,typmod,tz}`.
- **`JsonbPair`** (`:313-318`) — `{key, value, order}`; `order`
  preserves observed order for "last wins" dedup
  (`:309-312` [from-comment]).
- **`JsonbInState`** (`:331-339`) — builder state, with optional
  `outcontext` and soft-error `escontext`.
- **`JsonbParseState`** (`:346-353`) — one frame of the
  push-parser stack.
- **`JsonbIterator` + `JsonbIterState`** (`:359-396`) — streaming
  reader state. Dual cursors `curDataOffset` (current key) and
  `curValueOffset` (current value) drive object iteration
  (`:385-390` [from-comment]).

## Key invariants

- **Root container is implicit-typed.** No JEntry for the root; its
  jbvArray/jbvObject identity comes from JB_FARRAY/JB_FOBJECT bits
  in `root.header`. Naked scalars are wrapped as a 1-element array
  with both `JB_FSCALAR | JB_FARRAY` set (`:93-101`
  [from-comment]).
- **JEntry encodes EITHER length OR end-offset.** High bit
  `JENTRY_HAS_OFF` selects; low 28 bits hold the value (`:113-137`
  [from-comment]). The mixed encoding is what enables TOAST
  compression to work on jsonb at all.
- **Every `JB_OFFSET_STRIDE` (= 32)-th child gets an offset; the
  rest get lengths.** Caller must walk through `JBE_ADVANCE_OFFSET`
  rather than assume (`:163-180` [from-comment]).
- **4-byte alignment within Jsonb.** Padding is at the *beginning*
  of the variable-length portion of types that need it
  (`:103-109` [from-comment]).
- **`jbvDatetime` is in-memory only.** Serialized to string when
  written out (`:240-246` [from-comment]). Produced by
  jsonpath's `.datetime()` method, never stored on disk.
- **JsonbValue ordinal ordering matters for comparators.** Any
  reorder breaks btree.

## Cross-references

- `source/src/backend/utils/adt/jsonb.c` — I/O, casts, agg.
- `source/src/backend/utils/adt/jsonb_util.c` — iterator,
  comparator, deep-contains, hashing, on-disk converter.
- `source/src/backend/utils/adt/jsonb_op.c` — operators.
- `source/src/backend/utils/adt/jsonb_gin.c` — GIN opclasses
  using JGIN* flags.

## Open questions

- Could `JB_OFFSET_STRIDE` ever be made per-container? Existing
  header bits are all used. `[from-comment]` notes that storing
  stride in the container header was considered and rejected.

## Confidence tag tally

- `[from-comment]` × 9
- `[verified-by-code]` × 0
- `[unverified]` × 0
