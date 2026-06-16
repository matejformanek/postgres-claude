# `src/backend/utils/adt/datum.c`

- **File:** `source/src/backend/utils/adt/datum.c` (594 lines)
- **Last verified commit:** `4b0bf0788b066a4ca1d4f959566678e44ec93422` (2026-06-03)

## Purpose

Generic `Datum` manipulation: size, copy, transfer between contexts,
binary equality, image-hash, and the (de)serialization used by parallel
workers / shm queue traffic. (`datum.c:1-41` [from-comment])

The header comment encodes the **typByVal × typLen layout matrix** that
all later PG code relies on:

| typByVal | typLen | meaning |
|----------|--------|---------|
| true     | 1..sizeof(Datum) | value inline in Datum |
| false    | > 0 | pointer to fixed-length byte stream |
| false    | -1 | pointer to varlena |
| false    | -2 | pointer to cstring |

(`:18-35` [verified-by-code])

## Type role

Generic infrastructure — not bound to any one SQL type. Used by tuple
deforming, sorts, hashing, parallel exec.

## Key functions

- `datumGetSize(value, typByVal, typLen)` (`:65`) — uniform size lookup;
  rejects NULL pointers for non-byval cases (`:87-91, :99-103`).
- `datumCopy(value, typByVal, typLen)` (`:132`) — palloc into current
  context. **Flattens expanded objects** via `EOH_flatten_into` (`:143-154`)
  so callers always get a single pfree-able chunk.
- `datumTransfer(value, typByVal, typLen)` (`:194`) — like `datumCopy` but
  if the source is a R/W expanded-object pointer, just **reparents** the
  expanded object's context (no flatten). Returns the canonical R/W ptr.
- `datumIsEqual(v1, v2, typByVal, typLen)` (`:223`) — bytewise equality.
  Header comment "XXX!" (`:209-219`) explicitly warns: this is bitwise,
  not semantic; do NOT use on TOASTed datums.
- `datum_image_eq` (`:271`) — bytewise equality with TOAST-aware varlena
  handling: detoasts both sides only if lengths match (`:303-318`); used
  by btree `equalimage`/deduplication path.
- `datum_image_hash` (`:358`) — hash of post-detoast payload; companion
  to `datum_image_eq`.
- `btequalimage` (`:433`) — unconditionally returns true. Generic
  support-function-4 entry for btree opclasses that opt into
  deduplication. (`:417-430` [from-comment])
- `datumEstimateSpace` / `datumSerialize` / `datumRestore` (`:450`, `:497`,
  `:559`) — the parallel-worker / shm-queue serialization protocol. Header
  word: `-2` = NULL, `-1` = pass-by-value (sizeof(Datum) follows),
  positive = byte count.

## Phase D notes

- **Expanded-Datum lifecycle is the load-bearing concern.** `datumCopy`
  always flattens; `datumTransfer` reparents only if the input is a R/W
  pointer (`VARATT_IS_EXTERNAL_EXPANDED_RW`, `:196-198`). A code path that
  *thinks* it's transferring a R/W pointer but is actually holding an R/O
  pointer would silently flatten (correct but slower) — no correctness
  issue. [verified-by-code]
- `datumSerialize` flattens expanded objects too (`:508-513, :527-541`) —
  necessary because the receiving worker has no access to the sender's
  process memory. TOAST pointers, by contrast, are sent verbatim because
  both processes share the database (`:478-482` [from-comment]).
- `datumGetSize` performs a `MAXALIGN`-free length read on cstrings via
  `strlen` (`:104`) — a deliberately oversized cstring **doesn't** cause
  OOB read here (strlen finds the terminator), but extremely long cstrings
  can stall the loop. [inferred — not exploitable but worth noting]
- `datumIsEqual` for pass-by-val types compares **the whole Datum**
  (`:235`), not just the low-typLen bytes, on the assumption that "any
  given datatype is consistent about how it fills extraneous bits"
  (`:229-234` [from-comment]). PG_RETURN_INT16 zero-pads via Int16GetDatum
  — but if a buggy type stored uninitialized high bits, two semantically
  equal values would compare unequal here. `datum_image_eq` explicitly
  re-canonicalizes (`:281-292`) to dodge this; `datumIsEqual` does not.

## Potential issues

- `[ISSUE-undocumented-invariant: pass-by-val types MUST zero-pad the high
  bits of Datum or datumIsEqual will report unequal for equal values
  (:229-234). (medium)]` — documented at this site but easy to violate
  in a new type.
- `[ISSUE-correctness: datumGetSize on a deliberately-very-long cstring
  walks the full string for strlen; could be slow with a malicious caller.
  (low) — but caller controls the pointer, not user input directly.]`
- `[ISSUE-dead-code: btequalimage takes Oid opcintype only via NOT_USED
  branch (:436-437). (info) — comment notes future use.]`

## Cross-references

- `source/src/include/utils/datum.h` — declarations.
- `source/src/include/utils/expandeddatum.h` — `EOH_*` macros, R/W vs R/O
  expanded-object pointer conventions.
- `source/src/backend/access/common/heaptuple.c` — uses `datumCopy` in
  detoasting / detuple paths.
- `source/src/backend/executor/execParallel.c` — `datumSerialize` /
  `datumRestore` consumer.

<!-- issues:auto:begin -->
- [Issue register — `utils-adt`](../../../../../issues/utils-adt.md)
<!-- issues:auto:end -->

## Confidence tag tally

- `[verified-by-code]` × 4
- `[from-comment]` × 4
- `[inferred]` × 1
