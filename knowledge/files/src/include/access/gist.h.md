# gist.h

- **Source path:** `source/src/include/access/gist.h` (253 lines)
- **Last verified commit:** `ef6a95c7c64`

## Purpose

**Public** GiST API — exposed to opclass implementors. Backward-incompatible changes are avoided. [from-comment, gist.h:1-7]

## Procnum constants

```c
GIST_CONSISTENT_PROC   1
GIST_UNION_PROC        2
GIST_COMPRESS_PROC     3
GIST_DECOMPRESS_PROC   4
GIST_PENALTY_PROC      5
GIST_PICKSPLIT_PROC    6
GIST_EQUAL_PROC        7
GIST_DISTANCE_PROC     8
GIST_FETCH_PROC        9
GIST_OPTIONS_PROC      10
GIST_SORTSUPPORT_PROC  11
GISTNProcs             11
```

## Public structs

- `GISTPageOpaqueData` — page opaque: `nsn` (FullTransactionId-sized LSN), `rightlink`, `flags`, `gist_page_id` (a magic for page-type checking).
- `GISTSTATE` — opclass-cache (held in `IndexInfo->ii_AmCache`).
- `GISTENTRY` — single-key entry passed to opclass procs.
- `GIST_SPLITVEC` — `(spl_left[], spl_right[], spl_ldatum, spl_rdatum)`.

## Page flags

- `F_LEAF` — leaf page.
- `F_DELETED` — page deleted; carries `deleteXid` in opaque.
- `F_TUPLES_DELETED` — vacuum touched this page (heuristic).
- `F_FOLLOW_RIGHT` — split not yet linked to parent.
- `F_HAS_GARBAGE` — `LP_DEAD`-marked items present (cleanup deferred).

## Misc

- `GIST_ROOT_BLKNO = 0` — root is at block 0.
- `GIST_MAX_SPLIT_PAGES` — cap on N-way split (currently 75).
