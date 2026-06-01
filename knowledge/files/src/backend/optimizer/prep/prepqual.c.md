# prepqual.c — qual canonicalization (NOT push-down, OR distribution)

- **Source:** `source/src/backend/optimizer/prep/prepqual.c` (676 lines)
- **Last verified commit:** `ef6a95c7c64`
- **Depth:** read

## Purpose

Normalize qualification expressions: push NOTs down via De Morgan,
flatten nested AND/OR, distribute OR-of-AND-of-foo when it exposes
more top-level AND structure. Assumes input already passed through
`eval_const_expressions` (which now owns the initial flattening).
[from-comment:7-19]

## Public entries

- `Node *negate_clause(Node *node)` (line 72) — applies De Morgan's
  laws; may *increase* the number of NOTs (e.g. `NOT (a AND b)` →
  `NOT a OR NOT b`). Done unconditionally because exposing AND/OR
  structure pays off for WHERE-clause planning. Also makes
  logically-equal expressions `equal()`-comparable. [from-comment:60-67]
- `Expr *canonicalize_qual(Expr *qual, bool is_check)` (line 292) —
  the top-level driver. `is_check=true` adjusts for CHECK constraints
  (NULL is "OK" rather than "false"). [from-comment:285-291]
- `pull_ands` / `pull_ors` (static helpers) — flatten nested
  same-kind boolean ops; called from inside transformations to keep
  AND/OR-flatness.

## Tags
`[verified-by-code]` ×2, `[from-comment]` ×4

## Synthesized by
<!-- backlinks:auto -->
- [subsystems/optimizer.md](../../../../../subsystems/optimizer.md)
