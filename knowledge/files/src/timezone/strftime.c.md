---
path: src/timezone/strftime.c
anchor_sha: 4b0bf0788b066a4ca1d4f959566678e44ec93422
loc: 582
depth: read
---

# src/timezone/strftime.c

## Purpose

PostgreSQL's bundled `strftime(3)` — converts a broken-down `struct pg_tm` to a
formatted string using a `printf`-style time format. A lightly-PG-patched copy
of the UCB/tzcode `strftime`, supporting **only the C locale** (the `lc_time_T`
table is hard-coded English, `strftime.c:64-107`). The single public entry is
`pg_strftime`; the recursive `_fmt` does the work. Used by the backend to render
timestamps (notably in `log_line_prefix` and `timestamptz_to_str`-adjacent
paths) without depending on the platform `strftime`, whose locale behavior and
`%Z` handling vary. `[verified-by-code]`

## Public symbols

| Symbol | Site | Role |
|---|---|---|
| `size_t pg_strftime(char *s, size_t maxsize, const char *format, const struct pg_tm *t)` | `strftime.c:134` | Format `*t` into caller buffer `s`; returns byte count (excluding NUL) or 0 on overflow/overrun |

## Internal landmarks

- `_fmt` (`strftime.c:161-524`) — the format-char `switch`. Recurses for
  composite specs (`%c`→`c_fmt`, `%D`→`"%m/%d/%y"`, `%F`→`"%Y-%m-%d"`,
  `%R`/`%r`/`%T`, `%+`→`date_fmt`). The `%E`/`%O` locale-modifier prefixes are
  skipped via `goto label` (`:227-236`), falling through to the base spec.
- `_conv` (`strftime.c:526`) — numeric field formatter; `sprintf`s into a
  stack buffer sized `INT_STRLEN_MAXIMUM(int)+1` then `_add`s it.
- `_add` (`strftime.c:535`) — copies a string into the output, stopping at
  `ptlim` (the buffer end). The single bounds chokepoint: every byte written
  goes through `_add` or the literal-copy at `:521`, both guarded by `ptlim`.
- `_yconv` (`strftime.c:551`) — year formatter handling negative / >9999 years
  so that `%C`+`%y` concatenate to the same output as `%Y`.
- The ISO-8601 week/year block for `%V`/`%G`/`%g` (`strftime.c:332-421`) — the
  one genuinely intricate piece, with Markus Kuhn's week-01 definition quoted
  inline.

## Invariants & gotchas

- **Always NUL-terminates on failure (if `maxsize > 0`).** Unlike standard
  `strftime`, on buffer overrun `pg_strftime` writes `*s = '\0'` and returns 0
  (`strftime.c:142-155`) rather than leaving a possibly mis-encoded partial
  string. The header comment (`:121-132`) explains why this matters: `%Z` copies
  `t->tm_zone`, which **comes from outside and could contain multibyte bytes**
  even though the module is C-locale-only — truncating mid-character would
  produce invalid output, so it returns empty instead. This is a deliberate
  defensive choice worth preserving.
- `%z` derives the numeric offset from `t->tm_gmtoff` but returns nothing when
  `t->tm_isdst < 0` (`strftime.c:481-482`) — "offset unknown".
- `%Z` emits the empty string (not `"?"`) when `t->tm_zone == NULL`
  (`strftime.c:465-474`), per C99.
- Unknown conversion chars fall through `default` and the literal `%X` is copied
  verbatim (`strftime.c:508-521`), matching `printf(3)` behavior — no error.
- C-locale only: any future need for localized month/day names would mean
  diverging further from upstream tzcode. Don't.

## Potential issues

- **[ISSUE-undocumented-invariant: `pg_strftime` `%Z` is the one untrusted-input
  path]** `strftime.c:465-467` — `%Z` blindly `_add`s `t->tm_zone`, whose bytes
  originate from the TZif file / POSIX TZ string parsed in `localtime.c`. The
  overrun-returns-empty contract (`:121-132`, `_add`'s `ptlim` guard) is what
  bounds it; there is no length or charset validation of the abbreviation
  itself. Benign given the `_add` bound, but the trust boundary (zone-file
  string → format output) is only documented in a function-header comment, not
  at the call sites that pass attacker-influenceable `pg_tm`. Severity: nit.

## Cross-refs

- `knowledge/files/src/timezone/localtime.c.md` — produces the `struct pg_tm`
  (including `tm_zone`/`tm_gmtoff`) that `pg_strftime` formats.
- `knowledge/files/src/timezone/private.h.md` — `INT_STRLEN_MAXIMUM`,
  `MONSPERYEAR`, `DAYSPERWEEK`, `isleap_sum`.
- `knowledge/files/src/backend/utils/adt/datetime.c.md` — backend timestamp
  rendering; sibling formatter for the SQL `to_char` path.

<!-- issues:auto:begin -->
- [Issue register — `timezone`](../../../issues/timezone.md)
<!-- issues:auto:end -->
