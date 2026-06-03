---
path: src/bin/psql/mainloop.h
anchor_sha: 4b0bf0788b0
loc: 17
depth: header
---

# mainloop.h

- **Source path:** `source/src/bin/psql/mainloop.h`
- **Lines:** 17
- **Last verified commit:** `4b0bf0788b0`
- **Companion file:** `mainloop.c` (662 lines; the read-parse-execute loop).

## Purpose

Two-symbol surface: the `MainLoop(FILE*)` entry point and the `psqlscan_callbacks` table the flex lexer needs in order to expand `:var` references. [verified-by-code, mainloop.h:1-17]

## Surface

- `psqlscan_callbacks` (13) — a `const PsqlScanCallbacks` initialised in mainloop.c to wire `psql_get_variable` (from common.c) into the lexer. [verified-by-code, mainloop.c:20-22]
- `MainLoop(source)` (15) — the REPL. Re-entrant: called recursively by `process_file` for `\i`, and by `startup.c::main` with `stdin`. Returns one of `EXIT_SUCCESS`, `EXIT_FAILURE`, `EXIT_USER`, `EXIT_BADCONN`. [verified-by-code, mainloop.c:32-662; startup.c:471]

## Phase D notes

Nothing direct. The fact that `psqlscan_callbacks` is exposed (rather than mainloop owning it privately) means `startup.c` can build a transient scan state for `-c \foo` actions using the same variable-resolution callback. [verified-by-code, startup.c:406-407]

## Cross-references

- `mainloop.c` — the implementation.
- `startup.c:407` — second user of `psqlscan_callbacks`.

## Confidence tally

`[verified-by-code]=3`
