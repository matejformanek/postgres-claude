# `src/backend/tsearch/ts_selfuncs.c`

- **Last verified commit:** `ef6a95c7c64`
- **Lines:** ~380
- **Source:** `source/src/backend/tsearch/ts_selfuncs.c`

Selectivity estimators for the `@@` (`tsvector @@ tsquery`) operator
and friends. Reads the MCELEM stats kind from `pg_statistic` — for
tsvector columns, ANALYZE (`ts_typanalyze.c`) stores most-common
lexemes + their frequencies. The estimator walks the tsquery's AND/OR
tree, for each leaf looks up the lexeme in the MCV array, applies
Jensen-like combination for AND, sum for OR, and falls back to a
default selectivity when the lexeme isn't in the MCV. [from-comment]
