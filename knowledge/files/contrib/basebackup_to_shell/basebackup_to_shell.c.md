# contrib/basebackup_to_shell/basebackup_to_shell.c

**Pin:** `4b0bf0788b066a4ca1d4f959566678e44ec93422`
**LOC:** 376
**Verification depth:** full read

## Role

Implements a `pg_basebackup --target shell:DETAIL` backend by registering a
`bbsink` (base-backup sink) that pipes archive + manifest contents into an
operator-configured shell command (`basebackup_to_shell.command`), with
`%f` substituted to the current filename and `%d` to the user-supplied detail
string.  Conceptually parallel to `archive_command` for WAL: an
operator-trusted shell template parameterized with per-file fields.
[verified-by-code] `source/contrib/basebackup_to_shell/basebackup_to_shell.c:1-94`

## Public API

- `_PG_init()` — registers two GUCs and calls `BaseBackupAddTarget("shell",
  shell_check_detail, shell_get_sink)` to install the sink.
  [verified-by-code] `source/contrib/basebackup_to_shell/basebackup_to_shell.c:70-94`
- GUCs (both `PGC_SIGHUP`, postmaster-config only at SIGHUP-time):
  `basebackup_to_shell.command` (string), `basebackup_to_shell.required_role`
  (string).
  [verified-by-code] `source/contrib/basebackup_to_shell/basebackup_to_shell.c:73-89`
- Internal `bbsink_shell_ops` vtable wires the eight `bbsink` callbacks
  (`begin_archive`, `archive_contents`, `end_archive`, manifest equivalents,
  `begin/end_backup`, `cleanup`).
  [verified-by-code] `source/contrib/basebackup_to_shell/basebackup_to_shell.c:55-65`

## Invariants

- INV-1: `target_detail` (the `%d` substitution source) must be alphanumeric
  ONLY — the code rejects anything that isn't `[A-Za-z0-9]` to prevent shell
  metacharacters from being interpreted by `popen()`.
  [verified-by-code] `source/contrib/basebackup_to_shell/basebackup_to_shell.c:173-202`
- INV-2: `%d` and target_detail must agree: detail required iff command
  template contains `%d`.
  [verified-by-code] `source/contrib/basebackup_to_shell/basebackup_to_shell.c:151-171`
- INV-3: command template must be non-empty.
  [verified-by-code] `source/contrib/basebackup_to_shell/basebackup_to_shell.c:145-149`
- INV-4: If `basebackup_to_shell.required_role` is set, the invoking backend
  must be a member of that role; checked in `shell_check_detail` before any
  real work.
  [verified-by-code] `source/contrib/basebackup_to_shell/basebackup_to_shell.c:101-118`
- INV-5: The current value of `shell_command` is *captured at sink creation*
  via `pstrdup`, freezing the template for the lifetime of the backup so a
  concurrent SIGHUP can't mutate it mid-stream.
  [verified-by-code] `source/contrib/basebackup_to_shell/basebackup_to_shell.c:136-143`

## Notable internals

- Substitution uses the generic helper `replace_percent_placeholders(...,
  "df", target_detail, filename)` from `common/percentrepl`. This is the
  same helper used by `archive_command` and similar features.
  [verified-by-code] `source/contrib/basebackup_to_shell/basebackup_to_shell.c:211-217`
- Shell process is started via `OpenPipeStream(cmd, PG_BINARY_W)` (popen
  in write mode); ended via `ClosePipeStream(pipe)`, with non-zero
  pclose status producing an `ERRCODE_EXTERNAL_ROUTINE_EXCEPTION` ereport.
  [verified-by-code] `source/contrib/basebackup_to_shell/basebackup_to_shell.c:222-274`
- `fwrite` failures with `errno==EPIPE` call `shell_finish_command()` early
  to surface a useful child-side error (e.g. wrong destination) instead of
  a bare "Broken pipe" message.
  [verified-by-code] `source/contrib/basebackup_to_shell/basebackup_to_shell.c:286-303`
- One pipe per archive AND one pipe per manifest — `begin_manifest`
  spawns a fresh command with filename `"backup_manifest"`.
  [verified-by-code] `source/contrib/basebackup_to_shell/basebackup_to_shell.c:345-376`

## Trust-boundary / Phase-D surface

This module is **headline Phase-D material** — it executes operator-supplied
shell strings on the backend, blending two principals (the operator who
sets the GUC, and the role who triggers a backup):

