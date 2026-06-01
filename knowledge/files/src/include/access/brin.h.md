# brin.h

- **Source path:** `source/src/include/access/brin.h` (59 lines)
- **Last verified commit:** `ef6a95c7c64`

## Purpose

Public AM-callable surface for BRIN, plus reloption + planner-stats struct definitions. Included by core code that doesn't need page-level internals. [from-comment, brin.h:1-7]

## Key types

- `BrinOptions` — reloption storage: `pagesPerRange`, `autosummarize`.
- `BrinStatsData` — planner stats: `pagesPerRange`, `revmapNumPages`.
- `BRIN_DEFAULT_PAGES_PER_RANGE = 128`.

Exposes the `brinhandler` PG_FUNCTION declaration plus parallel-build entry-points (`_brin_parallel_main` etc.) and a `brinGetStats` helper.
