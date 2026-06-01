# `src/backend/tsearch/ts_typanalyze.c`

- **Last verified commit:** `ef6a95c7c64`
- **Lines:** ~530
- **Source:** `source/src/backend/tsearch/ts_typanalyze.c`

`tsvector_typanalyze` — the `typanalyze` hook for the `tsvector` type.
ANALYZE calls it per tsvector column. The implementation does **not**
build per-tsvector stats; instead it implements **lossy lexeme
sampling** across the entire column to produce `STATISTIC_KIND_MCELEM`
data: most-common lexemes + their global frequencies.

Algorithm: Cormode/Muthukrishnan lossy-counting style — maintain a hash
of (lexeme → count, last-seen-bucket); on each ANALYZE row,
increment, then periodically prune entries whose count has fallen
below the current "bucket epoch". Final pass selects the top N
lexemes (sized from `default_statistics_target`) for storage. This
makes `ts_selfuncs.c` cheap and accurate. [from-comment]
