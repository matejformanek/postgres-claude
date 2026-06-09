# contrib/cube/cubedata.h

Source pin: `4b0bf0788b066a4ca1d4f959566678e44ec93422`.

## Role

On-disk and in-memory layout for the `cube` type. Declares `NDBOX`,
the `IS_POINT` / `DIM` / `LL_COORD` / `UR_COORD` accessors, KNN
strategy numbers, scanner/parser externs.

## Public API

```c
#define CUBE_MAX_DIM (100)

typedef struct NDBOX
{
    int32         vl_len_;              /* varlena header */
    unsigned int  header;               /* dim in bits 0-7, POINT_BIT in bit 31 */
    double        x[FLEXIBLE_ARRAY_MEMBER];
} NDBOX;
```

`source/contrib/cube/cubedata.h:7-34`. [verified-by-code]

Macros: `POINT_BIT 0x80000000`, `DIM_MASK 0x7fffffff`, `IS_POINT`,
`SET_POINT_BIT`, `DIM`, `SET_DIM`, `LL_COORD`, `UR_COORD`, `POINT_SIZE`,
`CUBE_SIZE` (`:36-49`). KNN strategy numbers 15-18 (`:57-60`).
[verified-by-code]

## Invariants

- `DIM(cube) ≤ CUBE_MAX_DIM = 100`. Enforced at every constructor.
  100 is "pretty arbitrary, but don't make it so large that you risk
  overflow in sizing calculations" (`:3-6` comment). With dim=100,
  `CUBE_SIZE = 8 + 100*8*2 = 1608` bytes — well below MaxAllocSize.
  [verified-by-code, from-comment]
- For an IS_POINT cube, only DIM doubles are stored; `UR_COORD(i)`
  redirects to `x[i]`. [verified-by-code]
- Header bits 8-30 are documented as "unused, initialize to zero"
  (`:21`) but no code masks them on input; see Issues in `cube.c.md`.

## Trust-boundary / Phase-D surface

- `CUBE_MAX_DIM` is the single Phase-D-relevant constant. 100 keeps
  per-cube storage bounded at ~1.6 KB; without it, GiST page splits
  with thousands of dimensions would explode in O(dim²). [inferred]

## Cross-refs

- `source/contrib/cube/cube.c` — uses every macro defined here.
- `source/contrib/cube/cubeparse.y` — enforces `CUBE_MAX_DIM`.

## Issues

None beyond those filed against `cube.c`.
