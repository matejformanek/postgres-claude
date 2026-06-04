# `src/backend/utils/adt/expandeddatum.c`

- **File:** `source/src/backend/utils/adt/expandeddatum.c` (145 lines)
- **Last verified commit:** `4b0bf0788b066a4ca1d4f959566678e44ec93422` (2026-06-03)

## Purpose

Core infrastructure for **expanded Datum representations**: large mutable
in-memory forms of composite/array/record values that PL/pgSQL and the
executor can update without copying the whole varlena each time. This file
holds only the small generic operations; per-type expanded code (e.g.
`expandedrecord.c`, `array_expanded.c`) supplies the actual flatten /
get_flat_size methods. (`expandeddatum.c:1-14` [from-comment])

## Type role

Generic varlena extension. The Datum is a varlena pointer to a
`varattrib_1b_e` external-tag header whose payload encodes a pointer to
the live `ExpandedObjectHeader` plus a R/W vs R/O distinction.

## Key functions

- `DatumGetEOHP(Datum d)` (`:29`) — extract the `ExpandedObjectHeader *`
  from a Datum holding a `VARTAG_EXPANDED_R{W,O}` external pointer. Uses
  `memcpy` because the embedded pointer may not be properly aligned
  (`:25-37` [from-comment]; compare `VARATT_EXTERNAL_GET_POINTER`).
- `EOH_init_header(eohptr, methods, obj_context)` (`:48`) — set up the
  common header + the two canonical R/W / R/O TOAST-style pointers
  embedded in the object itself, so callers can return them directly
  via `EOHPGetRWDatum` / `EOHPGetRODatum`.
- `EOH_get_flat_size` / `EOH_flatten_into` (`:75`, `:81`) — thin
  dispatchers into the per-type method table.
- `MakeExpandedObjectReadOnlyInternal(d)` (`:95`) — if `d` is a R/W
  expanded pointer, return the canonical R/O pointer; otherwise return
  `d` unchanged. The public macro `MakeExpandedObjectReadOnly` wraps this
  with a non-null + non-byval check.
- `TransferExpandedObject(d, new_parent)` (`:118`) — reparent the
  expanded object's MemoryContext to `new_parent`, return the canonical
  R/W pointer. Asserts the input was R/W.
- `DeleteExpandedObject(d)` (`:136`) — `MemoryContextDelete` on the
  object's context. Asserts R/W (you can't delete via an R/O pointer).

## Phase D notes

- **Lifecycle correctness rests on the R/W vs R/O distinction.** A R/W
  expanded pointer is a *single* unique handle whose lifetime matches the
  object's MemoryContext; an R/O pointer can be freely copied. Passing an
  R/W pointer where an R/O is expected (or vice versa) is a memory-safety
  hazard but the public macros (`MakeExpandedObjectReadOnly`,
  `TransferExpandedObject`) enforce the invariants at runtime via Assert.
  [verified-by-code, :100, :123, :141]
- **Memory-context-leak surface:** if a function builds an expanded object
  in a short-lived context and returns the R/W pointer to a longer-lived
  caller without `TransferExpandedObject`, the object is freed when the
  short context is reset — a classic use-after-free. `datumCopy`
  (datum.c) defensively flattens; `datumTransfer` reparents. So this file
  is correctness-critical for cross-context Datum flows.
- **No untrusted input.** All callers are internal C code; expanded
  Datums are not exposed on the wire or in the parser. There is no input
  validation surface here.
- **Alignment trick:** `DatumGetEOHP` uses `memcpy` (`:35`) to read an
  unaligned pointer; this is the standard PG pattern for stored varlena
  pointers. No issue.

## Potential issues

- `[ISSUE-undocumented-invariant: callers MUST distinguish R/W vs R/O
  pointers; only the FIRST R/W pointer is canonical (:88-93,114-117).
  (medium) — captured in nearby comments but easy to violate.]`
- `[ISSUE-correctness: TransferExpandedObject does no defensive null
  check; caller must guarantee non-null (:120). (low)]`
- `[ISSUE-dead-code: none observed. (info)]`

## Cross-references

- `source/src/include/utils/expandeddatum.h` — `ExpandedObjectHeader`,
  `ExpandedObjectMethods`, the `EOHPGet*` accessors, `VARATT_*EXPANDED*`
  macros, `MakeExpandedObjectReadOnly`.
- `source/src/backend/utils/adt/expandedrecord.c` — per-type
  implementation for composite-typed expanded objects.
- `source/src/backend/utils/adt/array_expanded.c` — per-type
  implementation for arrays.
- `source/src/backend/utils/adt/datum.c` — `datumCopy` / `datumTransfer`
  call into here.
- `source/src/include/utils/memutils.h` — `MemoryContextSetParent`,
  `MemoryContextDelete`.

## Confidence tag tally

- `[verified-by-code]` × 3
- `[from-comment]` × 2
