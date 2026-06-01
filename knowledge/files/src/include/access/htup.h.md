# htup.h

- **Source path:** `source/src/include/access/htup.h`
- **Lines:** 89
- **Last verified commit:** `ef6a95c7c64`
- **Companion files:** `htup_details.h` (the bit/struct layouts), `heapam.h` (operations), `combocid.c` (Cmin/Cmax helpers)

## Purpose

Lightweight public header that defines the in-memory `HeapTupleData` wrapper (length + self-TID + table OID + pointer to header) and the forward typedef for `HeapTupleHeader` / `MinimalTuple`. The "details" — bit layouts, accessor inlines — are in `htup_details.h`. [from-comment, htup.h:3-12]

## Top-of-file comment
> "POSTGRES heap tuple definitions." (terse; the per-struct comments do the explaining)

## Public surface (every prototype/typedef)
- `typedef struct HeapTupleHeaderData HeapTupleHeaderData;` (forward, definition in `htup_details.h`) [verified-by-code, htup.h:21-23]
- `typedef MinimalTupleData *MinimalTuple;` (forward) [verified-by-code, htup.h:25-27]
- `struct HeapTupleData { uint32 t_len; ItemPointerData t_self; Oid t_tableOid; HeapTupleHeader t_data; }` [verified-by-code, htup.h:62-69]
- `#define HEAPTUPLESIZE MAXALIGN(sizeof(HeapTupleData))` [verified-by-code, htup.h:73]
- `HeapTupleHeaderGetCmin(tup)` / `HeapTupleHeaderGetCmax(tup)` / `HeapTupleHeaderAdjustCmax(...)` — declared here, implemented in `utils/time/combocid.c`. [verified-by-code, htup.h:81-84]
- `HeapTupleGetUpdateXid(tup)` — declared here, implemented in `heapam.c`. [verified-by-code, htup.h:87]
- `#define HeapTupleIsValid(tuple) ((tuple) != NULL)` [verified-by-code, htup.h:78]

## Key types / structs

- `HeapTupleData` (htup.h:62) — The in-memory tuple handle. The top comment enumerates **five** distinct usage modes (pointer-into-buffer, NULL, palloc'd-adjacent, palloc'd-separate, minimal-tuple-overlay) and notes that modes 1, 4, 5 cannot be told apart by inspection. [from-comment, htup.h:30-60]

## Key invariants and locking

- `t_len` is always valid except in the NULL-pointer case. [from-comment, htup.h:57]
- `t_self` and `t_tableOid` are valid only when the tuple is on disk or is a copy thereof; manufactured tuples must be explicitly invalidated. [from-comment, htup.h:58-60]
- When `t_data` points into a shared buffer, the caller MUST be holding a pin on that buffer — but this fact is not encoded in the struct. [from-comment, htup.h:35-37] **This is a major footgun.**

## Functions of note

This header only declares 4 functions; all are in other files. The interesting object is the 5-mode-overloaded struct.

## Cross-references

- Included almost everywhere — `grep -l '"access/htup.h"' source/src/include source/src/backend | wc -l` is large; ~every backend C file that touches tuples ends up here transitively. [inferred]
- Companion `htup_details.h` is what consumers actually need to use the tuples.

## Open questions
None.

## Confidence tag tally
`[verified-by-code]=6 [from-comment]=4 [from-readme]=0 [inferred]=1 [unverified]=0`

## Synthesized by
<!-- backlinks:auto -->
- [data-structures/heap-tuple-layout.md](../../../../data-structures/heap-tuple-layout.md)
- [subsystems/access-heap.md](../../../../subsystems/access-heap.md)
