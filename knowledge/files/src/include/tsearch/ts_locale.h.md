# `src/include/tsearch/ts_locale.h`

- **Last verified commit:** `e18b0cb7344`
- **Lines:** ~75
- **Source:** `source/src/include/tsearch/ts_locale.h`

Locale-aware character classification + UTF-8/encoding-safe file
reader (`tsearch_readline`) used by ispell/snowball-style dictionaries
to parse on-disk `.dict`/`.affix`/stopword files. [verified-by-code]

## API / declarations

- `tsearch_readline_state { fp, filename, lineno, buf (UTF-8),
  curline (DB encoding), cb }` — caller stack-allocates;
  `curline` may be NULL, alias `buf.data`, or a separately palloc'd
  string (engine handles the difference). [verified-by-code]
- `tsearch_readline_begin`, `tsearch_readline`, `tsearch_readline_end`
  — convert each line into DB encoding via the
  `ErrorContextCallback cb` so any parsing errror naturally reports
  filename + line. [verified-by-code]
- `t_iseq(x, c)` macro — equality test, second arg MUST be ASCII.
  [verified-by-code] [from-comment]
- `TOUCHAR(x)` — cast to `const unsigned char *`.
- `ts_copychar_with_len(dest, src, length)` /
  `ts_copychar_cstr(dest, src)` — inline copy of a multibyte char.
  Historical alias: `COPYCHAR`. [verified-by-code]
- `GENERATE_T_ISCLASS_DECL(character_class)` macro generates three
  variants (`_with_len`, `_cstr`, `_unbounded`) plus a deprecated
  bare-name version. Instantiated for `alnum` and `alpha`.
  [verified-by-code]

## Notable invariants / details

- `tsearch_readline` always reads files as UTF-8 internally (the
  on-disk format) and converts to the DB encoding per line; that's
  why dictionary files must be UTF-8 regardless of server encoding.
  [from-comment]
- The "deprecated" plain `t_isalpha`/`t_isalnum` variants take a
  null-terminated string — newer code should use `_with_len` or
  `_cstr` to avoid implicit strlen-like scans on multibyte input.
  [inferred]

## Potential issues

- Three variants per class × deprecated bare name is a lot of surface
  area for "is alpha"; deprecation note is in the macro
  (`/* deprecated */`) but not advertised anywhere user-facing.
  [ISSUE-doc-drift: deprecated t_isXxx not on a removal schedule
  (nit)]
