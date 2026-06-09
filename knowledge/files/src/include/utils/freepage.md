# utils/freepage.h — page-organized free-list backing DSA

Source: `source/src/include/utils/freepage.h` (98 lines)
Source pin: `4b0bf0788b066a4ca1d4f959566678e44ec93422`

## Role

`FreePageManager` — manages a region of `FPM_PAGE_SIZE` (4 kB) pages, tracking free spans via a btree + size-class freelists. The backing data structure for DSA segments.

## Public API

- `FPM_PAGE_SIZE = 4096` (`freepage.h:30`) — note: smaller than the 8 kB PG buffer page.
- `FPM_NUM_FREELISTS = 129` (`freepage.h:40`).
- Forward decls of `FreePageSpanLeader`, `FreePageBtree`, `FreePageManager` (`freepage.h:21-23`).
- `relptr_declare`s for each (`freepage.h:43-45`).
- `FreePageManager` struct (`freepage.h:48-64`): self relptr, btree_root + recycle relptrs, btree_depth, singleton page span, contiguous_pages (largest span), freelist[129].
- Conversion macros: `fpm_page_to_pointer`, `fpm_pointer_to_page`, `fpm_size_to_pages`, `fpm_pointer_is_page_aligned`, `fpm_relptr_is_page_aligned`, `fpm_segment_base`, `fpm_largest` (`freepage.h:67-89`).
- Functions: `FreePageManagerInitialize`, `FreePageManagerGet(npages, *first_page)`, `FreePageManagerPut(first_page, npages)`, `FreePageManagerDump` (`freepage.h:92-97`).

## Invariants

- **INV-FPM_PAGE_SIZE=4096** [from-comment, `freepage.h:26-30`]: "PostgreSQL normally uses 8kB pages for most things, but many common architecture/operating system pairings use a 4kB page size for memory allocation, so we do that here also." Chosen for OS page alignment, NOT PG buffer page alignment.
- **INV-129-freelists** [from-comment, `freepage.h:33-39`]: indices 0..127 hold spans of exactly that page count; index 128 holds "everything larger." Lets small allocations pop from the head without size verification.
- **INV-relptr-based** [verified-by-code, `freepage.h:43-45, 50-52`]: all internal pointers are RelptrFreePage* — usable across processes attached to the same dsm segment.
- **INV-base-derivable-from-self-relptr** [verified-by-code, `freepage.h:83-85`]: `fpm_segment_base(fpm) = ((char *)fpm) - relptr_offset(fpm->self)` — the manager knows its containing segment's base address.
- **INV-FPM_EXTRA_ASSERTS-debug-only** [verified-by-code, `freepage.h:60-63`]: `free_pages` counter is conditional debug-only.
- **INV-page-aligned-pointers** [from-macros]: `fpm_pointer_is_page_aligned`/`fpm_relptr_is_page_aligned` are asserts callers should use before storing into the freelist.

## Notable internals

- The btree (`btree_root`) tracks variable-size spans; the size-class freelists are the fast path for small spans. Tradeoff: freelist[128] still needs btree consultation to find best fit.
- `contiguous_pages_dirty` (`freepage.h:58`): largest-span cache, lazily refreshed.

## Trust-boundary / Phase-D surface

- **Wrong base in fpm_page_to_pointer** — `base` parameter is the segment's address; passing a wrong base in `FreePageManagerGet` callers yields out-of-segment writes. The StaticAssert at `freepage.h:68` only checks it's a `char *`.
- **`FreePageManagerPut` with overlapping spans** — header doesn't say what happens; implementation likely detects via the btree's sortedness but could corrupt with crafted input. DSA is the only consumer though.

## Cross-refs

- `knowledge/files/src/include/utils/dsa.md` — primary consumer.
- `knowledge/files/src/include/utils/relptr.md` — relative pointer machinery.
- `source/src/backend/utils/mmgr/freepage.c` — implementation.

## Issues

- `[ISSUE-DOC: FPM_PAGE_SIZE 4kB vs PG buffer 8kB easy to confuse (low)]` — comment is clear but readers used to BLCKSZ may grep the wrong constant.
