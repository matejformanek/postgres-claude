---
path: src/test/modules/test_regex/test_regex.c
anchor_sha: e18b0cb7344
loc: 762
depth: read
---

# src/test/modules/test_regex/test_regex.c

## Purpose

White-box test harness for PostgreSQL's Spencer-based regex engine
(`src/backend/regex/`). Mirrors the public `regexp_matches` plumbing
but exposes the diagnostic `re_info` bits, the indices-vs-strings
output mode, and the "partial match" semantics so the regression suite
can compare engine output against the reference Tcl/Henry-Spencer test
oracle. Returns matches as a set of `text[]` arrays; the first row is
always the `re_info` summary, equivalent to Tcl's `regexp -about`.
`[verified-by-code]` `test_regex.c:72-77,116-119`

## Public symbols

| Symbol | Site | Notes |
|---|---|---|
| `test_regex(pattern text, string text, flags text) returns setof text[]` | `:80` | SRF; first row is regex info, subsequent rows are match groups |

## Internal landmarks

- `test_re_flags` (`:27-35`) — captures the parsed flags string into
  `cflags` / `eflags` / `info` / `glob` / `indices` / `partial`.
- `test_regex_ctx` (`:38-55`) — cross-call SRF state: compiled
  `rm_detail_t`, the original `text` string, match locations as 0-based
  char indexes, scratch arrays for building each result row, the
  wide-char string used by the regex engine, and an MB conversion
  buffer.
- `parse_test_flags` (`:158`) — translates the user's flags-string
  characters into Spencer cflags/eflags + behavior flags.
- `test_re_compile` (`:199`) — wraps `pg_regcomp`, raising a PG error
  on compile failure with a readable diagnostic.
- `setup_test_matches` (`:433`) — drives `pg_regexec` in a loop,
  recording start/end char indexes for each match × subpattern,
  honoring `glob` and `partial` semantics.
- `build_test_info_result` (`:616`) — formats Spencer's `re_info` bits
  (REG_UBACKREF, REG_ULOOKAROUND, REG_UBOUNDS, etc.) as a `text[]` for
  the first SRF row.
- `build_test_match_result` (`:690`) — for each match, returns either
  the substring or its `[start, end]` indices per `indices` flag.

## Invariants & gotchas

- TEST MODULE — exercises engine internals; SQL-callable only.
- The regex engine stores patterns as `pg_wchar`; the test must convert
  back to MB-encoded bytes for output, which is why `wide_str` and
  `conv_buf` live in the SRF context.
- `npatterns` is the number of capturing subpatterns + 1 (for the
  whole match); `elems` / `nulls` are sized `npatterns + 1` accordingly
  (`:50-51`).
- Comment block on `test_regex` (`:71-77`) explicitly notes the
  implementation is "largely based on `regexp.c`'s `regexp_matches`,
  with additions for debugging".
- Flag-string parsing is permissive but compile failures are hard
  errors — invalid patterns ERROR rather than returning empty.

## Cross-refs

- `source/src/backend/regex/` — Henry Spencer's regex engine.
- `source/src/include/regex/regex.h` — `regex_t`, `pg_regcomp`,
  `pg_regexec`, `rm_detail_t`, `REG_*` cflags/eflags.
- `source/src/backend/utils/adt/regexp.c` — `regexp_matches`, the
  production SRF this test mirrors.
