---
path: src/include/fe_utils/connect_utils.h
anchor_sha: 4b0bf0788b066a4ca1d4f959566678e44ec93422
loc: 48
depth: read
---

# `src/include/fe_utils/connect_utils.h`

- **File:** `source/src/include/fe_utils/connect_utils.h` (48 lines)
- **Last verified commit:** `4b0bf0788b066a4ca1d4f959566678e44ec93422` (2026-06-05)

## Purpose

Declares the shared connect/disconnect helpers frontend tools use to open a libpq connection
with consistent password-prompt and error handling. Defines `trivalue` (the three-state
password-prompt flag) and `ConnParams` (the command-line connection parameters), plus
`connectDatabase`, `connectMaintenanceDatabase`, and `disconnectDatabase`. Implementation in
[[knowledge/files/src/fe_utils/connect_utils.c]]. `[from-comment]` (:1-9)

## Public symbols

| Symbol | Line | Role |
|---|---|---|
| `enum trivalue` | :17 | TRI_DEFAULT / TRI_NO / TRI_YES — encodes `-w`/`-W`/neither for password prompting. |
| `ConnParams` (`_connParams`) | :25 | dbname (may be a connstring) + host + port + user + `prompt_password` + `override_dbname`. |
| `connectDatabase` | :38 | Open a connection; handles password prompt + retry; `fail_ok` + `allow_password_reuse`. |
| `connectMaintenanceDatabase` | :43 | Connect to `postgres`/`template1` for tools that need a maintenance DB. |
| `disconnectDatabase` | :46 | `PQfinish` wrapper. |

## Internal landmarks

- `ConnParams.dbname` "may be a connstring" (`:28`) — a full `host=… dbname=…` keyword string,
  not just a database name; `override_dbname` (`:35`) replaces **only** the DB name within
  that connstring, leaving the rest intact. This is how `vacuumdb -d "connstr" mydb` works. `[from-comment]` (:33-35)
- `prompt_password` (`:32`) is the `trivalue` that drives whether `connectDatabase` pre-prompts
  for a password (`-W`), never prompts (`-w`), or prompts on demand after a failed attempt
  (default). `[verified-by-code]`

## Invariants & gotchas

- `allow_password_reuse` on `connectDatabase` (`:41`) lets a tool cache the password the user
  typed and reuse it for subsequent connections (e.g. parallel slots) without re-prompting.
  The cached plaintext password is `free()`d without zeroing on reuse-reset — a frontend
  secret-scrub property shared cluster-wide, tracked in `knowledge/issues/fe_utils.md` row
  `connect_utils.c:44`. `[verified-by-code]`
- `fail_ok` (`:40`) distinguishes "this connection failing is fatal" from "try another DB" —
  `connectMaintenanceDatabase` uses the latter to fall back across candidate maintenance DBs. `[inferred]`

## Cross-refs

- Implementation: [[knowledge/files/src/fe_utils/connect_utils.c]] (secret-scrub register row).
- Pool that consumes `ConnParams`: [[knowledge/files/src/include/fe_utils/parallel_slot.h]].

## Potential issues

None new at the header level — the password-reuse secret-scrub property is tracked against
`connect_utils.c` in `knowledge/issues/fe_utils.md`. Cross-linked.
