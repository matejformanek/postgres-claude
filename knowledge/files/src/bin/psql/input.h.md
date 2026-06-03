---
path: src/bin/psql/input.h
anchor_sha: 4b0bf0788b0
loc: 60
depth: read
---

# input.h

- **Source path:** `source/src/bin/psql/input.h`
- **Lines:** 60
- **Last verified commit:** `4b0bf0788b0`
- **Companion files:** `input.c` (implementation), `tab-complete.c` (registers callbacks against readline), `mainloop.c` (caller).

## Purpose

Public surface for the readline-or-fgets input layer. Also handles the system-header pragma jiggery-pokery needed to silence warnings from readline's headers and to pick between `readline/`, `editline/`, and bare `readline.h` include layouts. [from-comment, input.h:17-44]

## Public surface

- `USE_READLINE` (18) — defined iff `HAVE_LIBREADLINE`. All readline-using code is guarded by this. [verified-by-code, input.h:17-18]
- `gets_interactive(prompt, query_buf)` (50) — primary input function. Returns malloc'd line.
- `gets_fromFile(source)` (51) — non-interactive variant.
- `initializeInput(int flags)` (53) — flag `1` enables readline+history.
- `printHistory(fname, pager)` (55) — `\s` command.
- `pg_append_history(s, history_buf)` / `pg_send_history(history_buf)` (57-58) — append-then-flush idiom so multi-line statements become one history entry.

[verified-by-code, input.h:50-58]

## Phase D notes

- **`HAVE_PRAGMA_GCC_SYSTEM_HEADER`** suppresses warnings from inside readline headers — including `-Wstrict-prototypes` problems. Pragma scope is the rest of `input.h`. Cosmetic, no security concern. [from-comment, input.h:20-26] [no concern]
- The header doesn't expose history-file path resolution; that lives in `input.c::initializeInput`. See that doc for `PSQL_HISTORY` env-var handling. [verified-by-code, input.c:369-395]

## Confidence tag tally
`[verified-by-code]=3 [from-comment]=2 [no concern]=1`
