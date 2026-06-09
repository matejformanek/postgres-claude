# Issues — `contrib/cube`

N-dimensional cube datatype + GiST opclass. 2 source files / ~1999 LOC.

**Parent docs:** `knowledge/files/contrib/cube/cube.c.md`, `knowledge/files/contrib/cube/cubedata.h.md`.

**Source:** 6 entries surfaced 2026-06-09 by A14-3.

## Headlines

1. **NaN coords defeat `cube_cmp` / `contains` / `overlap` semantics** — breaks `EXCLUDE USING gist`. Direct echo of A13 btree_gist + A14 seg.
2. **Inf coords → `Inf*0=NaN` in `rt_cube_size` → NaN penalty in `g_cube_penalty`** → poor GiST splits → degenerate index.
3. **`cubeparse` list-builder palloc's `scanbuflen+1` BEFORE `CUBE_MAX_DIM` check** — `YY_READ_BUF_SIZE = 16 MB` allowed before any rejection. **Memory DoS upstream of the dim cap.**
4. UB-low: `g_cube_distance` + `cube_coord_llur` do `coord=-coord` without guarding `INT32_MIN`.
5. `cube_recv` doesn't mask unused header bits 8-30 contrary to `cubedata.h` invariant.
6. `g_cube_picksplit` O(N²) Guttman split is DoS-amplifier on pathological page splits.

## Entries

- [ISSUE-correctness: NaN coords defeat `cube_cmp`/`contains`/`overlap` semantics; breaks `EXCLUDE USING gist` (likely)] — `source/contrib/cube/cube.c:944-1021,1131-1236`
- [ISSUE-correctness: Inf coords → `Inf*0=NaN` in `rt_cube_size` → NaN penalty in `g_cube_penalty` → poor GiST splits (likely)] — `source/contrib/cube/cube.c:914-937,491-507`
- [ISSUE-resource: `cubeparse` list-builder palloc's `scanbuflen+1` BEFORE `CUBE_MAX_DIM` check; `YY_READ_BUF_SIZE = 16 MB` allowed before any rejection (likely)] — `source/contrib/cube/cubeparse.y:154-166, cubescan.l:17`
- [ISSUE-correctness: `g_cube_distance` + `cube_coord_llur` do `coord=-coord` without guarding `INT32_MIN` (nit)] — `source/contrib/cube/cube.c:1431-1434,1666-1671`
- [ISSUE-defense-in-depth: `cube_recv` doesn't mask unused header bits 8-30 contrary to `cubedata.h` invariant (nit)] — `source/contrib/cube/cube.c:374-378`
- [ISSUE-resource: `g_cube_picksplit` O(N²) Guttman split is DoS-amplifier on pathological page splits (nit)] — `source/contrib/cube/cube.c:516-660`

## Cross-sweep references

- A13 btree_gist float4/float8 NaN — same root pattern.
- A14 seg — sister geometric module with same NaN hazards.
- A5 jsonapi recursive-parser — `cubeparse.y` echo.
