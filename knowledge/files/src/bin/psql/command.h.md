---
path: src/bin/psql/command.h
anchor_sha: 4b0bf0788b0
loc: 49
depth: header
---

# command.h

- **Source path:** `source/src/bin/psql/command.h`
- **Lines:** 49
- **Last verified commit:** `4b0bf0788b0`
- **Companion file:** `command.c` (the implementation, 6571 lines).

## Purpose

Public interface for backslash-command dispatch. Defines the `backslashResult` enum that `MainLoop` uses to decide what to do after each `\foo` and declares the entry points called from `mainloop.c`, `startup.c`, and `copy.c`. [verified-by-code, command.h:1-49]

## Surface

### `backslashResult` enum (15)

[verified-by-code, command.h:15-24]

- `PSQL_CMD_UNKNOWN` — sentinel; only valid before dispatch completes.
- `PSQL_CMD_SEND` — query buffer is complete, mainloop should call `SendQuery`.
- `PSQL_CMD_SKIP_LINE` — backslash command consumed; keep accumulating query text.
- `PSQL_CMD_TERMINATE` — `\q` (or similar) — quit psql.
- `PSQL_CMD_NEWEDIT` — `\e`/`\ef`/`\ev` rewrote the buffer; mainloop must rescan it.
- `PSQL_CMD_ERROR` — backslash command failed (used by `ON_ERROR_STOP` logic).

### Externs

- `HandleSlashCmds(scan_state, cstack, query_buf, previous_buf)` (27) — the top-level entry, called by `MainLoop` and `startup.c` for `-c \foo`. `query_buf`/`previous_buf` may be NULL when handling a `-c` action. [verified-by-code, command.h:27-30; command.c:230-304]
- `process_file(filename, use_relative_path)` (32) — handler for `\i` / `\ir`; also called by `process_psqlrc_file` and the `-f` option. [verified-by-code, command.h:32; command.c:4924-4987]
- `do_pset(param, value, popt, quiet)` (34) — programmatic interface to the `\pset` machinery. Called from `-P` option (startup.c:617) and from many `exec_command_*` shortcuts (`\a`, `\t`, `\T`, `\x`, `\f`). [verified-by-code, command.h:34-37; command.c:5078]
- `savePsetInfo` / `restorePsetInfo` (39, 41) — snapshot/restore the printQueryOpt around `\g (...)` option overrides. [verified-by-code, command.h:39-41]
- `connection_warnings(in_startup)` (43) — version banner + SSL/GSS/Win32-codepage warnings. Called after every connect. [verified-by-code, command.h:43; command.c:4442-4493]
- `SyncVariables` / `UnsyncVariables` (45, 47) — push connection state into psql variables (`USER`, `HOST`, `PORT`, `ENCODING`, …) and clear them on connection loss. [verified-by-code, command.h:45-47; command.c:4565-4637]

## Includes pulled in

- `fe_utils/conditional.h` — `ConditionalStack` for `\if`.
- `fe_utils/print.h` — `printQueryOpt`.
- `fe_utils/psqlscan.h` — `PsqlScanState`.

## Phase D notes

Header-only; no Phase D surface beyond exposing the dispatch contract. The fact that `query_buf` / `previous_buf` can be NULL in the `-c` case is load-bearing for `copy_previous_query` (command.c:3848) — a buggy backslash handler that dereferences `query_buf` would crash in `-c \foo` mode. [inferred from header comment + command.c:489]

## Cross-references

- `command.c` — implements everything declared here.
- `startup.c` — calls `HandleSlashCmds` for `-c \foo` actions (startup.c:413).
- `mainloop.c` — calls `HandleSlashCmds` on every `PSCAN_BACKSLASH` token (mainloop.c:496).
- `knowledge/files/src/bin/psql/command.c.md` — the per-command audit.

## Confidence tally

`[verified-by-code]=8 [inferred]=1`
