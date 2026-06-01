# `src/backend/utils/mmgr/memdebug.c`

- **File:** `source/src/backend/utils/mmgr/memdebug.c` (93 lines)
- **Last verified commit:** `ef6a95c7c64de07dff4dd1f1da88ffae7b086ef3` (2026-06-01)

## Purpose

Tiny support file for the debug-build memory-context features that
`aset.c`, `generation.c`, `slab.c`, `bump.c`, and `alignedalloc.c`
sprinkle through their code. Only one function is actually compiled
(under `RANDOMIZE_ALLOCATED_MEMORY`); the rest of the file is doc.
The accompanying header `utils/memdebug.h` defines the actual macros
(`wipe_mem`, `set_sentinel`, `sentinel_ok`, the
`VALGRIND_MAKE_MEM_*` stubs when Valgrind isn't compiled in).

## Top-of-file comment (verbatim)

```
About CLOBBER_FREED_MEMORY:

If this symbol is defined, all freed memory is overwritten with 0x7F's.
This is useful for catching places that reference already-freed memory.

About MEMORY_CONTEXT_CHECKING:

Since we usually round request sizes up to the next power of 2, there
is often some unused space immediately after a requested data area.
... the MEMORY_CONTEXT_CHECKING option stores 0x7E just beyond
the requested space whenever the request is less than the actual chunk
size, and verifies that the byte is undamaged when the chunk is freed.

About USE_VALGRIND and Valgrind client requests:

... When running under Valgrind, we want a NOACCESS memory region both
before and after the allocation.  The chunk header is tempting as the
preceding region, but mcxt.c expects to be able to examine the standard
chunk header fields.  Therefore, we use, when available, the
requested_size field and any subsequent padding.  requested_size is
made NOACCESS before returning a chunk pointer to a caller.  However,
to reduce client request traffic, it is kept DEFINED in chunks on the
free list.
```
(`memdebug.c:14-52` [from-comment])

## Public surface

- `randomize_mem(char *ptr, size_t size)` (`:74`) — only under
  `RANDOMIZE_ALLOCATED_MEMORY`. Fills the region with a fixed
  pseudorandom byte sequence (modulo 251, a prime) so two
  same-sized palloc's start out with different content.

The macros are in the header:
- `CLOBBER_FREED_MEMORY` → `wipe_mem(p, n)` overwrites with `0x7F`.
- `MEMORY_CONTEXT_CHECKING` → `set_sentinel(p, off)` writes
  `0x7E` at `p[off]`, `sentinel_ok(p, off)` verifies it.
- `USE_VALGRIND` → `VALGRIND_*` real macros; otherwise stubbed
  to no-ops.

## Key invariants

- **Sentinel byte is `0x7E`** (NOT `0x7F` — the latter is the
  clobber-freed-memory pattern). They're picked to be visually
  distinct in hex dumps (`:14-30` [from-comment]).
- **Sentinel only written when `requested_size < chunk_size`**
  (i.e. when the allocator rounded up). Exact-fit chunks have no
  sentinel and write-past-end of those is undetected under
  `MEMORY_CONTEXT_CHECKING` (this is the trade-off documented in
  `aset.c:1039-1043, 1063-1066` [from-comment]).
- **`requested_size` field** (only present in checking builds, in the
  `MemoryChunk` header) doubles as the Valgrind NOACCESS region
  before the chunk — see header comment `:38-44` [from-comment].
- **Random byte sequence is global state** across the backend
  (`save_ctr`) — sequence wraps at 251 so it's not deterministic
  per allocation but is reproducible per backend run. Intent: catch
  callers that assume zero-init of palloc-not-palloc0 chunks.

## Functions of note

1. **`randomize_mem` (`:74-91`)** — sets the region UNDEFINED for
   Valgrind, fills with `(save_ctr++) % 251 + 1` byte sequence,
   then sets UNDEFINED again so Valgrind keeps flagging
   reads-before-init. Called by every allocator's "small chunk"
   path under `RANDOMIZE_ALLOCATED_MEMORY` (e.g. `aset.c:1067-1070`,
   `bump.c:427-430`, `generation.c:413-416`).

## Cross-references

- `source/src/include/utils/memdebug.h` — the actual macro
  definitions (not read in this pass, but referenced by every
  allocator file).
- All five allocator files (`aset.c`, `generation.c`, `slab.c`,
  `bump.c`, `alignedalloc.c`) include `utils/memdebug.h` and call
  `set_sentinel`/`sentinel_ok`/`wipe_mem`/`randomize_mem` under the
  three compile-time flags.

## Open questions

None — file is small and documentation-heavy.

## Confidence tag tally

- `[verified-by-code]` × 3
- `[from-comment]` × 5

## Synthesized by
<!-- backlinks:auto -->
- [subsystems/utils-mmgr.md](../../../../../subsystems/utils-mmgr.md)
