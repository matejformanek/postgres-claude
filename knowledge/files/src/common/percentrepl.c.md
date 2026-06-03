# src/common/percentrepl.c

## Purpose

The variadic `%`-substitution helper used by GUCs that take command
templates: `archive_command`, `restore_command`,
`archive_cleanup_command`, `recovery_end_command`, and a few others.

## Role in PG

Shared **frontend + backend**. Backend uses it from
`pgarch_archiveXlog()` and `RestoreArchivedFile()`. Frontend
`pg_archivecleanup` uses it for the same templating semantics so
the cleanup tool agrees with the server.

## Key functions

- `char *replace_percent_placeholders(const char *instr,
  const char *param_name, const char *letters, ...)` —
  the only public function. Walks `instr`, copies bytes verbatim
  except for `%`-escapes:
  - `%%` → single `%` (`percentrepl.c:69-74`)
  - `%X` where X is in `letters` → corresponding `va_arg(ap, char *)`
    value, by `appendStringInfoString` (`percentrepl.c:89-127`)
  - `%X` where X is not in `letters`, OR the matching `va_arg` value
    is NULL → ereport(ERROR) (backend) or `pg_log_error` + `exit(1)`
    (frontend) (`percentrepl.c:114-127`)
  - Trailing `%` → same error path (`percentrepl.c:75-87`)

  Returns a palloc'd (or malloc'd, frontend) `StringInfoData.data`.

## State / globals

None.

## Phase D notes

**Shell-injection boundary.** The returned string is fed straight
to `system(3)` or `OpenPipeStream()` by the archive/restore command
machinery. This helper does NOT escape shell metacharacters;
substituting a placeholder value containing `'` / `;` / `$(...)` /
backticks would create the obvious injection — `cp %p /tmp/%f` with
`%f` = `foo; rm -rf $HOME` becomes a shell command. The current
contract is that the placeholder values (WAL filename `%f`, full
path `%p`, etc.) come from internal name-generators and are NEVER
attacker-controlled. This invariant is **not** enforced or
documented in this file.

The frontend path uses `pg_log_error` then `exit(1)` rather than
ereport. Note the early bailout uses `exit(1)` not `pg_log_fatal`,
so partial output may have been printed by the time the caller dies.

The function's docstring (`percentrepl.c:46-52`) notes it is meant
for "all values available, all string" use cases — not for log
prefixes (`log_line_prefix` has its own logic).

## Potential issues

`[ISSUE-injection: no shell-escaping of substituted values; depends
on caller never passing attacker-controlled values into the
substitution (maybe)]`

`[ISSUE-undocumented-invariant: the "no attacker-controlled
placeholder values" rule is not stated in this file or in
percentrepl.h. A future caller could miss it. (maybe)]`
