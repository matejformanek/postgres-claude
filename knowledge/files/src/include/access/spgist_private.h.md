# spgist_private.h

- **Source path:** `source/src/include/access/spgist_private.h` (551 lines)
- **Last verified commit:** `ef6a95c7c64`

## Purpose

Internal SP-GiST types shared across `src/backend/access/spgist/*.c`. [from-comment, spgist_private.h:1-9]

## Key types

- `SpGistOptions` — `fillfactor`.
- `SpGistState` — per-relation opclass cache: `config`, `attLeafType`, `attPrefixType`, `attLabelType`, `compressFn`, `chooseFn`, `picksplitFn`, etc.
- `SpGistMetaPageData` — metapage: magic, root-block of main tree, root-block of nulls tree, **last-used-page cache** (4 entries × 2 trees), versioned flags.
- `SpGistPageOpaqueData` — page-special: `nRedirection`, `nPlaceholder`, `flags` (LEAF, NULLS, ROOT).
- `SpGistLeafTuple`, `SpGistInnerTuple`, `SpGistNodeTuple`, `SpGistDeadTuple` — on-disk tuple shapes.
- Tuple-state constants: `SPGIST_LIVE`, `SPGIST_REDIRECT`, `SPGIST_DEAD`, `SPGIST_PLACEHOLDER`.

## Macros

- `SpGistPageStoresNulls(page)`, `SpGistPageIsLeaf(page)`, `SpGistBlockIsRoot(blkno)`, `SpGistPageIsLeafPage(page)` — page-type predicates.
- `SGITDP_*` — dead-tuple-pointer encoding.

## Constants

- `SPGIST_LAST_FIXED_BLKNO` — the highest fixed-meaning block (the two roots).
- `SPGIST_METAPAGE_BLKNO = 0`.
- `SPGIST_ROOT_BLKNO = 1` (main tree).
- `SPGIST_NULL_BLKNO = 2` (nulls tree).
