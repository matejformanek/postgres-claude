# `src/backend/tsearch/dict_simple.c`

- **Last verified commit:** `ef6a95c7c64`
- **Lines:** ~90
- **Source:** `source/src/backend/tsearch/dict_simple.c`

"Simple" dictionary template: lowercase the lexeme, optionally check
against a stopword list, return as-is (no stemming). Options:
`STOPWORDS = filename`, `ACCEPT = true|false` (the latter controls
whether non-stopwords are accepted as their own lexeme or passed
through). Exports `dsimple_init` / `dsimple_lexize`. [from-comment]
