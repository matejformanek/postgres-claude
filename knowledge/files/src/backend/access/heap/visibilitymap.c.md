# visibilitymap.c

- **Source path:** `source/src/backend/access/heap/visibilitymap.c`
- **Lines:** 630
- **Last verified commit:** `ef6a95c7c64`
- **Companion files:** `visibilitymap.h`, `visibilitymapdefs.h`, callers in `heapam.c`, `pruneheap.c`, `vacuumlazy.c`

## Purpose

Implements the visibility map fork: a 2-bits-per-heap-page bitmap (`ALL_VISIBLE`, `ALL_FROZEN`) stored as a separate relation fork. Provides pin/clear/set/get operations and truncation helpers. The top-of-file comment (~80 lines) is the authoritative discussion of VM crash-safety and the "examine page → pin VM → re-lock" race window. [from-comment, visibilitymap.c:1-95]

## Top-of-file comment
> Long (95-line) block explaining: the conservative-hint semantics ("set bit is authoritative, cleared bit is unknown"), the implicit dependency between `PD_ALL_VISIBLE` on the heap page and the VM bit, the crash-recovery rules (clear must replay before heap page hits disk; set must replay if VM page hit disk first), and the LOCKING section that documents the unlock-pin-relock race window. [from-comment, visibilitymap.c:1-95]

## Public surface (non-static functions)

- `visibilitymap_clear` (line 151) — clear specified bits for one heap page.
- `visibilitymap_pin` (line 204) — pin (extending the fork if needed) the VM page that maps `heapBlk`.
- `visibilitymap_pin_ok` (line 228) — does an already-pinned vmbuf cover heapBlk?
- `visibilitymap_set` (line 255) — set bits; caller is responsible for the WAL record of the underlying op.
- `visibilitymap_get_status` (line 319) — read both bits.
- `visibilitymap_count` (line 367) — count set bits across the whole VM (for pg_class stats).
- `visibilitymap_prepare_truncate` (line 421) — handle heap truncation: zero out the trailing partial byte if needed, return the new VM block count.
- `visibilitymap_truncation_length` (line 524) — compute VM block count for an N-block heap.

## Key types / structs

None defined here; the bit constants `VISIBILITYMAP_ALL_VISIBLE = 0x01` / `VISIBILITYMAP_ALL_FROZEN = 0x02` live in `visibilitymapdefs.h`. [verified-by-code, visibilitymap.c includes "access/visibilitymapdefs.h"]

## Key invariants and locking

- `ALL_FROZEN` may be set only if `ALL_VISIBLE` is also set. [from-comment, visibilitymap.c:760-762 in header]
- VM bit changes are NOT separately WAL-logged. Synchronisation between heap page and VM bit relies on the WAL record of the heap operation. [from-comment, visibilitymap.c:767-771]
- `visibilitymap_set` updates VM page LSN to the LSN of the just-emitted heap WAL record, so crash recovery reapplies the bit only if the heap modification is also reapplied. [inferred, standard PG pattern]
- The "race window": if a heap modifier examines the page without lock, sees `PD_ALL_VISIBLE` unset, and decides not to pin a VM buffer, it must re-check after locking — because another backend may have set PD_ALL_VISIBLE in between. [from-comment, visibilitymap.c:797-812]

## Functions of note (≥3)

- `visibilitymap_set` (visibilitymap.c:255) — Locks VM buffer in exclusive mode, OR-in the flag bits in the target byte, sets page LSN to the heap-WAL-record LSN passed via the caller, marks buffer dirty. Asserts `flags & VISIBILITYMAP_VALID_BITS == flags`. [verified-by-code]
- `vm_readbuf` (visibilitymap.c:536, static) — Reads the requested VM block; if `extend=true`, calls `vm_extend` when block is beyond current EOF. Uses smgrnblocks + RBM_ZERO_ON_ERROR.
- `vm_extend` (visibilitymap.c:610, static) — Extends the VM fork by repeatedly writing zero-filled blocks. Holds the relation extension lock.
- `visibilitymap_prepare_truncate` (visibilitymap.c:421) — Called from heap truncation paths. If the truncation falls in the middle of a VM byte, zero out only the bits past the new EOF; otherwise smgrtruncate the VM fork.

## Cross-references

- Callers (`grep '"access/visibilitymap.h"' source/src/backend/`): `heapam.c`, `heapam_handler.c`, `heapam_xlog.c`, `hio.c`, `pruneheap.c`, `vacuumlazy.c`, plus `commands/vacuum.c` and `storage/freespace/indexfsm.c` indirectly. [verified-by-code]
- Outbound: bufmgr (`ReadBufferExtended`, `LockBuffer`, `MarkBufferDirty`), smgr (`smgrnblocks`, `smgrextend`, `smgrtruncate`).

## Open questions

- Whether `vm_extend` still holds the relation extension lock for the full extension or has been refactored to the new bulk-extend pattern in heap proper. [unverified]
- The exact rule for when `visibilitymap_set` may skip the LSN bump (when the heap operation is no-WAL, e.g. unlogged table). [unverified]

## Confidence tag tally
`[verified-by-code]=8 [from-comment]=5 [from-readme]=0 [inferred]=1 [unverified]=2`

## Synthesized by
<!-- backlinks:auto -->
- [subsystems/access-heap.md](../../../../../subsystems/access-heap.md)
- [subsystems/optimizer.md](../../../../../subsystems/optimizer.md)
