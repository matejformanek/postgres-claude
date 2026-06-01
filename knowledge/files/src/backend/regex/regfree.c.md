# `src/backend/regex/regfree.c`

- **Last verified commit:** `ef6a95c7c64`
- **Lines:** ~50
- **Source:** `source/src/backend/regex/regfree.c`

`pg_regfree(re)` — release a compiled `regex_t`. Walks `re->re_guts`,
frees the colormap, all subre nodes (recursively), all cnfas, and the
guts itself; finally zeroes the public `regex_t` so re-use is detected.
PG-specific: uses `pfree` via the wrapped allocators set up in
regguts.h. [from-README]

## Synthesized by
<!-- backlinks:auto -->
- [subsystems/optimizer.md](../../../../subsystems/optimizer.md)
