# `src/include/regex/regex.h`

- **Last verified commit:** `e18b0cb7344`
- **Lines:** ~272
- **Source:** `source/src/include/regex/regex.h`

PG's POSIX-compatible regex front-end. Replaces the system
`<regex.h>` (note the `_PG_REGEX_H_` guard chosen specifically to
NOT collide with BSD's `_REGEX_H_`). Public API of the Henry-Spencer
regex engine, locally customized: compiled regex (`pg_regex_t`),
match struct (`pg_regmatch_t`), result detail (`rm_detail_t`).
Original copyright Henry Spencer 1998-1999. [verified-by-code]

## API / declarations

### Compiled regex

- `pg_regex_t { re_magic, re_nsub, re_info, re_csize, re_endp,
  re_collation, re_guts (opaque), re_fns (opaque) }`. `re_info`
  carries `REG_U*` flag bits describing what features the regex
  actually uses (set by compile, queried by callers — see Notable
  invariants). [verified-by-code]
- Result types: `pg_regmatch_t { rm_so, rm_eo }`,
  `rm_detail_t { rm_extend }`, `pg_regoff_t` (long).
- Typedef redirects: `regex_t` → `pg_regex_t`, `regmatch_t` →
  `pg_regmatch_t`, `regoff_t` → `pg_regoff_t`.

### Compile flags (`pg_regcomp` flags arg)

- `REG_BASIC=0` (BREs), `REG_EXTENDED=1` (EREs), `REG_ADVF=2`,
  `REG_ADVANCED=3` (AREs = EREs + advanced features), `REG_QUOTE=4`
  (no special chars), `REG_ICASE=010`, `REG_NOSUB=020`,
  `REG_EXPANDED=040`, `REG_NLSTOP=0100`, `REG_NLANCH=0200`,
  `REG_NEWLINE=0300`, `REG_PEND=0400` (back-compat), `REG_EXPECT=01000`,
  `REG_BOSONLY=02000`, `REG_DUMP=04000`, `REG_FAKE=010000`,
  `REG_PROGRESS=020000`. [verified-by-code]

### Execution flags (`pg_regexec` flags arg)

- `REG_NOTBOL=01`, `REG_NOTEOL=02`, `REG_STARTEND=04`,
  `REG_FTRACE=010`, `REG_MTRACE=020`, `REG_SMALL=040`.

### re_info usage flags (set on compiled regex)

- `REG_UBACKREF` (has `\n`), `REG_ULOOKAROUND` (lookahead/behind),
  `REG_UBOUNDS` (`{m,n}`), `REG_UBRACES`, `REG_UBSALNUM`,
  `REG_UPBOTCH` ("unmatched right paren in ERE (legal per spec, but
  that was a mistake)"), `REG_UBBS`, `REG_UNONPOSIX`, `REG_UUNSPEC`
  (empty branch), `REG_UUNPORT` (numeric char code dep),
  `REG_ULOCALE`, `REG_UEMPTYMATCH`, `REG_UIMPOSSIBLE`,
  `REG_USHORTEST` (non-greedy). [from-comment]

### Error codes (driven by `regerrs.h`)

- `REG_OKAY=0`, `REG_NOMATCH=1`, … `REG_ECOLORS=20`, plus debug-only
  `REG_ATOI=101`/`REG_ITOA=102`, and `pg_regprefix`-only
  `REG_PREFIX=-1`/`REG_EXACT=-2`.

### Exported functions

- `pg_regcomp(re, string, len, flags, collation)`,
- `pg_regexec(re, string, len, search_start, details, nmatch,
  pmatch[], flags)`,
- `pg_regprefix(re, **string, *slength)`,
- `pg_regfree(re)`,
- `pg_regerror(errcode, preg, errbuf, errbuf_size)`,
- `RE_compile_and_cache(text_re, cflags, collation)` (regexp.c
  cache layer),
- `RE_compile_and_execute(text_re, dat, dat_len, cflags, collation,
  nmatch, pmatch)`.

## Notable invariants / details

- The huge `#undef REG_*` wall at the top exists because PG forces
  the system `<regex.h>` to be included first (on non-Windows) and
  then strips its definitions so PG's own can take over. macOS+BSD
  use the same include guard as PG would, so the guard had to be
  named differently. [from-comment]
- Inputs to `pg_regcomp`/`pg_regexec` are `pg_wchar` arrays, not
  bytes — encoding conversion happens outside.
- `RE_compile_and_cache` returns a cached regex_t — callers MUST NOT
  call `pg_regfree` on it. [inferred]
- The "Be careful if modifying the list of error codes — the table
  used by regerror() is generated automatically from this file!"
  comment lines up with `regerrs.h` being a textual mirror.
  [from-comment]

## Potential issues

- `REG_UPBOTCH` comment ("legal per spec, but that was a mistake")
  hints that POSIX itself has the quirk; not actionable but worth
  flagging when reviewing regex error messages. [ISSUE-doc-drift:
  POSIX-quirk note buried in re_info bit comment (nit)]
- `pg_regoff_t` is `long` — "it's only a guess that long is
  suitable" per the comment. On Windows long is 32-bit even on
  64-bit builds, which would silently cap match offsets at 2 GB.
  [ISSUE-correctness: pg_regoff_t = long is 32-bit on Win64
  (maybe)]
- Multiple `REG_*` flag bits are still labeled "none of your
  business" (`REG_DUMP`, `REG_FAKE`, `REG_PROGRESS`, `REG_FTRACE`,
  `REG_MTRACE`, `REG_SMALL`) — opaque debug bits from the upstream
  Spencer code that PG carries forward. [ISSUE-stale-todo:
  undocumented debug bits inherited from Spencer (nit)]
