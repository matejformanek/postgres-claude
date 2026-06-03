# `src/backend/utils/adt/rangetypes.c`

- **File:** `source/src/backend/utils/adt/rangetypes.c` (3187 lines)
- **Last verified commit:** `4b0bf0788b066a4ca1d4f959566678e44ec93422` (2026-06-03)

## Purpose

I/O and all primary operators for **range types** (the `int4range`,
`tstzrange`, … family plus user-defined CREATE TYPE … AS RANGE).
On-disk representation is a varlena `RangeType` carrying the element
typid in the header, a flags byte, and the bound values inline.

Functions here implement the SQL surface: `range_in`/`out`/`recv`/
`send`, constructors `range_constructor2`/`3`, accessors (`lower`,
`upper`, `isempty`, `lower_inc`, etc.), set operations (`range_union`,
`range_intersect`, `range_minus`), predicates (`@>`, `<@`, `&&`, `-|-`,
`<<`, `>>`, `&<`, `&>`), and the canonicalization machinery.

## Key functions

### I/O

- `range_in(str, rngtypoid, typmod)` (`:93-140`) —
  **`check_stack_depth()` at `:108`** for recursion when subtype is
  itself a range type (`rangeofrange`-style user types). Cache obtained
  via `get_range_io_data(fcinfo, rngtypoid, IOFunc_input)`
  (`:110`, `:322-372`). Delegates to `range_parse` (defined further
  down) to split into `lbound_str`/`ubound_str` + flags, then calls
  the subtype's input function via `InputFunctionCallSafe`
  (`:118-126`). Finally `make_range` validates and canonicalizes
  (`:136-137`). [verified-by-code]
- `range_out(range)` (`:142-173`) — `check_stack_depth()` at `:155`.
  `range_deserialize` → per-bound subtype `OutputFunctionCall` →
  `range_deparse` joins into the `[lb,ub)` style text.
  [verified-by-code]
- `range_recv(buf, rngtypoid, typmod)` (`:182-264`) —
  `check_stack_depth()` at `:194`. Reads flags byte, masks to known
  bits (`:206-210`), then per-bound `(uint32 len, bytes)` consumed by
  `ReceiveFunctionCall`. `make_range(typcache, &lower, &upper,
  EMPTY_FLAG, NULL)` finalizes — note `escontext = NULL`, so errors
  HARD-throw from binary input. [verified-by-code]
- `range_send(range)` (`:266-313`) — `check_stack_depth()` at `:277`.
  Reverse of `range_recv`. [verified-by-code]

### Constructors

- `range_constructor2(arg1, arg2)` (`:382-408`) — `[arg1, arg2)`,
  treating SQL NULLs as ±infinity. Calls `make_range` with
  `escontext=NULL`. [verified-by-code]
- `range_constructor3(arg1, arg2, flags_text)` (`:411+`) — accepts
  a textual `(`/`[`/`)`/`]` flags string.

### Bound math + canonicalization

- `range_get_flags`, `range_set_contain_empty`, etc., are inlined
  bit-twiddling over the flags byte.
- `make_range(typcache, lower, upper, empty, escontext)` (defined
  further down, `:1500+`) — validates that lower ≤ upper unless EMPTY,
  invokes the type's `rng_canonical_finfo` if defined (e.g. integer
  ranges normalize `[1,5]` to `[1,6)`). Serializes via
  `range_serialize`. This is the central correctness chokepoint.
- `range_serialize`/`range_deserialize` — the on-disk varlena layout
  marshallers, used by every operator.
- `range_cmp_bounds` (`:1700+`) — three-way bound comparison
  respecting infinity flags, inclusivity, and lower-vs-upper-bound
  sense.

## Phase D notes

- **Recursion depth**: all four I/O entry points (`in`/`out`/`recv`/
  `send`) call `check_stack_depth()` precisely because subtype-is-range
  is legal. Recursion depth is bounded by `max_stack_depth` GUC.
  [verified-by-code]
- **Bound validation**: `make_range` is the single point that enforces
  `lower ≤ upper` — every constructor and parser eventually funnels
  through it. Empty ranges bypass this check (`range_serialize`
  encodes empty via the flag byte without bound values).
  [verified-by-code]
- **`range_recv` does NOT canonicalize via `escontext`**: it passes
  `NULL`, so any validation failure in `make_range` becomes a hard
  ERROR rather than a soft error. Acceptable for binary protocol but
  worth noting if binary input becomes COPY-soft-error-eligible in
  future. [verified-by-code]
- **Flag-byte masking** at `range_recv:206-210` is critical — drops
  `RANGE_xB_NULL` and any unknown bits before downstream consumers
  rely on them. Without this mask, a crafted flag byte could trip
  asserts in `range_serialize`. [from-comment]

## Potential issues

- [ISSUE-trust-boundary: `range_recv` discards `escontext` even when
  available; soft-error eligibility for binary range input is not
  supported (info)]
- [ISSUE-undocumented-invariant: `range_parse` (text path) must
  produce flags consistent with what `make_range` expects — split
  across functions, no shared assertion (low)]
- [ISSUE-correctness: per-type `rng_canonical_finfo` runs user code
  inside the range-input fmgr call chain; a buggy canonicalization
  function on a user-defined range type could mis-form storage but
  bounded by `make_range`'s post-canonical sanity (info)]

## Cross-references

- `source/src/include/utils/rangetypes.h` — `RangeType`, `RangeBound`,
  flag bits.
- `source/src/backend/utils/cache/typcache.c` — `TypeCacheEntry.rngtype`,
  `rng_canonical_finfo`, `rng_subdiff_finfo`.
- `source/src/backend/utils/adt/multirangetypes.c` — consumes
  `make_range`/`range_serialize` from here.
- `source/src/backend/utils/adt/rangetypes_gist.c`,
  `source/src/backend/utils/adt/rangetypes_spgist.c` — index opclasses
  on top of these primitives.

## Confidence tag tally
- `[verified-by-code]` × 9
- `[from-comment]` × 1
