# src/include/common/shortest_dec.h

## Purpose
Public API for the Ryu shortest-decimal float→string formatters. Six
functions and two buffer-length constants. The only header callers in
`float.c` need to include.

## API
```c
#define DOUBLE_SHORTEST_DECIMAL_LEN 25  /* incl NUL */
int  double_to_shortest_decimal_bufn(double f, char *result);
int  double_to_shortest_decimal_buf(double f, char *result);
char *double_to_shortest_decimal(double f);

#define FLOAT_SHORTEST_DECIMAL_LEN 16   /* incl NUL */
int  float_to_shortest_decimal_bufn(float f, char *result);
int  float_to_shortest_decimal_buf(float f, char *result);
char *float_to_shortest_decimal(float f);
```

Worst-case lengths derived in the header comment (`shortest_dec.h:38-42`):
double `-9.9999999999999999e-299` = 24 + NUL = 25; float `-9.99999999e+29`
= 15 + NUL = 16.

## Role in PG
Included by `utils/adt/float.c` (the `float4out`/`float8out` user-facing
output functions) and by a small number of internal callers (e.g.
`pg_dump` for floating-point dumping). The `_buf` variants are preferred
when the caller has a stack buffer; the palloc-returning variants for
one-shot use.

## State / globals
None.

## Phase D notes
- **Lengths exclude NUL in the comment math but include it in the
  `#define`** — re-read the comment at lines 38-42: "*24 bytes, plus 1
  for null*". The `_LEN` constants are correct as buffer-size hints; the
  `_bufn` variant returns content length and **does not write NUL**, so
  callers using `_bufn` with a tight buffer must either copy + NUL
  manually or use the `_buf` variant.
- Misuse pattern: `double_to_shortest_decimal_bufn(f, small_buf)` where
  `small_buf` is exactly 24 bytes — works for content but `strlen()`
  afterwards would walk past. Callers always size by `_LEN`.

## Potential issues
- [ISSUE-undocumented-invariant: `_bufn` variants do NOT NUL-terminate;
  the suffix `n` is the only signal. Mistaking `_bufn` for `_buf` would
  leave a non-terminated string. (low)]

## Cross-references

<!-- issues:auto:begin -->
- [Issue register — `include-common`](../../../../issues/include-common.md)
<!-- issues:auto:end -->
