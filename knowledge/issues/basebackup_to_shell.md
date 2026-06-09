# Issues — `contrib/basebackup_to_shell`

Base-backup shell-out target module (operator-configured archive command for base backups). 1 source file / ~376 LOC.

**Parent docs:** `knowledge/files/contrib/basebackup_to_shell/basebackup_to_shell.c.md`.

**Source:** 3 entries surfaced 2026-06-09 by A14-2.

## Headlines

1. **Substitution model relies on a fragile per-escape convention** — `%d` is alphanumeric-only because the only allowed value is target. A future `%`-escape sourced from client-controlled data would silently bypass the check that today protects `%d`. The current code is safe, but the design is fragile.
2. **`required_role` defaults empty** — out-of-the-box ANY role with REPLICATION can fire the operator's shell command.
3. Alphanumeric-only `%d` rejects safe values like UUIDs / dotted IDs — restrictive by design.

## Entries — `basebackup_to_shell.c`

- [ISSUE-defense-in-depth: substitution model relies on a fragile per-escape convention; not enforced (likely)] — `:211-217` — future `%`-escapes from client data would silently break the safety model.
- [ISSUE-defense-in-depth: `required_role` defaults empty; any REPLICATION role can fire shell cmd (maybe)] — `:67-68,104-115`
- [ISSUE-documentation: alphanumeric-only `%d` rejects safe values like UUIDs/dotted IDs (nit)] — `:181-202` — restrictive by design.

## Cross-sweep references

- A8 archive_command — "load arbitrary code from untrusted name" cluster origin.
- A14 basic_archive — sister module; both shell out, both have admin-set GUC.
- A11 postgres_fdw — gold-standard cross-cluster trust pattern (the contrast: postgres_fdw has TWO layers of `require_password`; basebackup_to_shell has ONE).
