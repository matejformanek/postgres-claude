# `src/include/utils/sortsupport.h`

- **File:** `source/src/include/utils/sortsupport.h` (286 lines)
- **Last verified commit:** `ef6a95c7c64de07dff4dd1f1da88ffae7b086ef3` (2026-06-01)

## Purpose

Defines the **SortSupport** framework: a reduced-overhead alternative to
the traditional fmgr-routed `cmp(x,y)` BTORDER_PROC. Opclass authors that
want their datatype to sort fast can publish a `BTSORTSUPPORT_PROC`
support function whose job is to fill in a `SortSupportData` struct with
direct C function pointers and, optionally, abbreviated-key callbacks.
(`sortsupport.h:6-29` [from-comment])

## The SortSupportData contract (`:60-192`)

Three groups of fields:

**Set by caller, immutable across calls:**
- `ssup_cxt` (`:66`) — memory context for opclass allocations.
- `ssup_collation` (`:67`) — used by collation-sensitive comparators
  (e.g. text). Available before `BTSORTSUPPORT` is invoked so the
  opclass can choose comparators per collation.

**Set by caller, mutable:**
- `ssup_reverse` (`:74`), `ssup_nulls_first` (`:75`) — sort direction
  knobs; honored by `ApplySortComparator` (not the opclass).
- `ssup_attno` (`:81`) — column number; caller-private.
- `abbreviate` (`:155`) — "abbreviation may apply" hint — typically only
  the leading sort column. **One-way one-time signal**: the opclass
  decides yes/no by either setting `abbrev_converter` (yes) or leaving
  it NULL (no).

**Set by opclass (in `BTSORTSUPPORT_PROC`):**
- `comparator` (`:106`) — **required**. Either the authoritative
  comparator, or (if abbreviation is engaged) the cheap
  abbreviation comparator. Convention: returns `<0/0/>0`; inputs
  guaranteed non-null. The `ssup` pointer is available to the
  comparator for collation / extra state.
- `abbrev_converter` (`:172`) — non-NULL signals "abbreviation in
  play"; converts a Datum to a pass-by-value abbreviated key proxy.
- `abbrev_abort` (`:182`) — periodically called by core; opclass-defined
  cost model that can give up on abbreviation.
- `abbrev_full_comparator` (`:191`) — authoritative comparator used to
  break abbreviation ties (or installed back as `comparator` if core
  decides to abandon abbreviation).
- `ssup_extra` (`:87`) — opclass scratch; allocated in `ssup_cxt`.

## Abbreviation contract (the subtle bits)

> "Returning zero from the alternative comparator does not indicate
> equality, as with a conventional support routine 1, though — it
> indicates that it wasn't possible to determine how the two abbreviated
> values compared. A proper comparison, using `abbrev_full_comparator` /
> `ApplySortAbbrevFullComparator()` is therefore required."
> (`sortsupport.h:126-131` [from-comment])

The opclass must consider final cardinality of the abbreviation space
when choosing an encoding (`:138-142` [from-comment]). All four
abbreviation callbacks are mandatory together — partial implementations
are forbidden.

## Apply* inline helpers (`:199-268`)

- **`ApplySortComparator(d1, n1, d2, n2, ssup)`** (`:199-230`) — the
  hot-path inline. Handles NULL ordering up-front using `ssup_nulls_first`,
  dispatches to `ssup->comparator`, then conditionally
  `INVERT_COMPARE_RESULT` if `ssup_reverse`. **This is the single most
  important function in the sort hot path** — `comparetup_heap` and
  friends call it for every pair.
- **`ApplySortAbbrevFullComparator(...)`** (`:237-268`) — same shape but
  dispatches to `abbrev_full_comparator`. Used by tiebreak paths.

## Specialized datum comparators

Three exported comparator functions (`:275-277`):
- `ssup_datum_unsigned_cmp` — unsigned Datum compare.
- `ssup_datum_signed_cmp` — signed Datum compare.
- `ssup_datum_int32_cmp` — int32 compare (extracts lower 32 bits).

These exist because **`tuplesort.c`'s `tuplesort_sort_memtuples`
recognizes these specific function pointers and switches to radix sort**
(`tuplesort.c:3011-3021`). Datatypes that install one of these as their
`comparator` (typically as the abbreviated comparator) get radix-sort
acceleration automatically.

## Setup entry points (in `sortsupport.c`)

- `PrepareSortSupportComparisonShim(cmpFunc, ssup)` — wrap old-style cmp.
- `PrepareSortSupportFromOrderingOp(orderingOp, ssup)` — from a `<`/`>`
  operator OID.
- `PrepareSortSupportFromIndexRel(indexRel, reverse, ssup)` — from an
  open btree index relcache entry.
- `PrepareSortSupportFromGistIndexRel(indexRel, ssup)` — GiST-specific.

## Cross-references

- `source/src/backend/utils/sort/sortsupport.c` — implementation of the
  `Prepare*` setup helpers.
- `source/src/backend/utils/sort/tuplesort.c` — primary consumer (calls
  `ApplySortComparator`, recognizes `ssup_datum_*_cmp` for radix sort).
- Opclass BTSORTSUPPORT examples:
  - `numeric_sortsupport` (`utils/adt/numeric.c`),
  - `varstrfastcmp_*` family in `utils/adt/varlena.c`,
  - `bttextsortsupport` (`utils/adt/varlena.c`),
  - `btint{2,4,8}sortsupport`, `btoidsortsupport`,
  - `date_sortsupport`, `timestamp_sortsupport`.
- `access/nbtree.h` defines `BTSORTSUPPORT_PROC = 2`; `access/gist.h`
  defines `GIST_SORTSUPPORT_PROC = 11`.

## Confidence tag tally

- `[verified-by-code]` × ~5
- `[from-comment]` × ~6
