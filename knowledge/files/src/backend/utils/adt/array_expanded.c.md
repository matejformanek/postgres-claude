# `src/backend/utils/adt/array_expanded.c`

- **File:** `source/src/backend/utils/adt/array_expanded.c` (455 lines)
- **Last verified commit:** `4b0bf0788b066a4ca1d4f959566678e44ec93422` (2026-06-03)

## Purpose

The **expanded-object** Datum representation for `ArrayType`. An expanded
array lives in its own `AllocSetContext`, holds either a flat copy of
the original `ArrayType` or a deconstructed `Datum[]`/`bool[]` pair (or
both), and exposes an `ExpandedObjectMethods` table so it can be flattened
back into varlena form on demand. Major perf win for `plpgsql` array
variables and `array_set_element` chains that would otherwise rewrite
the whole varlena per assignment.

## Key functions

- `expand_array(arraydatum, parentcxt, metacache)` (`:50-179`) —
  the entry point. Always allocates a per-object `AllocSetContext`
  (`:64-66`, `ALLOCSET_START_SMALL_SIZES`) as a child of `parentcxt`.
  Fast path: if source is already an expanded array AND elements are
  pass-by-value AND it has a `dvalues[]` rep, just `memcpy` the dvalues
  via `copy_byval_expanded_array` (`:102-107`, `:184-227`). Otherwise
  takes a flat copy via `DatumGetArrayTypePCopy` (`:131`) within the
  new context. Returns a R/W EOH datum. [verified-by-code]
- `EA_get_flat_size(eohptr)` (`:233-289`) — required EOH callback. If
  flat representation present, returns `ARR_SIZE(fvalue)`. Otherwise
  walks `dvalues[]`, accumulating `att_addlength_datum` +
  `att_nominal_alignby`, plus the right overhead constant
  (`ARR_OVERHEAD_WITHNULLS` vs `ARR_OVERHEAD_NONULLS`). Each iteration
  checks `AllocSizeIsValid(nbytes)` and ereports on overflow
  (`:273-277`). Result cached in `eah->flat_size`. [verified-by-code]
- `EA_flatten_into(eohptr, result, allocated_size)` (`:295-340`) —
  materializes the expanded form into a destination buffer.
  Zero-fills first (`:327`) to ensure alignment padding is canonical,
  then sets varlena header + `ARR_DIMS`/`ARR_LBOUND` + element data via
  `CopyArrayEls`. [verified-by-code]
- `DatumGetExpandedArray(d)` (`:354-368`) /
  `DatumGetExpandedArrayX(d, metacache)` (`:374-396`) — if input is
  already an EXPANDED-RW pointer, returns it directly (caller is
  warned at `:351` that mutations must be safe); else calls
  `expand_array` in `CurrentMemoryContext`. [verified-by-code]
- `DatumGetAnyArrayP(d)` (`:403-419`) — return either an expanded EOH
  pointer or a PG_DETOAST result without flattening expanded arrays.
  Result must NOT be mutated (`:402` comment). [from-comment]
- `deconstruct_expanded_array(eah)` (`:426-455`) — switches into the
  EOH context, builds `dvalues[]`/`dnulls[]` from `fvalue` via
  `deconstruct_array`. Only updates header pointers after success so a
  partial failure just leaks within the object context (`:443-447`
  [from-comment]). [verified-by-code]

## Phase D notes

- **Memory-context discipline** is the load-bearing invariant: every
  allocation belongs to `eah->hdr.eoh_context`. Forgetting to switch
  contexts on a new field (e.g. in a future `deconstruct_*` variant)
  would create a dangling pointer when the EOH is freed.
- `EA_MAGIC` (defined in `utils/array.h`) gets asserted in every entry
  point — sanity-check against type confusion between EOH pointer
  flavors. [verified-by-code]
- `expand_array` "may leak" if `DatumGetArrayTypePCopy` performs TOAST
  detoast then errors mid-way (`:124-129` [from-comment]) — bounded by
  the per-object context, which is reaped on EOH free.

## Potential issues

- [ISSUE-undocumented-invariant: the "caller must ensure mutations are
  safe" warning at `:350-352` is the only protection against corrupting
  shared expanded arrays passed across plpgsql call boundaries; not
  enforced (maybe)]
- [ISSUE-correctness: `EA_get_flat_size` overflow check
  (`AllocSizeIsValid`) is per-element rather than at end — fine in
  practice, but a malicious sequence of tiny elements summing to
  >1 GB would trip on the element that pushes it over (info)]

## Cross-references

- `source/src/include/utils/array.h` — `ExpandedArrayHeader`, `EA_MAGIC`,
  `ARR_*` macros, `ArrayMetaState`.
- `source/src/include/utils/expandeddatum.h` — EOH framework.
- `source/src/backend/utils/adt/arrayfuncs.c` — `deconstruct_array`,
  `CopyArrayEls`, `construct_*`.

<!-- issues:auto:begin -->
- [Issue register — `utils-adt`](../../../../../issues/utils-adt.md)
<!-- issues:auto:end -->

## Confidence tag tally
- `[verified-by-code]` × 7
- `[from-comment]` × 3
