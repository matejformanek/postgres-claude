# `src/backend/regex/regc_color.c`

- **Last verified commit:** `ef6a95c7c64`
- **Lines:** ~1180; `#include`d into `regcomp.c`
- **Source:** `source/src/backend/regex/regc_color.c`

Color machinery: partition the (potentially huge — Unicode) input
alphabet into equivalence classes such that every NFA arc accepts
either all chars of a color or none. Two-level radix lookup for the
low-codepoint range (fast inline) plus a hash table for hi codepoints.
Each new bracket-expression or character class triggers `subcolor` to
split colors as needed. Result: NFA arc count is bounded by
distinguishable color classes, not by alphabet size. [from-README]

## Synthesized by
<!-- backlinks:auto -->
- [subsystems/optimizer.md](../../../../subsystems/optimizer.md)
