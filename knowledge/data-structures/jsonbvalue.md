# JsonbValue — in-memory JSONB representation

`JsonbValue` is the **deserialized** form of JSONB used during
manipulation — converting on-disk JSONB into something a C
function can navigate, mutate, or build up before
re-serializing. Distinct from the on-disk `Jsonb` struct (which
is a packed varlena), `JsonbValue` is a tagged union with
pointers to children. Used by every JSONB function that reads
or constructs JSON values.

Anchors:
- `source/src/include/utils/jsonb.h:227-247` — `jbvType` enum
  [verified-by-code]
- `source/src/include/utils/jsonb.h:255-297` — `JsonbValue`
  struct [verified-by-code]
- `source/src/backend/utils/adt/jsonb.c` — input/output
- `knowledge/subsystems/utils-mmgr.md` — JsonbValue lives in
  memory contexts

## The type enum

```c
enum jbvType
{
    /* Scalar types */
    jbvNull = 0x0,
    jbvString,
    jbvNumeric,
    jbvBool,
    /* Composite types */
    jbvArray = 0x10,
    jbvObject,
    /* Binary (i.e. on-disk struct Jsonb) jbvArray/jbvObject */
    jbvBinary,
    /* Virtual types */
    jbvDatetime = 0x20,
};
```

[verified-by-code `jsonb.h:227-247`]

Three categories:

- **Scalars** (0x0..0xF) — JSON primitives. `jbvNull`,
  `jbvString`, `jbvNumeric`, `jbvBool`.
- **Composites** (0x10..0x1F) — `jbvArray`, `jbvObject`
  (fully deserialized; `elems[]` / `pairs[]` arrays of
  child JsonbValues), and `jbvBinary` (composite still in
  its on-disk packed form — lazy deserialization).
- **Virtual** (0x20..) — `jbvDatetime` for `jsonpath` /
  `SQL/JSON` ops; gets serialized to a string on output.

The `IsAJsonbScalar` macro [verified-by-code `jsonb.h:299-301`]
distinguishes scalar from composite — important for ops that
behave differently per category.

## The tagged-union struct

[verified-by-code `jsonb.h:255-297`]

```c
struct JsonbValue
{
    enum jbvType type;

    union
    {
        Numeric numeric;             /* jbvNumeric */
        bool    boolean;             /* jbvBool */
        struct { int len; char *val; }   string;      /* jbvString */
        struct { int nElems; JsonbValue *elems; bool rawScalar; }  array;
        struct { int nPairs; JsonbPair *pairs; }                    object;
        struct { int len; JsonbContainer *data; }                   binary;
        struct { Datum value; Oid typid; int32 typmod; int tz; }    datetime;
    } val;
};
```

The `type` field selects which `val.*` member is meaningful.
Standard tagged-union discipline.

## Scalar memory layout

- **`jbvNull`** — no payload.
- **`jbvBool`** — single bool.
- **`jbvNumeric`** — pointer to a `Numeric` (arbitrary
  precision).
- **`jbvString`** — `(len, val)` where `val` is NOT
  null-terminated. Always use `len`, never `strlen`.

The non-null-terminated string is a critical detail: JSONB
strings may contain embedded nulls; `strlen` would lie.

## Array layout

```c
struct {
    int           nElems;
    JsonbValue   *elems;
    bool          rawScalar;
} array;
```

`elems` is a contiguous array of `JsonbValue`. **Heterogeneous
types are fine** — `[1, "two", null, {"key": "value"}]` packs
into 4 JsonbValues with varying types.

`rawScalar` is a JSON-spec quirk: a top-level "raw scalar"
(e.g. `42` or `"foo"` not wrapped in `[]` / `{}`) is internally
stored as a 1-element array with `rawScalar = true`, so the
on-disk format always has a container at the top. The flag
distinguishes "real array of one element" from "scalar
wrapped for storage."

## Object layout

```c
struct {
    int          nPairs;
    JsonbPair   *pairs;
} object;
```

Where each `JsonbPair` has key + value + order:

```c
struct JsonbPair {
    JsonbValue  key;     /* MUST be jbvString */
    JsonbValue  value;
    uint32      order;   /* original insertion index */
};
```

[verified-by-code `jsonb.h:313-318`]

- Keys MUST be `jbvString` — JSONB doesn't allow non-string
  object keys.
- `order` preserves original insertion order despite
  on-disk sort: pairs are sorted by key for fast lookup, but
  the `order` field lets duplicates be resolved
  "last-observed-wins" deterministically.

## The "binary" lazy form

```c
struct {
    int               len;
    JsonbContainer   *data;
} binary;
```

A `jbvBinary`-typed JsonbValue is a **handle to on-disk JSONB
that hasn't been deserialized yet**. The `data` pointer is
into the original `Jsonb` varlena's content; iteration over
it (via `JsonbIterator`) deserializes lazily.

This matters for performance: navigating to a deep path in a
1MB JSONB document doesn't have to fully deserialize the
intermediate containers. Walk through them in `jbvBinary` form
until you find the leaf you want.

