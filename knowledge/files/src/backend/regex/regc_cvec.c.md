# `src/backend/regex/regc_cvec.c`

- **Last verified commit:** `ef6a95c7c64`
- **Lines:** ~140; `#include`d into `regcomp.c`
- **Source:** `source/src/backend/regex/regc_cvec.c`

Allocator + accessor utilities for `struct cvec` — a character vector
used during bracket-expression parsing. A cvec holds three arrays:
single chars, char ranges `[lo..hi]`, and named character-class
references. Built incrementally as `regc_lex.c` walks `[...]` and
then fed to `subcolor` to add to the colormap. [from-README]

## Synthesized by
<!-- backlinks:auto -->
- [subsystems/optimizer.md](../../../../subsystems/optimizer.md)
