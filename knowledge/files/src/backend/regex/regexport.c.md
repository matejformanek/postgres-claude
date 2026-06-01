# `src/backend/regex/regexport.c`

- **Last verified commit:** `ef6a95c7c64`
- **Lines:** ~270
- **Source:** `source/src/backend/regex/regexport.c`

Exposes the compiled NFA shape for outside readers (currently
`contrib/pg_trgm` regex indexing). API: walk colors
(`pg_reg_getsubre_num_colors`, `pg_reg_getsubre_color`...) and walk
states/arcs of the top-level NFA (`pg_reg_getnumstates`,
`pg_reg_getfinalstates`, `pg_reg_getnumoutarcs`,
`pg_reg_getoutarcs`).

Notable design: the NFA is necessary-but-not-sufficient — strings can
match the NFA without matching the full regex (because back-refs and
lookarounds are dropped). This is OK for trigram indexing because the
trigram set is also a necessary-but-not-sufficient filter; false
positives are caught by the recheck. [from-comment] (`regexport.c:6-10`)
