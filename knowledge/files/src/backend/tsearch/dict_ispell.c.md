# `src/backend/tsearch/dict_ispell.c`

- **Last verified commit:** `ef6a95c7c64`
- **Lines:** ~140
- **Source:** `source/src/backend/tsearch/dict_ispell.c`

Ispell-template dictionary glue. Accepts DICT/AFFIX/STOPWORDS file
options; calls into `tsearch/dicts/spell.c` (which actually loads and
indexes the Ispell/Hunspell rule files). Exports
`dispell_init(internal)` and `dispell_lexize(internal,...)` —
referenced via `pg_ts_template.tmplinit`/`tmpllexize`. [from-comment]
