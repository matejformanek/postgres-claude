---
path: src/include/common/restricted_token.h
anchor_sha: 4b0bf0788b0
loc: 24
depth: skim
---

# restricted_token.h

- **Source path:** `source/src/include/common/restricted_token.h`
- **Lines:** 24
- **Last verified commit:** `4b0bf0788b0`
- **Companion file:** `common/restricted_token.c`.

## Purpose

Two-symbol Windows-privilege-drop API used by frontend tools (`initdb`, `pg_ctl`, `pg_upgrade`, …) that must not run as Administrator. On non-Windows, `get_restricted_token` is a no-op. [from-comment, restricted_token.h:13-17]

## Public surface

- `get_restricted_token(void)` — Windows: re-exec ourselves inside a restricted token if `$PG_RESTRICT_EXEC != "1"`. Non-Windows: nothing. [verified-by-code, restricted_token.h:17]
- `CreateRestrictedProcess(cmd, *processInfo)` — Windows-only helper that does the actual token + `CreateProcessAsUser`. [verified-by-code, restricted_token.h:19-22]

## Phase D notes

- Privilege-drop boundary. See `restricted_token.c.md` for the fail-open analysis.

## Confidence tag tally
`[from-comment]=1 [verified-by-code]=2`
