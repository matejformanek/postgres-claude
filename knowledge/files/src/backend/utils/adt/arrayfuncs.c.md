# `src/backend/utils/adt/arrayfuncs.c`

- **File:** `source/src/backend/utils/adt/arrayfuncs.c` (6988 lines)
- **Header:** `source/src/include/utils/array.h`
- **Last verified commit:** `ef6a95c7c64de07dff4dd1f1da88ffae7b086ef3` (2026-06-01)

## Purpose

Core support for PostgreSQL's polymorphic array type: I/O, subscripting
(get/set element and slice), comparison/equality, hashing, dimension
introspection, NULL handling, and construct/deconstruct helpers used by
the executor and other ADT code.

## On-disk layout (from `array.h:6-29` [from-comment])

```
<vl_len_>     varlena header
<ndim>        int — number of dimensions (≤ MAXDIM = 6)
<dataoffset>  int32 — offset to data, or 0 if no nulls bitmap
<elemtype>    Oid — element type OID
<dimensions>  int[ndim] — length per axis
<lower bnds>  int[ndim] — lower bound per axis
<null bitmap> optional — 1 = non-null (matches tuple null-bitmap conv)
<actual data> MAXALIGN'd, row-major (last subscript varies fastest)
```

**Limits**: `MAXDIM = 6` (`array.h:75`), `MaxArraySize = MaxAllocSize /
sizeof(Datum)` ≈ a quarter billion elements (`array.h:78-82`
[from-comment]).

**TOAST rule**: "array elements of toastable datatypes NOT be toasted,
since the tupletoaster won't know they are there." (`array.h:30-34`
[from-comment]) — i.e. you can compress the whole array as one TOAST
blob, but individual elements must be inline.

**OIDVECTOR / INT2VECTOR** are storage-compatible with arrays but
restricted to 1-D with no nulls. NAME, POINT, etc. are "fixed-length
arrays" — just fixed-size byte sequences with no overhead.

## Key entry points

I/O:
- `array_in` (`:181`) — parses textual `{a,b,{c,d}}` notation. Recursive
  via `ReadArrayDimensions` / `ReadArrayStr`. Supports the
  `[lb:ub]={...}` lower-bound syntax. Soft-error capable.
- `array_out` (`:1021`) — serialize to text.
- `array_recv` / `array_send` (`:1275`, `:1553`) — binary protocol.

Introspection:
- `array_ndims`, `array_dims`, `array_lower`, `array_upper`,
  `array_length`, `array_cardinality` (`:1656-1824`).

Subscripting:
- `array_get_element` (`:1824`) and `_expanded` variant (`:1925`).
- `array_get_slice` (`:2034`).
- `array_set_element` (`:2205`), `_expanded` (`:2506`).
- `array_set_slice` (`:2811`).
- `array_ref` (`:3151`) / `array_set` (`:3168`) — older wrappers.
- `array_map` (`:3206`) — apply a function to each element.

Construction:
- `construct_array(elems, nelems, elmtype, ...)` (`:3367`),
  `construct_array_builtin` (`:3387`), `construct_md_array` (`:3500`),
  `construct_empty_array` (`:3587`), `construct_empty_expanded_array`
  (`:3604`).
- `deconstruct_array` (`:3638`), `deconstruct_array_builtin` (`:3705`)
  — extract a Datum[] / bool[] pair.
- `array_contains_nulls` (`:3781`) — fast O(bitmap-size) check.

Comparison and hash:
- `btarraycmp` (`:3985`) — btree compare proc.
- `array_cmp` (`:3997`) — the workhorse used by both `=`/`<>` (via
  `array_eq`/`array_ne`, `:3828`, `:3955`) and ordering (`array_lt` /
  `_gt` / `_le` / `_ge`, `:3961-3979`). Compares element-by-element
  using the element type's default btree opclass; arrays compare equal
  iff same shape and corresponding elements compare equal.
- `hash_array` (`:4170`), `hash_array_extended` (`:4303`).
- `arrayoverlap` (`:4536`) — the `&&` operator. `arraycontains` (`:4554`)
  — `@>`. Both delegate to `array_contain_compare` (`:4393`).

## Expanded arrays

A varlena array can be promoted to an **expanded** representation
("expanded object" TOAST infrastructure — `array.h:48-51`) for repeated
in-place modification by the executor (e.g. `arr[i] := …` in PL/pgSQL).
The expanded form maintains parallel `Datum[]` and `isnull[]` arrays
alongside or instead of the flat byte storage, so element updates don't
require rewriting the whole varlena. Functions with `_expanded` suffixes
operate on this representation.

`AARR_FREE_IF_COPY(array, n)` (`:51-55`) is the macro you use instead of
`PG_FREE_IF_COPY` to avoid freeing an expanded header: only flat
varlenas should be freed; expanded headers are owned by their context.

## `ArrayIteratorData` (`:69-91`)

Returned by `array_create_iterator()`. Walks the array forward by
element or by slice (`slice_ndim`, `slice_len`, `slice_dims`,
`slice_lbound`). Caller alternates with `array_iterate()` until it
returns false.

## NULL handling

The null bitmap is omitted entirely if no element is null (cheap fast
path). When present, `dataoffset` is non-zero and points past the
bitmap to the first data byte. `array_contains_nulls` (`:3781`) only
needs to scan the bitmap, not the data.

## Cross-references

- `source/src/include/utils/array.h` — layout, `ArrayType`,
  `AnyArrayType`, `ExpandedArrayHeader`, declarations.
- `source/src/include/utils/arrayaccess.h` — element-walker macros.
- `source/src/backend/utils/adt/array_userfuncs.c` — user-callable
  array funcs (append, prepend, cat, agg, position, sample, shuffle,
  reverse).
- `source/src/backend/utils/adt/array_typanalyze.c` — ANALYZE on
  array columns (MCE — most common elements — via Lossy Counting).
- `source/src/backend/utils/adt/array_expanded.c` — expanded
  array machinery (not covered here).
- `source/src/backend/utils/adt/arrayutils.c` — small subscript-math
  helpers.

## Confidence tag tally

- `[verified-by-code]` × ~5
- `[from-comment]` × ~5
