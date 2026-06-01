# `src/backend/regex/regc_locale.c`

- **Last verified commit:** `ef6a95c7c64`
- **Lines:** ~750; `#include`d into `regcomp.c`
- **Source:** `source/src/backend/regex/regc_locale.c`

Built-in tables for POSIX-named character classes (`[:alpha:]`,
`[:digit:]`, `[:xdigit:]`, ...) plus equivalence classes (`[=a=]`) and
collating elements (`[.ch.]`). For Unicode-aware classes, defers to
`regc_pg_locale.c` which queries the active collation/ctype provider
(libc / ICU / built-in). Returns `cvec`s the parser then folds into
the colormap. [from-README]
