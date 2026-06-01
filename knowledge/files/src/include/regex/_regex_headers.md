# `src/include/regex/` (combined)

- **Last verified commit:** `ef6a95c7c64`
- **Source:** `source/src/include/regex/`

- `regex.h` — public API: `pg_regcomp`, `pg_regexec`, `pg_regfree`,
  `pg_regerror`, `pg_regprefix`. `regex_t` struct (`re_magic`,
  `re_nsub`, `re_info`, `re_csize`, `re_collation`, `re_lookahead`,
  `re_guts`, `re_fns`). Compile flags `REG_BASIC`, `REG_EXTENDED`,
  `REG_ADVANCED`, `REG_ICASE`, `REG_NOSUB`, `REG_NEWLINE`,
  `REG_EXPECT`, `REG_BOSONLY`. Execute flags `REG_NOTBOL`, `REG_NOTEOL`,
  `REG_STARTEND`. Error codes `REG_OKAY` .. `REG_ATOI`.
- `regexport.h` — NFA introspection for pg_trgm:
  `pg_reg_getnumstates`, `pg_reg_getinitialstate`,
  `pg_reg_getfinalstates`, `pg_reg_getnumoutarcs`,
  `pg_reg_getoutarcs`, `pg_reg_getsubre_*`.
- `regguts.h` — internal-only types shared between regcomp/regexec:
  `struct guts`, `struct cnfa`, `struct carc`, `struct subre`,
  `struct cvec`, `struct colormap`. Macros `MALLOC`/`FREE`/`REALLOC`
  abstract over palloc vs malloc.
- `regcustom.h` — PG-specific customizations: `chr` typedef as
  `pg_wchar`, `MALLOC` → `palloc`, etc.
- `regerrs.h` — `regex_errors[]` (REG_BADRPT, REG_BADBR, ...) name +
  message table; `#include`d into `regerror.c`.
