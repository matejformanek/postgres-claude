# spginsert.c

- **Source path:** `source/src/backend/access/spgist/spginsert.c` (219 lines)
- **Last verified commit:** `ef6a95c7c64`

## Purpose

Externally-visible build + insert wrappers. **All actual insertion logic lives in `spgdoinsert.c`**; this file is the AM-callable surface. [from-comment, spginsert.c:1-15]

## Key entry points

- `spgbuild` — the build path: scan heap with a callback that calls `spgistBuildCallback` per row, which calls `spgdoinsert`.
- `spgbuildCallback` — per-heap-row callback during build.
- `spgbuildempty` — initialize a fresh metapage in the init fork via bulk write.
- `spginsert` — the AM slot; thin wrapper over `spgdoinsert`.

## Build is "just insert in a loop"

Unlike GIN/GIST which have sorted-build or buffering-build paths, SP-GiST simply calls `spgdoinsert` for every heap row. Reason: SP-GiST inserts touch random pages by design (space partitioning has no natural sort order across all opclasses), so pre-sorting wouldn't help. [inferred; no buffering build path in source]

Tags: [from-comment, spginsert.c:1-15].
