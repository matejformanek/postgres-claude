# detoast.h

- **Source path:** `source/src/include/access/detoast.h`
- **Last verified commit:** `ef6a95c7c64`
- **Companion files:** `detoast.c`, `toast_internals.h`, `varatt.h`.

## Purpose

Declares the public TOAST read API plus the `VARATT_EXTERNAL_GET_POINTER` macro for unaligned-safe access to `varatt_external` pointers embedded in tuples. [from-comment, detoast.h:1-26]

## Key macro

- **`VARATT_EXTERNAL_GET_POINTER(toast_pointer, attr)`** (22) — `memcpy`-via-cast workaround for old GCC versions that assumed the embedded varlena was aligned. Always copy through `varattrib_1b_e *` to be safe. [from-comment, detoast.h:15-26]

## Public surface

- `detoast_external_attr(varlena *attr)` — Reassemble EXTERNAL pointer into inline (possibly still compressed).
- `detoast_attr(varlena *attr)` — Full detoast: inline AND decompressed.
- `detoast_attr_slice(varlena *attr, int32 sliceoffset, int32 slicelength)` — Slice fetch.
- `toast_raw_datum_size(Datum value)`, `toast_datum_size(Datum value)` — Size queries that don't actually fetch.

## Cross-references

- Behaviour: `knowledge/files/src/backend/access/common/detoast.c.md`.

## Confidence tag tally
`[verified-by-code]=1 [from-comment]=2 [from-readme]=0 [inferred]=0 [unverified]=0`

## Synthesized by
<!-- backlinks:auto -->
- [idioms/heap-tuple-decompression-pattern.md](../../../../idioms/heap-tuple-decompression-pattern.md)
