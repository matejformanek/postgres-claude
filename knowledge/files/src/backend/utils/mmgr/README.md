# `src/backend/utils/mmgr/README`

- **File:** `source/src/backend/utils/mmgr/README` (527 lines)
- **Last verified commit:** `ef6a95c7c64de07dff4dd1f1da88ffae7b086ef3` (2026-06-01)

## Purpose

Canonical design document for the memory-context subsystem. Explains *why*
PG uses hierarchical, vtable-dispatched allocators instead of raw `malloc`,
and lays out the contract every context-type implementation must obey.
Most of this content is summarized in `knowledge/idioms/memory-contexts.md`;
this doc is the per-file index into the README's section layout.

## Section map

| README lines | Topic |
|---|---|
| `4-50` | Background — basic operations + why context trees beat per-chunk free [from-readme] |
| `52-75` | palloc vs malloc differences: ERROR on OOM, `palloc(0)` valid, `pfree(NULL)` invalid, `repalloc(NULL,...)` invalid [from-readme] |
| `78-96` | Rules around `CurrentMemoryContext` — keep it short-lived [from-readme] |
| `99-105` | pfree/repalloc are context-of-chunk, not `CurrentMemoryContext` [from-readme] |
| `107-137` | Parent/child trees; `MemoryContextReset` deletes children, vs `ResetOnly` + `ResetChildren` [from-readme] |
| `139-170` | Reset/delete callbacks; reverse-registration, child-before-parent ordering [from-readme] |
| `174-258` | Globally known contexts: Top, Postmaster, Cache, Message, TopTransaction, CurTransaction, Portal, Error [from-readme] |
| `261-274` | Prepared-statement and portal contexts [from-readme] |
| `277-285` | ApplyContext / ApplyMessageContext (logical replication apply worker) [from-readme] |
| `288-368` | Transient contexts inside the executor; per-tuple reset *at start of cycle*; nodeAgg ping-pong; btree/hash leak rules [from-readme] |
| `370-442` | Mechanism: `MemoryContextMethodID` in low 4 bits of the uint64 chunk header; `mcxt_methods[]` vtable lookup; the `MemoryChunk` hdrmask layout (4 + 1 + 30 + 30 bits, top bit shared with bottom block-offset bit since both pointers are MAXALIGNed) [from-readme] |
| `444-468` | AllocSet block-doubling, `initBlockSize`/`maxBlockSize`/`minContextSize`, the keeper-block-on-reset trick [from-readme] |
| `471-499` | Allocator choice table: AllocSet (default), Slab (fixed size), Generation (FIFO), Bump (no header) [from-readme] |
| `501-527` | Memory accounting: per-block (not per-chunk), lazy, recursive walks for inquiry [from-readme] |

## Load-bearing facts to know before reading the implementation files

1. **Every chunk pointer is immediately preceded by a uint64 whose low 4
   bits identify the owning allocator.** This is what makes `pfree`,
   `repalloc`, `GetMemoryChunkContext`, `GetMemoryChunkSpace` work without
   the caller passing a context. (`README:397-419` [from-readme])
2. **`MemoryChunk` (the standard chunk header) packs four fields into 64
   bits**: 4-bit method-ID, 1-bit external flag, 30-bit value (allocator-
   specific; for AllocSet it's the freelist index, for Generation/Slab/Bump
   it's the chunk size), 30-bit block-offset. Top bit of value and bottom
   bit of block-offset are *the same bit* — safe because MAXALIGN
   guarantees the offset's low bit is zero. (`README:421-435` [from-readme])
3. **"External" chunks** (large chunks on their own block) set bit 4 and
   stomp `MEMORYCHUNK_MAGIC` over the value+offset fields, signalling that
   the context type must find the block by other means (in practice: the
   block always starts immediately before the chunk header).
   (`README:437-442` [from-readme])
4. **Block-doubling + keeper block.** AllocSet doubles `nextBlockSize` per
   allocated block up to `maxBlockSize`. The first block ("keeper") shares
   its malloc allocation with the context header and is *not* returned to
   malloc on reset — this is the key to per-tuple contexts not thrashing
   the system allocator. (`README:444-468` [from-readme])
5. **Accounting is at block level, lazy, and per-context.** Asking for a
   subtree total walks all descendants. Don't build code that polls
   `MemoryContextMemAllocated` on a tree with many thousands of contexts.
   (`README:501-527` [from-readme])

## Cross-references

- Implementation: `aset.c`, `generation.c`, `slab.c`, `bump.c`,
  `alignedalloc.c`.
- Type-independent layer: `mcxt.c`.
- Header for the abstract struct: `source/src/include/nodes/memnodes.h`.
- Chunk header layout: `source/src/include/utils/memutils_memorychunk.h`.
- Method-ID enum and per-impl prototypes:
  `source/src/include/utils/memutils_internal.h`.
- Public API: `source/src/include/utils/palloc.h`,
  `source/src/include/utils/memutils.h`.
- The idiom-level distillation:
  `knowledge/idioms/memory-contexts.md`.

## Open questions

None — the README is the authoritative design statement and is consistent
with the code as of the last-verified commit.

## Confidence tag tally

- `[from-readme]` × ~15
- `[verified-by-code]` × 0 (this is a meta-doc *about* the README)
