# btree_numeric.c

## One-line summary

GiST opclass for `NUMERIC` — uses the **variable-length** framework
(`btree_utils_var.c`) but **disables truncation** because numeric ordering is
not a byte-prefix order. Has its own `gbt_numeric_penalty` (variable-width
keys can't use the fixed-width `penalty_num` macro).

## Public API

Standard 7-function GiST set: `gbt_numeric_{compress,union,picksplit,
consistent,penalty,same,sortsupport}`
`source/contrib/btree_gist/btree_numeric.c:16-22`. No fetch.

## Key invariants

- **Truncation OFF** (`tinfo.trnc = false` at
  `source/contrib/btree_gist/btree_numeric.c:80`). Numeric is varlena but the
  varlena bytes (sign, weight, dscale, digits) are not lexicographically
  ordered — truncating them would break comparison. Both leaf and node store
  the full numeric.
- **No collation** — all comparators are plain `DirectFunctionCall2` to
  `numeric_gt/ge/eq/le/lt/cmp`.
- **`*recheck = false`** in `gbt_numeric_consistent` — exact match since no
  truncation `source/contrib/btree_gist/btree_numeric.c:118`.

## Notable internals

### Custom penalty

`source/contrib/btree_gist/btree_numeric.c:147` — does not use
`penalty_num` (which is fixed-width-only). Instead:

1. Union org + new.
2. `us = upper(union) - lower(union)` (the size of the merged range).
3. `os = upper(org) - lower(org)` (size of the original range).
4. `ds = us - os` (how much the range grew).
5. Penalty = `ds / us` (proportional growth), scaled by `FLT_MAX / (natts+1)`.

NaN handling at `source/contrib/btree_gist/btree_numeric.c:182`:
- If `us` is NaN AND `os` is NaN → penalty 0 (already saturated).
- If `us` is NaN AND `os` is finite → penalty 1.0 (worst case).
- Otherwise normal.

The `numeric_float8_no_overflow` conversion at `:201` saturates rather than
ereporting on huge numerics — defensive against pathological input.

## Trust boundary / Phase D surface

- **NaN semantics in numeric:** `numeric_cmp` treats NaN as greater than all
  other values (sql_features.h documents this). This is consistent across
  all six comparators here, so the index ordering is internally consistent.
  EXCLUDE constraints work correctly: `'NaN'::numeric = 'NaN'::numeric` is
  true, and the only conflict pattern.
- **Penalty NaN handling at `:182`** explicitly guards the divide-by-NaN case
  in `ds/us` (would otherwise produce NaN and propagate). This is the *only*
  per-type penalty function in btree_gist that handles NaN — `btree_float4.c`
  and `btree_float8.c` use `penalty_num` macro which does NOT handle NaN.
  See float4/float8 docs.
- **Varlena handling** flows through `gbt_var_compress` → `PG_DETOAST_DATUM`.
  A corrupt toasted numeric would `ereport(ERROR)` from `numeric_in` or
  `detoast_attr`, fail-closed.
- **Penalty arithmetic via `numeric_sub`/`numeric_div`** allocates intermediate
  Numerics in the current memory context. Inside `gbt_numeric_penalty`, the
  context is GiST's per-call context, freed after the call returns. No leak.
- **EXCLUDE constraint on `numeric(precision, scale)`:** scale/precision is
  enforced by the *type* — `gbt_numeric_compress` receives the already-coerced
  Datum. The index stores whatever was passed in; equality semantics match
  `numeric_eq`. Sound.

## Cross-references

- `source/src/backend/utils/adt/numeric.c` — `numeric_cmp`, `numeric_sub`,
  `numeric_div`, `numeric_is_nan`, `numeric_float8_no_overflow`.
- `knowledge/files/contrib/btree_gist/btree_utils_var.c.md` — framework.

## Issues spotted

- [ISSUE-PERF: Numeric keys are stored full-width and can be large (1000-digit
  numerics are legal). GiST index size scales linearly with numeric width;
  no truncation possible. (LOW — known limitation)]
- [ISSUE-CORRECTNESS-NAN: `gbt_numeric_penalty` `:201` calls
  `numeric_float8_no_overflow(os)` — this function returns `+Inf` for
  out-of-range, not NaN, so `(float4) ...` cast is safe. The downstream
  `*result *= FLT_MAX / natts` may produce `+Inf` for very large penalties;
  `add_path`-style comparisons against other `+Inf` penalties are not
  defined to give a deterministic ordering. Practically benign — there's
  always a tiebreaker — but worth flagging. (LOW)]
- [ISSUE-DEAD-CODE-RISK: `gbt_numeric_picksplit` calls `gbt_var_picksplit`
  with `tinfo.trnc = false`, so the trunc branch at
  `btree_utils_var.c:540` is dead for numeric. If anyone flipped `trnc =
  true` for numeric "to save space", the byte-prefix truncation would
  silently break numeric ordering. The convention is undocumented. (MED — a
  trap for future contributors)]
