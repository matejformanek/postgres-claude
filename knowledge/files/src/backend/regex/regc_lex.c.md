# `src/backend/regex/regc_lex.c`

- **Last verified commit:** `ef6a95c7c64`
- **Lines:** ~1030; `#include`d into `regcomp.c`
- **Source:** `source/src/backend/regex/regc_lex.c`

Lexical analyzer for the regex pattern. Produces tokens for the
recursive-descent parser in `regcomp.c`. Knows the three flavors —
basic, extended/POSIX, advanced — controlled by `REG_BASIC` /
`REG_ADVANCED` (PG uses advanced by default), the embedded options
`(?xms)`, escape sequences (`\d`, `\s`, `\b`...), and bracket-expression
parsing. Maintains `v->next`/`v->save` for one-token lookahead and a
push-back slot. [from-README]

## Synthesized by
<!-- backlinks:auto -->
- [subsystems/optimizer.md](../../../../subsystems/optimizer.md)