## The Datetime virtual type

```c
struct {
    Datum   value;
    Oid     typid;
    int32   typmod;
    int     tz;
} datetime;
```

Used by `jsonpath` (SQL/JSON path language) for
type-aware date arithmetic. The `value` is a regular PG
datum of the named `typid` (Date / Time / Timestamp /
TimestampTz / etc.).

On serialization to JSONB output, datetimes become ISO 8601
strings (jsonpath manipulation results then look like
ordinary `jbvString`).

## Conversion to on-disk form

`JsonbValueToJsonb(JsonbValue *)` walks a JsonbValue tree and
constructs a packed on-disk `Jsonb` (a varlena). The result
is the canonical storage representation: sorted keys,
deduplicated pairs, type-tagged headers.

The reverse direction is via iterators — `JsonbIteratorInit`
+ `JsonbIteratorNext` yield JsonbValues as it walks the
on-disk form.

## Memory model

- JsonbValue itself + scalar payloads live in
  `CurrentMemoryContext` (or whatever `palloc` context is
  active).
- For arrays/objects, the `elems` / `pairs` arrays are
  separate `palloc`s.
- The `jbvBinary` `data` pointer is into the underlying
  `Jsonb` varlena, which the caller must keep pinned.

A JsonbValue tree may share storage with the original
Jsonb (via jbvBinary) or be fully owned (after a builder
finishes). The two cases have different `pfree` discipline:
fully-owned trees can be freed entirely; binary-form trees
must be freed before the underlying Jsonb is.

## Common review-time concerns

- **Strings are NOT null-terminated** — always use `(len,
  val)` together.
- **Numeric values use `Numeric` (arbitrary precision).** Don't
  cast to `int` or `double` directly; use `numeric_*`
  conversion functions.
- **Object keys MUST be `jbvString`.** Building with non-string
  keys is invalid.
- **`rawScalar` is the top-level scalar trick.** Don't apply it
  to nested arrays.
- **`jbvBinary` is a window into a Jsonb varlena.** Don't
  outlive the varlena.

## Invariants

- **[INV-1]** Object keys are always `jbvString`.
- **[INV-2]** Strings are not null-terminated; carry length.
- **[INV-3]** `rawScalar = true` only for top-level
  1-element arrays representing JSON spec-quirk scalars.
- **[INV-4]** `jbvBinary` is a handle into an underlying
  Jsonb; doesn't own storage.
- **[INV-5]** `IsAJsonbScalar` discriminates scalar
  (incl. Datetime) from composite.

## Useful greps

- All jbvType users:
  `grep -RIn 'jbvString\|jbvNumeric\|jbvArray\|jbvObject' source/src/backend/utils/adt/jsonb*.c | head -30`
- The on-disk converters:
  `grep -n 'JsonbValueToJsonb\|JsonbIteratorInit\|JsonbIteratorNext' source/src/backend/utils/adt/jsonb_util.c | head -10`
- jbvBinary navigation patterns:
  `grep -RIn 'jbvBinary' source/src/backend/utils/adt | head -15`

## Call sites
<!-- callsites:auto -->

*Auto-extracted from `source/<path>:<line>` cites in this doc's prose (bullets and free text).*
*Refresh via `scripts/populate-idiom-callsites.py` — edits inside this block are overwritten.*

| File | Line | Role |
|---|---:|---|
| [`src/backend/utils/adt/jsonb.c`](../files/src/backend/utils/adt/jsonb.c.md) | — | input/output |
| [`src/backend/utils/adt/jsonb_util.c`](../files/src/backend/utils/adt/jsonb_util.c.md) | — | iterators + on-disk conversion |
| [`src/backend/utils/adt/jsonpath_exec.c`](../files/src/backend/utils/adt/jsonpath_exec.c.md) | — | heavy user (jsonpath evaluation) |
| [`src/include/utils/jsonb.h`](../files/src/include/utils/jsonb.h.md) | 227 | jbvType enum |
| [`src/include/utils/jsonb.h`](../files/src/include/utils/jsonb.h.md) | 255 | JsonbValue struct |
| [`src/include/utils/jsonb.h`](../files/src/include/utils/jsonb.h.md) | — | public type + struct definitions |

<!-- /callsites:auto -->
## Cross-references

- `knowledge/subsystems/parser-and-rewrite.md` — JSON
  parsing produces JsonbValues.
- `knowledge/subsystems/utils-mmgr.md` — memory contexts
  hold JsonbValue allocations.
- `.claude/skills/fmgr-and-spi/SKILL.md` — JSONB SQL
  functions take and return JsonbValues via PG_GETARG /
  PG_RETURN.
- `source/src/include/utils/jsonb.h` — public type +
  struct definitions.
- `source/src/backend/utils/adt/jsonb_util.c` — iterators
  + on-disk conversion.
- `source/src/backend/utils/adt/jsonpath_exec.c` — heavy
  user (jsonpath evaluation).
