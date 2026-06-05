---
path: src/include/fe_utils/query_utils.h
anchor_sha: 4b0bf0788b066a4ca1d4f959566678e44ec93422
loc: 24
depth: read
---

# `src/include/fe_utils/query_utils.h`

- **File:** `source/src/include/fe_utils/query_utils.h` (24 lines)
- **Last verified commit:** `4b0bf0788b066a4ca1d4f959566678e44ec93422` (2026-06-05)

## Purpose

Declares three thin wrappers frontend tools use to run a SQL string against a connection with
uniform echo + error handling: `executeQuery` (expects a result set), `executeCommand`
(fire-and-forget), and `executeMaintenanceCommand` (a fail-soft variant). Implementation in
[[knowledge/files/src/fe_utils/query_utils.c]]. `[from-comment]` (:1-11)

## Public symbols

| Symbol | Line | Role |
|---|---|---|
| `executeQuery` | :17 | Run `query`, echo if asked, return the `PGresult` (caller frees). |
| `executeCommand` | :19 | Run a command for side effects; exits on failure. |
| `executeMaintenanceCommand` | :21 | Run a command, return success bool instead of exiting (fail-soft). |

## Internal landmarks

- The split between `executeCommand` (exits on error) and `executeMaintenanceCommand` (returns
  a bool) is the key API distinction: tools that can recover from a failed maintenance command
  (e.g. try the next database) use the latter. `[inferred]`
- `executeQuery` returns the live `PGresult` to the caller (`:17`) — ownership transfers, so
  the caller must `PQclear` it; the void-returning `executeCommand` clears internally. `[inferred]`

## Invariants & gotchas

- `echo` on all three (`:17-22`) prints the SQL to stdout before running it — used by tool
  `--echo` flags; it does **not** sanitize the query, so callers are responsible for building
  injection-safe SQL upstream (via `string_utils.h` helpers). `[inferred]`
- `executeCommand` *exits the process* on failure (`:19`), which is why `parallel_slot.c`'s
  connect-then-initcmd path is leak-free today — see `knowledge/issues/fe_utils.md` row
  `parallel_slot.c:333`. `[verified-by-code]`

## Cross-refs

- Implementation: [[knowledge/files/src/fe_utils/query_utils.c]].
- Connection helpers: [[knowledge/files/src/include/fe_utils/connect_utils.h]].
- Injection-safe SQL construction: [[knowledge/files/src/include/fe_utils/string_utils.h]].

## Potential issues

None — minimal query-execution wrappers; the exit-on-failure behavior of `executeCommand` is
load-bearing for a downstream leak property already tracked against `parallel_slot.c`.
