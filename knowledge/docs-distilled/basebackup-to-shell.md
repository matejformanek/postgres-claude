---
source_url: https://www.postgresql.org/docs/current/basebackup-to-shell.html
fetched_at: 2026-07-16
anchor_sha: 572c3b2ddf8c
module: contrib/basebackup_to_shell
---

# basebackup_to_shell — a custom `pg_basebackup --target`

The reference example for the **server-side basebackup target API**
(`BaseBackupAddTarget`): it registers a `shell` target so that
`pg_basebackup --target=shell[:DETAIL]` streams each tar archive to the stdin
of an admin-configured shell command instead of to the client. The example
that teaches you how to write your own backup sink (S3, tape, dedup store).
Author: Robert Haas.

## Non-obvious claims

- Must be in `shared_preload_libraries` or `local_preload_libraries`; its
  `_PG_init` calls `BaseBackupAddTarget("shell", shell_check_detail,
  shell_get_sink)` to register the target with the core basebackup machinery.
  `[verified-by-code source/contrib/basebackup_to_shell/basebackup_to_shell.c:71,93]`
- Two GUCs, both `DefineCustomStringVariable`:
  - `basebackup_to_shell.command` — the shell command run once per archive,
    archive piped to its **stdin**.
  - `basebackup_to_shell.required_role` — role a user must belong to before
    they may select the `shell` target; empty ⇒ any replication user may use
    it. `[verified-by-code source/contrib/basebackup_to_shell/basebackup_to_shell.c:73,82]`
- The required-role check runs at target-selection time in
  `shell_check_detail`: if `shell_required_role` is non-empty it resolves the
  role OID and enforces `has_privs_of_role(GetUserId(), roleid)` — reusing the
  standard role-membership predicate, so `pg_read_all_settings`-style
  inheritance rules apply. `[verified-by-code source/contrib/basebackup_to_shell/basebackup_to_shell.c:104-110]`
- Command-string placeholders:
  - `%f` → current archive filename (e.g. `base.tar`, `<tablespaceoid>.tar`),
    substituted per-archive at sink startup.
  - `%d` → the user-supplied **target detail** (the part after `shell:`).
  - `%%` → literal `%`; any other `%x` is an error.
  `[verified-by-code source/contrib/basebackup_to_shell/basebackup_to_shell.c:124,253,263]`
- **`%d` presence is a strict two-way contract:** if the command contains `%d`,
  a target detail is *required*; if it does not, supplying a detail is
  *rejected*. Both are hard `errmsg` errors, checked by scanning the command
  for `%d` at sink open. `[verified-by-code source/contrib/basebackup_to_shell/basebackup_to_shell.c:151-171]`
- **Security model:** the command runs server-side as the postgres OS user
  (effectively superuser-equivalent power), so the module is deliberately
  built so a *replication* user cannot pick arbitrary commands — the command
  is fixed by the admin GUC, and the only user-controlled input (`%d`) is
  documented to be restricted to alphanumerics to keep it out of shell
  metacharacter territory. Access is further gated by `required_role`.
  `[from-README][verified-by-code shell_check_detail role gate:104-110]`
- The current command value is snapshotted into the sink at open
  (`sink->shell_command = pstrdup(shell_command)`), so a mid-backup
  `SIGHUP`/`SET` of the GUC does not change the command for an in-flight
  backup. `[verified-by-code source/contrib/basebackup_to_shell/basebackup_to_shell.c:143]`

## Worked example (from the docs page)

```ini
# postgresql.conf
shared_preload_libraries = 'basebackup_to_shell'
basebackup_to_shell.command = 'aws s3 cp - s3://mybucket/%f'
```
```bash
pg_basebackup --target=shell:s3bucket     # DETAIL "s3bucket" → %d
```

## Links into corpus

- Base-backup server code + the target sink abstraction (`bbsink`,
  `BaseBackupAddTarget`): lives in `src/backend/backup/` — see
  `[[knowledge/docs-distilled/app-pgbasebackup.md]]` for the client side and
  `[[knowledge/docs-distilled/protocol-replication.md]]` for the
  BASE_BACKUP replication command that carries `TARGET`/`TARGET_DETAIL`.
- Custom-GUC registration pattern (`DefineCustomStringVariable`, preload
  timing): `[[knowledge/docs-distilled/extend-extensions.md]]`.
- Role-membership predicate `has_privs_of_role`:
  `[[knowledge/docs-distilled/role-membership.md]]`,
  `[[knowledge/docs-distilled/predefined-roles.md]]`.
