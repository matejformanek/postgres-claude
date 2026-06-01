# `src/backend/regex/regerror.c`

- **Last verified commit:** `ef6a95c7c64`
- **Lines:** ~100
- **Source:** `source/src/backend/regex/regerror.c`

`pg_regerror(errcode, re, errbuf, errbuf_size)` — error-code → string
expansion. Pulls the canonical message from `regex/regerrs.h` (a list of
`REG_*` constants paired with their human messages). Used by SQL-level
regex functions to populate ereport detail. [from-README]
