# contrib/seg/segdata.h

Source pin: `4b0bf0788b066a4ca1d4f959566678e44ec93422`.

## Role

On-disk + in-memory layout of the `seg` data type, plus extern declarations
for the flex/bison scanner/parser entry points.

## Public API

```c
typedef struct SEG
{
    float4 lower;     /* lower bound */
    float4 upper;     /* upper bound */
    char   l_sigd;    /* significant digits, lower */
    char   u_sigd;    /* significant digits, upper */
    char   l_ext;     /* extension: '<','>','~','-','\0' */
    char   u_ext;
} SEG;
```

`source/contrib/seg/segdata.h:4-12`. Fixed 16-byte struct, no varlena
header — `seg` is a fixed-length pass-by-reference type. [verified-by-code]

Also exposes:
- `significant_digits(const char *)` — `seg.c:1074-1106`. Counts
  significant digits in a textual float representation.
- `seg_yylex`, `seg_yyerror`, `seg_scanner_init`, `seg_scanner_finish`
  — scanner entry points (`segdata.h:22-27`).
- `seg_yyparse` — bison entry (`segdata.h:30`).

## Invariants

- `lower <= upper`, enforced by `segparse.y:82-89`. Pre-1995 dumps
  may contain swapped boundaries, but new inputs are rejected.
  [verified-by-code]
- `l_ext` and `u_ext` are one of `<`, `>`, `~`, `-`, or `\0`. The
  `-` value indicates "open" bound paired with HUGE_VAL /
  -HUGE_VAL sentinels (`segparse.y:99,108`). [verified-by-code]
- `l_sigd`, `u_sigd` clamped to `Min(n, FLT_DIG)` (typically 6) at
  parse time (`segparse.y:182`). Storing larger values would overflow
  the `char` field if signed and >127 — but FLT_DIG is small enough
  this is moot. [verified-by-code]

## Trust-boundary / Phase-D surface

- `SEG` is a fixed-layout binary type — any out-of-range byte in
  l_ext/u_ext that arrives via `pg_upgrade` or corrupted page could
  reach `seg_cmp`'s switch-style fallthrough at `seg.c:792,850`
  which raises `elog(ERROR, "bogus … boundary types")`. That's an
  ERROR, not a PANIC, so the worst case is a query abort, not a
  crash. [verified-by-code]
- The four `char` fields are not zero-padded between them, so
  `memcmp` on two SEGs that are conceptually equal but have different
  l_ext bytes will diverge — but no code uses `memcmp` directly,
  comparisons all go through `seg_cmp`. [inferred]

## Cross-refs

- `source/contrib/seg/seg.c` — operator implementations.
- `source/contrib/seg/segparse.y` — construction sites that set the
  struct fields.

## Issues

None beyond those filed against `seg.c`.
