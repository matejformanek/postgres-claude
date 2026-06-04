# `src/backend/utils/adt/tsrank.c`

## Purpose

`ts_rank` (vector-of-weights × tsvector × tsquery) and `ts_rank_cd`
(cover-density rank). Configurable normalisation methods. 1043 lines.

## Key functions

- `word_distance` — `tsrank.c:45`. `1.0 / (1.005 + 0.05 * exp(w/1.5 - 2))`;
  returns `1e-30f` for `w > 100` to avoid `exp` overflow.
  `[verified-by-code]`
- `cnt_length` — `:54`. Count meaningful lexemes (handles empty
  position arrays as count-1).
- `find_wordentry` — `:87`. Binary search for a query operand in the
  tsvector's WordEntry table; honors prefix flag.
- `calc_rank_or`, `calc_rank_and` — `:38` decl. Recursive scorers
  over the polish-notation tsquery.
- `calc_rank` — Top-level dispatcher; applies the chosen
  `RANK_NORM_*` normalisation method (length, log length, etc.).
- `ts_rank_wttf`, `ts_rank_wtt`, `ts_rank_ttf`, `ts_rank_tt` —
  `:462`, `:481`, `:499`, `:514`. SQL entry points, four arity
  variants (weight array? normalisation flag?).
- `ts_rankcd_*` — `:980+`. Cover-density variants. The cover-density
  algorithm walks query positions in the vector and picks the
  smallest "cover" window.
- Argument validation at `:436-455`: rejects weights with NaN /
  ±inf? Actually rejects malformed weight arrays
  (`ereport ERROR` for wrong dims).

## Phase D notes

Output is `float4`. Internal computation uses `float8` in places
(via `exp`, `log`) then casts down. NaN inputs in the user-
supplied weights array propagate to NaN output — no explicit
`isnan` check in `calc_rank`. `[inferred]`

`word_distance` is clamped at `w > 100` (`:47`), so positions
beyond 100 saturate the exponential. The cap is hardcoded; no GUC.

For `ts_rank_cd`, the cover-window algorithm is O(query positions ×
vector positions) — already bounded by tsvector caps (`MAXNUMPOS`
≈ 256 per lexeme, `MAXSTRPOS` total).

## Potential issues

- [ISSUE-correctness: NaN in user weight arrays propagates to NaN
  rank output — no `isnan` check. Rank is supposed to be in
  `[0, 1]` range, so NaN breaks ORDER BY. Probably benign in
  practice (no one passes NaN explicitly) but worth a guard. (low,
  maybe)] — `:436+`
- [ISSUE-correctness: `1e-30f` saturation at `w > 100` in
  `word_distance` is a hardcoded magic number. For very long
  documents (lexemes at positions 100+) all far-distance scores
  collapse to the same tiny value — documented imprecision. (low)]
- [ISSUE-undocumented-invariant: `RANK_NORM_*` bit semantics are
  defined here (`:29-36`) and consumed in `calc_rank`. The bitmap
  is user-supplied via a SQL argument; values outside the mask are
  silently ignored. Worth an `errcode(ERRCODE_INVALID_PARAMETER_VALUE)`.
  (low)]
