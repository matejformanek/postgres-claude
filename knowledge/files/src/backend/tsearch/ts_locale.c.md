# `src/backend/tsearch/ts_locale.c`

- **Last verified commit:** `ef6a95c7c64`
- **Lines:** ~180
- **Source:** `source/src/backend/tsearch/ts_locale.c`

Multibyte/locale-aware character utilities used by every dictionary
and the default parser: `t_isalpha`, `t_isalnum`, `t_isspace`,
`t_isdigit`, `lowerstr`/`lowerstr_with_len`. They work on the current
DB encoding and respect the per-config collation passed to lexize.
Also `tsearch_readline`-family routines for safely reading dict/affix
files (with EOF/encoding error handling). [from-comment]

## Synthesized by
<!-- backlinks:auto -->
- [subsystems/optimizer.md](../../../../subsystems/optimizer.md)
