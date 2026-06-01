# brin_page.h

- **Source path:** `source/src/include/access/brin_page.h` (96 lines)
- **Last verified commit:** `ef6a95c7c64`

## Purpose

Page-layout constants and macros for BRIN, exposed for `pageinspect`-style tools. "These structs should really be private to specific BRIN files, but it's useful to have them here." [from-comment, brin_page.h:11-15]

## Key constants

- `BRIN_PAGETYPE_META`, `BRIN_PAGETYPE_REVMAP`, `BRIN_PAGETYPE_REGULAR` — the three values stored in the special area, last uint16 of the page.
- `BRIN_EVACUATE_PAGE` — flag bit on regular pages (set as dirty-hint by `brin_start_evacuating_page`, **not WAL-logged**).
- `BRIN_METAPAGE_BLKNO = 0` — fixed metapage location.
- `BRIN_META_MAGIC` / `BRIN_CURRENT_VERSION` — metapage version tag.

## Key types

- `BrinSpecialSpace` — last MAXALIGN element of every BRIN page; holds `(flags, type)` in fixed positions so external tools can decode page type by reading the trailing 4 bytes.
- `BrinMetaPageData` — fields in the metapage contents area: `brinMagic`, `brinVersion`, `pagesPerRange`, `lastRevmapPage`.
- `RevmapContents` — on a revmap page, the contents area is `ItemPointerData rm_tids[REVMAP_PAGE_MAXITEMS]`.
- `REVMAP_PAGE_MAXITEMS` — computed from `PageGetContents` capacity.

## Macros

- `BRIN_IS_META_PAGE(page)`, `BRIN_IS_REVMAP_PAGE(page)`, `BRIN_IS_REGULAR_PAGE(page)` — check `BrinPageType(page)`.
- `BrinPageFlags(page)` / `BrinPageType(page)` — accessors into the special area.

Tags: [from-comment, brin_page.h:11-15]; constants [verified-by-code].
