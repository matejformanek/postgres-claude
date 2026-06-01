# `src/backend/regex/README` (anchor)

- **Last verified commit:** `ef6a95c7c64`
- **Source:** `source/src/backend/regex/README`

Author: Henry Spencer's library, adapted for PG (functions prefixed
`pg_`). 26 KB of reverse-engineered internals documentation — load-
bearing for understanding `regcomp.c` / `regexec.c`.

## Six top-level files

- `regcomp.c` — `pg_regcomp`. Parses pattern, builds NFA, optimizes,
  compiles to CNFA for the DFA executor.
- `regexec.c` — `pg_regexec`. Lazy DFA execution with NFA fallback for
  back-references / lookaround.
- `regerror.c` — `pg_regerror`.
- `regfree.c` — `pg_regfree`.
- `regprefix.c` — `pg_regprefix` (extract literal prefix for index
  acceleration of `LIKE`/`~` planning).
- `regexport.c` — multi-function: walk a compiled NFA (used by
  `pg_trgm` to derive trigrams from a regex).

The `regc_*.c` files are `#include`'d into `regcomp.c` so their static
symbols don't leak; same for `rege_*.c` into `regexec.c`. This is
load-bearing: don't try to compile them standalone.

## Strategy summary (DFA vs NFA)

Spencer's library uses a **lazy DFA built from an NFA**. The DFA is
the fast path (linear time), the NFA is kept around for:
- back-references (DFA cannot handle them)
- lookaround constraints (lookahead/lookbehind)
- per-character class checks the DFA states encode as "color" lookups

When the DFA executor encounters a sub-pattern requiring back-refs or
lookarounds, it falls back to NFA-style backtracking just for that
sub-pattern. The two exported globals leaking out of regcomp →
regexec are `pg_set_regex_collation` and `pg_reg_getcolor` (the README
flags both as design debt).
