# seclabel.c

- **Source path:** `source/src/backend/commands/seclabel.c`
- **Lines:** 592
- **Last verified commit:** `ef6a95c7c64`

## Purpose

"Routines to support security label feature." [from-comment, seclabel.c:3-4] SECURITY LABEL FOR provider ON object IS 'label' — attach an arbitrary string from a registered "provider" to any object. Used primarily by sepgsql.

## Public surface

- `ExecSecLabelStmt` — top-level entry.
- `GetSecurityLabel`, `SetSecurityLabel`, `DeleteSecurityLabel`, `DeleteSharedSecurityLabel` — catalog mutators on pg_seclabel / pg_shseclabel.
- `register_label_provider` — called at extension `_PG_init` time; sepgsql does this so the database accepts `SECURITY LABEL FOR selinux ...`.

## Provider list

Internal `label_provider_list` is built at startup as extensions register themselves. Each provider supplies a `check_object_relabel_type` hook that gets called when a label is set — the provider can reject the label format. Unknown provider names always error.

## Confidence tag tally

`[verified-by-code]=3 [from-comment]=1`
