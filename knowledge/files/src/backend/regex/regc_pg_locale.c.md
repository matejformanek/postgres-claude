# `src/backend/regex/regc_pg_locale.c`

- **Last verified commit:** `ef6a95c7c64`
- **Lines:** ~390; `#include`d into `regcomp.c`
- **Source:** `source/src/backend/regex/regc_pg_locale.c`

PG-specific layer between Spencer's locale-agnostic regex and PG's
collation system. Adapts `iswupper`/`iswalpha`/`towlower`/etc. to work
on `pg_wchar` (`chr`) under the currently-active `pg_locale_t`
(libc / ICU / built-in Unicode). Caches "ctype maps" — wholesale
probing of which characters fall into which POSIX class for the active
locale — to avoid per-character collation calls in tight loops.

`pg_set_regex_collation(colloid)` (called from both regcomp and
regexec) chooses the `pg_locale_t` for this match. The README calls
out the static-state coupling as design debt to be eliminated.
[from-comment]
