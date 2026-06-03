---
path: src/bin/pg_dump/dumputils.h
anchor_sha: 4b0bf0788b0
loc: 72
depth: read
---

# dumputils.h

- **Source path:** `source/src/bin/pg_dump/dumputils.h`
- **Lines:** 72
- **Last verified commit:** `4b0bf0788b0`
- **Companion files:** `dumputils.c` (implementations), `fe_utils/string_utils.h` (where `fmtId`/`fmtQualifiedId`/`appendStringLiteralConn` actually live — this header does NOT re-expose them).

## Purpose

Extern declarations for the ten non-static functions of `dumputils.c`. Also defines `PGDUMP_STRFTIME_FMT` — the timestamp format used in TOC headers, which differs Windows vs non-Windows because Windows `%Z` produces localized timezone names that may break the dump-script encoding. [from-comment, dumputils.h:21-37]

## Public surface

- Macro `PGDUMP_STRFTIME_FMT` (34/36) — `"%Y-%m-%d %H:%M:%S %Z"` on Unix, `"%Y-%m-%d %H:%M:%S"` (no `%Z`) on Windows. [verified-by-code, dumputils.h:33-37]
- `sanitize_line(str, want_hyphen)` — newline scrubber.
- `buildACLCommands(name, subname, nspname, type, acls, baseacls, owner, prefix, remoteVersion, sql)` — GRANT/REVOKE emitter. **`name` and `subname` MUST already be quoted by the caller.** [from-comment, dumputils.c:75-78]
- `buildDefaultACLCommands(type, nspname, acls, acldefault, owner, remoteVersion, sql)` — wrapper for ALTER DEFAULT PRIVILEGES.
- `quoteAclUserName(output, input)` — backend-matching putid()-style role name quoting.
- `buildShSecLabelQuery(catalog_name, objectId, sql)` / `emitShSecLabels(conn, res, buffer, objtype, objname)` — SECURITY LABEL pair for shared objects.
- `variable_is_guc_list_quote(name)` — bool, hard-coded list.
- `SplitGUCList(rawstring, separator, ***namelist)` — overwrites input; collapses `""`.
- `makeAlterConfigCommand(conn, configitem, type, name, type2, name2, buf)` — ALTER ROLE/DATABASE SET emitter.
- `create_or_open_dir(dirname)` — directory-format archive directory.
- `generate_restrict_key()` / `valid_restrict_key(key)` — psql `\restrict` token.

[verified-by-code, dumputils.h:40-70]

## Phase D — surfaces of concern

- **The header does NOT re-export `fmtId`.** Callers of `buildACLCommands` must independently `#include "fe_utils/string_utils.h"` to get `fmtId` for pre-quoting names. This split is the root of the "name is already quoted" caller contract. [verified-by-code, dumputils.h:1-72] [maybe]
- **`generate_restrict_key` returns a `char *`** but the caller has no way to know the length without checking `valid_restrict_key`. Length is implicitly 63 chars + `\0` (see dumputils.c:978-991). [verified-by-code, dumputils.c:978-991] [no concern]
- **No `pg_attribute_*` annotations.** None of the prototypes carry printf/noreturn hints; these are not format-string functions, so this is fine. [verified-by-code, dumputils.h:40-70] [no concern]

## Cross-references

- Implementation: `knowledge/files/src/bin/pg_dump/dumputils.c.md`.
- For `fmtId` see `source/src/fe_utils/string_utils.{c,h}`.

## Confidence tag tally
`[verified-by-code]=4 [from-comment]=2 [maybe]=1 [no concern]=2`
