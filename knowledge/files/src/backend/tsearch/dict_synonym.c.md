# `src/backend/tsearch/dict_synonym.c`

- **Last verified commit:** `ef6a95c7c64`
- **Lines:** ~230
- **Source:** `source/src/backend/tsearch/dict_synonym.c`

Synonym dictionary template: word-for-word substitution from a
two-column file (`old new`). Loaded once at dict init into a sorted
array, then bsearch on lexize. Supports asterisk (`*`) suffix marking
the synonym as having phrase variants; `CaseSensitive = true|false`
option. `dsynonym_init` / `dsynonym_lexize`. [from-comment]
