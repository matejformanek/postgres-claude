# utils/array.h — Postgres array varlena format + expanded arrays

Source: `source/src/include/utils/array.h` (481 lines)
Source pin: `4b0bf0788b066a4ca1d4f959566678e44ec93422`

## Role

Declares the on-disk ArrayType varlena format, the expanded (in-memory) array representation, fmgr macros, and the public API for `arrayfuncs.c` / `arrayutils.c` / `array_expanded.c`. Defines `MAXDIM` (the hard upper bound on array dimensions) and `MaxArraySize` (the per-array element count cap).

## Public API / on-disk format

The header comment is the canonical spec for ArrayType layout:

```
<vl_len_>   - standard varlena header word
<ndim>      - number of dimensions
<dataoffset> - 0 if no null bitmap, else offset to data
<elemtype>  - element type OID
<dimensions> - int[ndim] axis lengths
<lower bnds> - int[ndim] lower bounds
<null bitmap> - optional, LSB-first, 1 = non-null
<actual data> - MAXALIGN'd, element-type-aligned, row-major
```

`array.h:6-29` [from-comment]. ArrayType struct itself only declares the *fixed* header (`array.h:92-98`); the dimensions, lbounds, null bitmap, and data area are flexible-array tail computed via `ARR_DIMS`/`ARR_LBOUND`/`ARR_NULLBITMAP`/`ARR_DATA_PTR` macros (`array.h:289-323`).

## Invariants

- **INV-array-MAXDIM=6** [verified-by-code, `array.h:75`]: `#define MAXDIM 6`. This is the *enforced* upper bound on `ndim` in every `array_recv`/`array_in` path (caller must check).
- **INV-array-MaxArraySize** [verified-by-code, `array.h:78-82`]: total elements ≤ `MaxAllocSize / sizeof(Datum)` (≈256 M elements on 64-bit) so `palloc(nelems * sizeof(Datum))` cannot overflow.
- **INV-array-no-toasted-elements** [from-comment, `array.h:30-34`]: individual elements of toastable types MUST NOT themselves be toasted (out-of-line); the whole array is compressed/toasted as one unit. Sites that build ArrayTypes from raw Datums must detoast first.
- **INV-array-row-major** [from-comment, `array.h:26-28`]: last subscript varies most rapidly; element alignment is per-type-specified.
- **INV-array-nullbitmap-encoding** [from-comment, `array.h:18-24`]: bitmap follows tuple-null convention — 1 means *non-null*, LSB first; absent bitmap ⇒ `dataoffset == 0`.
- **INV-array-EA_MAGIC** [verified-by-code, `array.h:113`]: `EA_MAGIC = 689375833` debug crosscheck on `ExpandedArrayHeader`.
- **INV-oidvector-int2vector-1D-no-nulls** [from-comment, `array.h:37-39`]: OIDVECTOR / INT2VECTOR are storage-compatible with array headers but are 1-D, no-null, never toasted. Code paths that walk these as generic arrays must enforce this.

## Notable internals

- `ExpandedArrayHeader` (`array.h:115-168`) holds an optional flat `fvalue` plus a deconstructed `dvalues`/`dnulls` representation. For pass-by-ref elements, `dvalues[i]` may point either into the flat data or into separately-palloc'd chunks; `fstartptr`/`fendptr` (`array.h:165-167`) are the discriminator.
- `AnyArrayType` union (`array.h:177-181`): caller should always cast to `ArrayType` not reference `.flt` — comment explicitly notes UBSan complains about 8-byte-aligned union accessed via 4-byte-aligned ArrayType pointer.
- `array_get_element` / `array_set_element` / `array_get_slice` / `array_set_slice` (`array.h:363-377`) are the SQL subscript ops; pass `arraytyplen` separately for fixed-length-array vs varlena dispatch.
- `ArrayGetNItemsSafe` / `ArrayCheckBoundsSafe` (`array.h:459-463`) are the soft-error counterparts; A7's lessons recommend these on any recv/parse path.

## Trust-boundary / Phase-D surface

- **array_recv input validation** [inferred from format]: `array_recv` in `arrayfuncs.c` consumes the on-wire `ndim`/`dataoffset`/`elemtype`/`dimensions`/`lbound`/`nullbitmap`/data. The header docs the format but does NOT call out that callers must:
  - bound-check `ndim ∈ [0, MAXDIM]`
  - validate `dataoffset == 0` iff bitmap absent
  - reject self-contradictory `dataoffset` (must equal `ARR_OVERHEAD_WITHNULLS(ndims, nitems)`)
  - prevent integer overflow in `nitems = ∏ dims[i]` (`ArrayGetNItems`)
  - reject toasted elements in the data area (per INV-array-no-toasted-elements)
- **`MAXDIM=6` is arbitrary** (`array.h:74`) — increasing it would require auditing every `int dims[MAXDIM]` and `int lbs[MAXDIM]` stack array (e.g. `ArrayBuildStateArr.dims`/`.lbs` at `array.h:215-216`). [from-comment]

## Cross-refs

- `source/src/backend/utils/adt/arrayfuncs.c` — implementations + `array_recv` (Phase D anchor).
- `source/src/backend/utils/adt/array_expanded.c` — expanded TOAST machinery.
- `varatt.h` — `VARATT_IS_EXPANDED_HEADER` macro used at `array.h:329` for the AnyArrayType dispatch.
- `knowledge/files/src/include/utils/arrayaccess.md` — companion (element iteration).
- `knowledge/files/src/include/utils/expandeddatum.md` — base of `ExpandedObjectHeader`.

## Issues

- `[ISSUE-DOC: header silent on array_recv DoS surface (low)]` — Header documents the on-disk format but does not mention that `array_recv` must defensively validate every header field. Cross-link from this header to `arrayfuncs.c:array_recv` would close A7's category at the API level.
- `[ISSUE-INVARIANT: MAXDIM=6 truly arbitrary (info)]` — `array.h:74` comment says "arbitrary limit". Multiple stack arrays (e.g. ArrayBuildStateArr) hardcode it; an invariant doc tag would help.
