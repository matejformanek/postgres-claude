# contrib/seg/seg.c

Source pin: `b78cd2bda5b1a306e2877059011933de1d0fb735` (re-verified
2026-06-16 by pg-quality-auditor AUDIT mode after anchor-bump
`e18b0cb7344..da1eff08a5be` touched `contrib/seg/seg.c`).

## Role

Implements the `seg` data type — a 1-D float4 interval `[lower..upper]`
augmented with significant-digit and "extension" metadata (`<`, `>`, `~`,
`-`) used to express measurement-uncertainty ranges. Provides text I/O,
R-tree-style operators (overlap, contains, left, right, …), a btree
opclass via `seg_cmp`, and the GiST opclass support functions
(`gseg_consistent`, `gseg_union`, `gseg_picksplit`, `gseg_penalty`,
`gseg_same`, `gseg_compress`, `gseg_decompress`). [verified-by-code]
`source/contrib/seg/seg.c:31` (PG_MODULE_MAGIC_EXT), `:107` (seg_in),
`:200` (gseg_consistent), `:324` (gseg_picksplit).

## Public API (SQL-callable)

- I/O: `seg_in`, `seg_out`, `seg_size`, `seg_lower`, `seg_upper`,
  `seg_center` — `source/contrib/seg/seg.c:107,124,724,173,181,165`.
- GiST methods: `gseg_consistent / _union / _compress / _decompress
  / _penalty / _picksplit / _same` — `:200,228,259,265,275,324,417`.
- R-tree operators: `seg_same / _contains / _contained / _overlap
  / _left / _over_left / _right / _over_right / _union / _inter` —
  `:564,542,551,577,602,590,614,626,635,675`.
- Btree comparison: `seg_cmp` plus `seg_lt/le/gt/ge/different` —
  `:736,858–905`. [verified-by-code]

## Invariants

- `SEG.lower <= SEG.upper` enforced at parse time
  (`segparse.y:82-89`) — swapped boundaries raise
  `ERRCODE_INVALID_PARAMETER_VALUE`. [verified-by-code]
- `seg_in` always palloc's a fixed `SEG` (`palloc_object(SEG)` —
  `seg.c:110`). On parse error, `seg_yyerror` raises via `errsave`,
  but if `seg_yyparse` returns nonzero without a soft error,
  `seg.c:115-117` calls `seg_yyerror` with "bogus input". The leaked
  SEG goes back through the per-call memory context. [verified-by-code]
- `seg_cmp` lexicographically orders by lower-bound value, then
  l_ext kind, then l_sigd, then upper-bound value, then u_ext, then
  u_sigd (`seg.c:736-855`). The order treats `-` (HUGE_VAL sentinel)
  as least for lower and greatest for upper, then `<` lowest, `>`
  highest, `~` (approximate) less than exact. [verified-by-code]
- `gseg_consistent` sets `*recheck = false` for all strategies
  (`seg.c:211`) — relies on bounding seg containing children exactly.
  [verified-by-code]

## Notable internals

- `gseg_picksplit` (rewritten from Guttman to 1-D center-sort) at
  `seg.c:317-411`. Uses `center = lower*0.5f + upper*0.5f` (`:354`)
  to avoid overflow. Splits at `maxoff / 2`. [verified-by-code,
  from-comment]
- `gseg_penalty` returns `union_size − orig_size` (`:289`). Uses
  `rt_seg_size` which returns 0 for `upper <= lower` (`:717`). For
  segments with NaN endpoints, `fabsf(NaN - NaN) = NaN`; this likely
  propagates a NaN penalty back into GiST split decisions and corrupts
  tree quality (no clamp). [inferred]
- `restore` (`:923-1063`) prints a float with a fixed number of
  significant digits to a 16-byte buffer. Caller in `seg_out` palloc's
  40 bytes (`:130`) — sufficient. Hard-caps `n` to `FLT_DIG` (typically
  6) so the buffer overflow risk is bounded; `n <= 0` reset to
  `FLT_DIG` (`:944-947`). [verified-by-code]
- The output buffer in `seg_out` is built with `sprintf` (`:148,150,
  154,156`) — no bounds checking; relies on `restore()` cap +
  fixed-width separator chars staying under 40 bytes. With l_ext + ` `
  + 15 + ` .. ` + 15 + u_ext that's ~37 bytes plus NUL — tight but
  appears safe. [inferred]

## Trust-boundary / Phase-D surface

- **NaN in seg endpoints** — `segparse.y` uses `float4in_internal`
  (`segparse.y:170`), which accepts `NaN` and `Inf`. `seg_cmp` compares
  via `<` / `>` on floats; NaN propagates IEEE-754 unordered semantics:
  every `<` and `>` returns false, so `seg_cmp` falls through to the
  l_ext/l_sigd branches and may return 0 for two distinct NaN segs,
  producing the same btree-uniqueness violation as A13 btree_gist
  float (`EXCLUDE USING gist (val WITH =)` permits duplicate NaN rows).
  [ISSUE-correctness, similar to A13 btree_gist]
- **NaN in GiST picksplit center** — `seg.c:354` computes `seg->lower
  * 0.5f + seg->upper * 0.5f`. If either is NaN, center is NaN, and
  the qsort comparator at `:303` treats `NaN < x`, `NaN == x`,
  `NaN > x` all as false → falls through to `return 1`, an unstable
  ordering. NaN-heavy data could degrade GiST tree quality to linear
  scans. [ISSUE-correctness]
- **HUGE_VAL boundary collapse** — comments at `:751-755,809-811`
  flag that "-HUGE_VAL used as a regular data value" can interact
  with the `-` extension marker. Attacker could inject `HUGE_VAL`
  to spoof boundaries. [ISSUE-DoS-low, from-comment]
- **`elog(ERROR)` on corrupt data** — `:792,850` `"bogus … boundary
  types"` — only triggered by on-disk corruption, not by user input.
  Defensive. [verified-by-code]

## Cross-refs

- `source/contrib/seg/segparse.y` — bison grammar, calls
  `float4in_internal` for actual float parsing.
- `source/contrib/seg/segscan.l` — flex scanner.
- `source/contrib/seg/segdata.h` — `SEG` struct layout (16-byte
  fixed: float4 lower, float4 upper, 4 chars).
- A13 `btree_gist` float family — same NaN comparison hazard with
  GiST exclusion constraints.

<!-- issues:auto:begin -->
- [Issue register — `seg`](../../../issues/seg.md)
<!-- issues:auto:end -->

## Issues

- `[ISSUE-correctness: NaN comparison in seg_cmp lets duplicate NaN
  segs satisfy EXCLUDE USING gist (val WITH =)] (medium)` —
  `source/contrib/seg/seg.c:744-855`
- `[ISSUE-correctness: NaN endpoint in gseg_picksplit center yields
  unstable qsort comparator → degenerate tree under adversarial data]
  (medium)` — `source/contrib/seg/seg.c:354,303-314`
- `[ISSUE-DoS-low: HUGE_VAL injected as a "regular" boundary value
  collides with the `-` extension sentinel; comment acknowledges the
  ambiguity but no validation rejects it] (low)` —
  `source/contrib/seg/seg.c:751-755`
- `[ISSUE-robustness: seg_out builds output with sprintf into a
  fixed 40-byte buffer; safe today only because restore() caps digits
  at FLT_DIG] (low)` — `source/contrib/seg/seg.c:130-159`

## Synthesized by
<!-- backlinks:auto -->
- [subsystems/contrib-seg.md](../../../subsystems/contrib-seg.md)
