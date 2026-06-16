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

## Issues

[ISSUE-trust-boundary: `get_restricted_token` (`restricted_token.h:17`)
returns `void`; on Windows it CANNOT signal failure to the caller.
A6's pg_upgrade finding: if `CreateRestrictedToken` fails, the
helper logs a warning but the binary continues running as
Administrator — fail-open privilege drop (high)] The header gives
no failure model. Compare to setuid(2)-style "check the return".

[ISSUE-undocumented-invariant: `$PG_RESTRICT_EXEC` environment
variable controls the re-exec logic — entirely undocumented at the
header level (low)] An attacker who can set the env var in the
parent process can skip the privilege drop entirely.

[ISSUE-trust-boundary: `CreateRestrictedProcess(cmd, *processInfo)`
(`restricted_token.h:21`) takes a `char *cmd` passed to
`CreateProcessAsUser` — Windows command-line parsing rules apply,
including quoted-path-with-spaces ambiguity (low)] Header has no
escaping contract.

## Cross-refs

- A5 `common.md` — fail-open privilege drop.
- A6 `pg_upgrade` — Windows execution path.
- Companion: `src/common/restricted_token.c.md`.

<!-- issues:auto:begin -->
- [Issue register — `include-common`](../../../../issues/include-common.md)
<!-- issues:auto:end -->

## Confidence tag tally
`[from-comment]=1 [verified-by-code]=2`
