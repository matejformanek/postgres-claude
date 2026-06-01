# brin_internal.h

- **Source path:** `source/src/include/access/brin_internal.h` (116 lines)
- **Last verified commit:** `ef6a95c7c64`

## Purpose

Internal types shared across the brin/*.c files but not exposed to non-BRIN code.

## Key types

- `BrinOpcInfo` — returned by opclass procnum 1 (`opcInfo`). Carries:
  - `oi_nstored` — number of Datums this opclass stores per indexed column (minmax=2, minmax-multi=1, bloom=1, inclusion=1+).
  - `oi_regular_nulls` — if true the framework manages `(hasnulls, allnulls)` bits; bloom turns this off because it wants its own NULL handling. [verified-by-code in opclass `opcInfo` impls]
  - `oi_typcache[FLEXIBLE_ARRAY]` — `TypeCacheEntry *` per stored column.
- `BrinDesc` — runtime descriptor for an open index: `bd_info[]` arrays of opclass info per indexed attribute, total `bd_totalstored`.

Function prototypes for `brin_doinsert`, `brinbuildCallback`, and the parallel-build helpers. Includes `amapi.h` so consumers see the AM-routine layout.
