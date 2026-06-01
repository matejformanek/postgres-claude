# `src/backend/regex/regprefix.c`

- **Last verified commit:** `ef6a95c7c64`
- **Lines:** ~250
- **Source:** `source/src/backend/regex/regprefix.c`

`pg_regprefix(re, **string, *slen)` — extract a fixed-character prefix
that every matching input must start with. Walks the search CNFA from
the initial state, following the unique chain of "must be this exact
char" arcs (single-color arcs whose color contains exactly one chr,
with no alternative path out). Stops at the first branch/option point.
Used by the planner to convert `col ~ '^foo'` (and similar) into
`col >= 'foo' AND col < 'fop'` for B-tree index acceleration. [from-comment]
