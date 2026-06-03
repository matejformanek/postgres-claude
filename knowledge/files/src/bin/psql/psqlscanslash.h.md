---
path: src/bin/psql/psqlscanslash.h
anchor_sha: 4b0bf0788b0
loc: 40
depth: read
---

# psqlscanslash.h

- **Source path:** `source/src/bin/psql/psqlscanslash.h`
- **Lines:** 40
- **Last verified commit:** `4b0bf0788b0`
- **Companion files:** `psqlscanslash.l` (the flex source that generates `psqlscanslash.c`), `fe_utils/psqlscan.h` (the shared scanner state).

## Purpose

Public interface for the flex-generated `\meta-command` argument scanner. Backslash-command argument parsing is more elaborate than `strtokx`: it must handle SQL identifiers, file-or-pipe args, and "whole rest of line" args, and it must interoperate with the main `psqlscan.l` SQL scanner via shared `PsqlScanState`.

## Public surface

- `enum slash_option_type` (15) — four flavors of argument parsing:
  - `OT_NORMAL` — generic argument.
  - `OT_SQLID` — SQL identifier; will dequote and downcase per PG rules.
  - `OT_SQLIDHACK` — SQL identifier but DO NOT downcase (used where the meta-command needs to preserve case).
  - `OT_FILEPIPE` — filename or `|pipe-command`. Triggers shell-style expansion paths.
  - `OT_WHOLE_LINE` — grab everything to end-of-line untouched.
  [verified-by-code, psqlscanslash.h:14-22]
- `psql_scan_slash_command(state)` (25) — return the command name (the word after the `\`).
- `psql_scan_slash_option(state, type, *quote, semicolon)` (27) — return the next argument; `*quote` (if non-NULL) gets the quoting character used, or `0` for none.
- `psql_scan_slash_command_end(state)` (32) — consume trailing input up to `\n` / `;` boundary.
- `psql_scan_get_paren_depth(state)` / `psql_scan_set_paren_depth(state, depth)` (34, 36) — paren-depth book-keeping passed back and forth with the SQL scanner.
- `dequote_downcase_identifier(str, downcase, encoding)` (38) — in-place identifier normalization. Used by `crosstabview.c::indexOfColumn` too. [verified-by-code, crosstabview.c:657]

## Phase D notes

- `OT_FILEPIPE` flag is the gateway for `\copy`/`\g`/`\o`-style file/pipe redirection. The header doesn't enforce anything about the contents — every meta-command implementation must check whether shelling out is even allowed (e.g. `\copy` runs psql-side; a `|cmd` is `popen()` on the user's machine). The actual safety boundary is "psql is running as YOU, so it's always allowed", which is psql's overall security model. [from-comment, psqlscanslash.h:21] [no concern — by design]
- `OT_WHOLE_LINE` — used by `\!` (shell escape), `\sf`/`\sv` source-fetch, and a few others. Whatever the user types after the meta-command name goes to `system()` (for `\!`) or is treated as a SQL identifier (for `\sf`). Standard psql trust model. [inferred, psqlscanslash.h:21] [no concern — by design]

## Confidence tag tally
`[verified-by-code]=2 [from-comment]=1 [inferred]=1 [no concern]=2`
