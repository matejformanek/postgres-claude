---
path: src/common/restricted_token.c
anchor_sha: 4b0bf0788b0
loc: 174
depth: read
---

# restricted_token.c

- **Source path:** `source/src/common/restricted_token.c`
- **Lines:** 174
- **Last verified commit:** `4b0bf0788b0`
- **Companion files:** `common/restricted_token.h`, callers under `src/bin/initdb`, `src/bin/pg_ctl`, `src/bin/pg_upgrade`, `src/bin/pg_regress`.

## Purpose

Windows-only privilege drop. PG forbids the server (and most CLI tools) from running with full Administrator rights — those rights also disable some sanity checks for paths/permissions and break PG's own permission discipline. `get_restricted_token` re-executes the current process under a restricted token if it isn't already, sniffing the `PG_RESTRICT_EXEC` env var to avoid infinite recursion. On non-Windows the file compiles to a no-op `get_restricted_token`. [from-comment, restricted_token.c:124-128]

## Role in PG

Frontend-only (`#error` for backend builds, line 17-19). Called near the top of `main()` in initdb/pg_ctl/pg_upgrade/pg_regress.

## Key functions

- `get_restricted_token()` (128-174) — if `$PG_RESTRICT_EXEC != "1"`, copy `GetCommandLine()`, set the env var, call `CreateRestrictedProcess` on a duplicate of ourselves, wait for it, propagate exit code via `exit(x)`. If `CreateRestrictedProcess` fails, log the error and **fall through to the end of the function** (i.e. continue running un-restricted — fail-open). [verified-by-code, restricted_token.c:128-174]
- `CreateRestrictedProcess(cmd, *processInfo)` (44-121) — open current process token, build a SID list dropping `Administrators` + `Power Users` aliases, call `CreateRestrictedToken(DISABLE_MAX_PRIVILEGE, ...)`, add user to its DACL (skipped on Cygwin), `CreateProcessAsUser(CREATE_SUSPENDED)`, `ResumeThread`. Returns the token HANDLE (0 on failure). [verified-by-code, restricted_token.c:44-121]

## State / globals

- `static char *restrict_env` — set inside `get_restricted_token` from `getenv("PG_RESTRICT_EXEC")`. Pointer stays alive as long as the env var slot does. [verified-by-code, restricted_token.c:29,139]

## Phase D notes

- **Fail-open if the token API fails.** Comment at line 41 ("On any system not containing the required functions, do nothing but still report an error") and the fall-through after `pg_log_error("could not re-execute with restricted token: error code %lu", ...)` at line 153 mean: a hostile environment that breaks `CreateRestrictedProcess` (e.g. token policy denies the drop) lets the process keep running with original privileges. [verified-by-code, restricted_token.c:151-155] [ISSUE-trust-boundary: privilege-drop is best-effort; failure does not abort the caller (maybe)]
- **`PG_RESTRICT_EXEC` is a normal env var.** Any caller can set it to `"1"` before invoking the PG tool, suppressing the drop. Since the tool's own caller is whatever launches it, this is an intra-process trust call. [verified-by-code, restricted_token.c:139-140]
- **`GetCommandLine()` round-trip.** The re-exec passes the raw command line verbatim; quoting bugs in third-party launchers could survive across the re-exec. [inferred, restricted_token.c:147]
- **Drops only `Administrators` and `Power Users`.** Tokens carrying other privileged group memberships (e.g. domain admin) survive unless they overlap. [verified-by-code, restricted_token.c:67-72] [maybe — Phase D]

## Confidence tag tally
`[from-comment]=2 [verified-by-code]=8 [inferred]=1 [maybe]=2`

## Cross-references

<!-- issues:auto:begin -->
- [Issue register — `common`](../../../issues/common.md)
<!-- issues:auto:end -->