1. **GUC scope is `PGC_SIGHUP` and DBA-only** [verified-by-code:78] —
   that means a regular (non-superuser) backend cannot mutate
   `basebackup_to_shell.command`. To exploit, the attacker would need
   filesystem write to `postgresql.conf` or `ALTER SYSTEM` (superuser).
   `MarkGUCPrefixReserved("basebackup_to_shell")` blocks third-party
   modules from re-using the namespace.
   [verified-by-code] `source/contrib/basebackup_to_shell/basebackup_to_shell.c:91`
2. **target_detail is the only attacker-controlled input** and is *validated
   to alphanumerics only* before any `popen` [verified-by-code:181-202],
   eliminating shell-injection via `%d`.  Whitespace, `$`, backtick, `;`,
   `&`, `|`, `\n`, `'`, `"`, `(`, `)` all rejected.
   **ISSUE-D1 (info)**: alphanumeric is restrictive enough to be safe but
   would also reject e.g. UUIDs with hyphens or backup-id strings with
   dots; this is by design but worth knowing for documentation purposes.
3. **filename (`%f`) substitution comes from the backup engine itself**, NOT
   from a client request — the names are the archive's internal tarfile
   names (e.g. `base.tar`, `pg_wal.tar`) plus `backup_manifest`. So `%f`
   is not directly attacker-controlled. However, **inferred**: if a
   future change exposed tablespace OIDs or symlink targets in the archive
   name, that would become a new vector — currently safe per the bbsink
   protocol naming.
   [inferred] from `bbsink_shell_begin_archive` at line 310-316 and
   `bbsink_shell_begin_manifest` at line 346-352.
4. **No restriction on the command working directory** — the popen-ed
   shell inherits the postmaster CWD. Output redirected by the command
   itself (e.g. `cat > /tmp/x`) lands wherever the postgres user can write.
   [from-comment]: the README documents this; the safety burden is on the
   operator who writes the command template.
5. **`required_role` is the protection against a role-with-pg_basebackup
   privileges (REPLICATION) triggering arbitrary backups**. Without it,
   any role with REPLICATION can use the `shell` target and cause the
   command template to execute (against benign filenames, but still
   executing once per archive + manifest).
   **ISSUE-D2 (note)**: `required_role` defaults to empty, meaning by
   default ANY user with REPLICATION can fire the shell command. That's
   the intended trade-off but a hardening default would be safer.
   [verified-by-code] `source/contrib/basebackup_to_shell/basebackup_to_shell.c:67-68,104-115`
6. **Substitution-quoting model**: `replace_percent_placeholders` does
   raw string substitution — it does NOT shell-quote the substituted
   value. Safety relies entirely on the alphanumeric-only check for `%d`
   and on `%f` being a fixed set of internal names.
   **ISSUE-D3 (medium)**: if a future template explicitly includes `%d`
   inside single quotes (e.g. `cp ... '/dest/%d/file'`), an alphanumeric
   detail string is still fine; but if a future maintainer added a new
   `%`-escape (say `%t` = tablespace name from client), the safety model
   would silently break. The convention "all `%`-escapes must be either
   internally generated OR alphanumeric-validated" is not documented as a
   per-escape contract anywhere in this file.
   [inferred] from `shell_construct_command` at line 211-217.

## Cross-refs

- `source/src/backend/backup/basebackup_target.c` — the
  `BaseBackupAddTarget` / `bbsink` registry side.
- `source/src/common/percentrepl.c` — `replace_percent_placeholders`.
- A8: `archive_command` (cousin pattern — operator-supplied shell template
  invoked by backend processes with `%`-substitutions).
- A6: `LOAD`/`dlopen` patterns — alternative way to wedge arbitrary code
  into the backend via operator-trusted path.

## Issues raised

- **ISSUE-D1 (info)** — alphanumeric-only detail blocks safe values
  (UUIDs with hyphens, dotted IDs). By design.
- **ISSUE-D2 (note, low severity)** — `basebackup_to_shell.required_role`
  default empty allows any REPLICATION role to fire the shell command.
- **ISSUE-D3 (medium)** — substitution model is "raw string concat";
  safety depends on a fragile convention that future `%`-escapes will
  either be internally generated or alphanumeric-validated. Not enforced
  by a per-escape contract.

## Synthesized by
<!-- backlinks:auto -->
- [subsystems/contrib-basebackup_to_shell.md](../../../subsystems/contrib-basebackup_to_shell.md)
