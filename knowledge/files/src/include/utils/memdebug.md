# utils/memdebug.h — Valgrind shims + sentinel/wipe helpers

Source: `source/src/include/utils/memdebug.h` (83 lines)
Source pin: `4b0bf0788b066a4ca1d4f959566678e44ec93422`

## Role

Wraps `<valgrind/memcheck.h>` when built with USE_VALGRIND; otherwise provides no-op stubs. Plus optional `wipe_mem`, `set_sentinel`/`sentinel_ok`, `randomize_mem` for build-flag-gated memory-error detection.

## Public API

- Valgrind macros (forwarded or stubbed, `memdebug.h:20-33`): `VALGRIND_CHECK_MEM_IS_DEFINED`, `_CREATE_MEMPOOL`, `_DESTROY_MEMPOOL`, `_MAKE_MEM_DEFINED`, `_MAKE_MEM_NOACCESS`, `_MAKE_MEM_UNDEFINED`, `_MEMPOOL_ALLOC`, `_MEMPOOL_FREE`, `_MEMPOOL_CHANGE`, `_MEMPOOL_TRIM`.
- `wipe_mem(ptr, size)` (`memdebug.h:39-45`) — only if `CLOBBER_FREED_MEMORY`. Marks UNDEFINED, fills 0x7F, marks NOACCESS.
- `set_sentinel(base, offset)` / `sentinel_ok(base, offset)` (`memdebug.h:51-72`) — only if `MEMORY_CONTEXT_CHECKING`. Writes/checks 0x7E byte; wraps in Valgrind UNDEFINED/NOACCESS bracket.
- `randomize_mem(ptr, size)` (`memdebug.h:78`) — only if `RANDOMIZE_ALLOCATED_MEMORY`.

## Invariants

- **INV-valgrind-stubs-no-op** [verified-by-code, `memdebug.h:23-32`]: when USE_VALGRIND not defined, all macros expand to `do {} while (0)`. Safe to use unconditionally in caller code.
- **INV-wipe-byte-0x7F** [verified-by-code, `memdebug.h:42`]: chosen so freed memory is visibly tampered (not 0xFF or 0x00 which could be mistaken for valid data).
- **INV-sentinel-byte-0x7E** [verified-by-code, `memdebug.h:55, 67-68`]: 0x7E ≠ 0x7F so wiped vs sentinel are distinguishable.
- **INV-NOACCESS-after-set** [verified-by-code, `memdebug.h:56-58, 69-70`]: after writing the sentinel, mark NOACCESS so any other access trips Valgrind. Reading back via `sentinel_ok` temporarily marks DEFINED, then re-NOACCESS.
- **INV-build-flag-gated** [verified-by-code, `memdebug.h:36, 49, 76`]: `CLOBBER_FREED_MEMORY`, `MEMORY_CONTEXT_CHECKING`, `RANDOMIZE_ALLOCATED_MEMORY` are independent. Production builds typically have none.

## Trust-boundary / Phase-D surface

- **Sentinel-detection only catches small overruns** — 1 byte after the allocation. Larger overruns slip past sentinel into adjacent valid allocations.
- **0x7F-filled freed memory looks like valid float NaN** in some code paths; misdiagnosed crashes from use-after-free might appear as "NaN propagation" rather than UAF.

## Cross-refs

- `source/src/backend/utils/mmgr/{aset,slab,generation,bump}.c` — AllocSet/Slab/Generation/Bump contexts that consume these primitives.
- `knowledge/files/src/include/utils/memutils.h` (not in this slice but adjacent).

## Issues

- `[ISSUE-INFO: production builds skip sentinels entirely (info)]` — MEMORY_CONTEXT_CHECKING is debug-only; sentinel violations in production are silently corrupting. Worth noting in header.
