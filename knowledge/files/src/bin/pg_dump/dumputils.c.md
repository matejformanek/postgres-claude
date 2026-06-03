---
path: src/bin/pg_dump/dumputils.c
anchor_sha: 4b0bf0788b0
loc: 1005
depth: deep
---

# dumputils.c

- **Source path:** `source/src/bin/pg_dump/dumputils.c`
- **Lines:** 1005
- **Last verified commit:** `4b0bf0788b0`
- **Companion files:** `dumputils.h` (the externs), `fe_utils/string_utils.c` (where `fmtId`/`fmtIdEnc`/`fmtQualifiedId`/`appendStringLiteralConn`/`appendConnStrVal` actually live — this file consumes those), `pg_dump.c` and `pg_dumpall.c` (callers of ACL/GUC/security-label builders).

## Purpose

Cross-application (pg_dump + pg_dumpall) SQL-text construction helpers. The high-stakes routines are:

- `buildACLCommands` — GRANT/REVOKE emission from a server-supplied ACL array.
- `buildDefaultACLCommands` — ALTER DEFAULT PRIVILEGES emission.
- `makeAlterConfigCommand` — ALTER DATABASE/ROLE SET emission (parses `name=value` config items, handles GUC_LIST_QUOTE variables).
- `emitShSecLabels` / `buildShSecLabelQuery` — SECURITY LABEL emission for shared objects.
- `quoteAclUserName` / `dequoteAclUserName` — match-the-backend ACL identifier quoting.
- `sanitize_line` — strip newlines from TOC text to prevent ambiguous line parsing.
- `SplitGUCList`, `variable_is_guc_list_quote` — parse the comma-separated values of GUC_LIST_QUOTE variables.
- `generate_restrict_key` / `valid_restrict_key` — generate/validate the random key for psql's `\restrict`/`\unrestrict` (the dump-script jailbreak countermeasure).

[verified-by-code, dumputils.c:35-1005]

## fmtId discipline — Phase D critical reading

`fmtId(rawid)` returns a pointer to a **`getLocalPQExpBuffer()`** static-ish buffer that is REUSED on the next `fmtId`/`fmtIdEnc`/`fmtQualifiedId` call. [verified-by-code, fe_utils/string_utils.c:97-235, 248-251] On Windows, `parallel.c` swaps `getLocalPQExpBuffer` for `getThreadLocalPQExpBuffer` so threads don't trample each other. [verified-by-code, parallel.c:284-323, 935-938]

The consequence for THIS file: every `appendPQExpBuffer(..., "%s", fmtId(x))` must consume the result before the next `fmtId` call. The standard idiom is to break a "schema.name" into TWO appends, as at dumputils.c:710-715 with the comment `/* must use fmtId result before calling it again */`. [from-comment, dumputils.c:709]

This file has 16 in-source `fmtId` callsites. I audited every one for the static-buffer hazard:

- 226 / 234 — in `buildACLCommands` REVOKE branch: `fmtId(nspname)` is appended via `appendPQExpBuffer(buf, "%s.", fmtId(nspname))` and then on a DIFFERENT iteration / DIFFERENT line `fmtId(grantee->data)` is appended. Sequential, safe. [verified-by-code, dumputils.c:225-234]
- 290, 297, 304, 311, 318 — `buildACLCommands` GRANT branch. Same pattern: each `fmtId(...)` is folded into its own `appendPQExpBuffer` call before the next `fmtId` runs. The five callsites are sequential through the loop body, never two in one statement. [verified-by-code, dumputils.c:286-321]
- 383 / 385 — `buildDefaultACLCommands` prefix builder. Two appends, never two in one statement. [verified-by-code, dumputils.c:382-385]
- 712 / 715 — `emitShSecLabels`. Explicit two-append idiom with the cited comment. [verified-by-code, dumputils.c:709-716]
- 887 / 889 / 890 — `makeAlterConfigCommand`. Three separate `appendPQExpBuffer` invocations, one `fmtId` per call. [verified-by-code, dumputils.c:887-890]

**Result: every `fmtId` callsite in this file is correct.** No statement evaluates two `fmtId()` in one expression. [verified-by-code]

The `name` and `subname` parameters of `buildACLCommands` are **pre-quoted by the caller** (the function header comment explicitly says "in the form to use in the commands (already quoted)" and "beware of passing a fmtId() result directly as 'name' or 'subname', since this routine uses fmtId() internally"). [from-comment, dumputils.c:74-101] This means the caller is on the hook for quoting tables/columns/sequences. Audit of callers belongs in pg_dump.c / pg_dumpall.c docs.

## Public surface

- `sanitize_line(str, want_hyphen)` (52) — replaces `\n`/`\r` with space. Comment explicitly notes "This ensures each logical output line is in fact one physical output line, to prevent corruption of the dump (which could, in the worst case, present an SQL injection vulnerability if someone were to incautiously load a dump containing objects with maliciously crafted names)." [from-comment, dumputils.c:36-50]
- `buildACLCommands(name, subname, nspname, type, acls, baseacls, owner, prefix, remoteVersion, sql)` (104) — returns bool, false if ACL parse failed. Diff-and-emit between `acls` (server-current) and `baseacls` (default-or-initprivs). [verified-by-code, dumputils.c:103-350]
- `buildDefaultACLCommands(type, nspname, acls, acldefault, owner, remoteVersion, sql)` (366) — calls `buildACLCommands` with an ALTER DEFAULT PRIVILEGES prefix. [verified-by-code, dumputils.c:365-402]
- `quoteAclUserName(output, input)` (588) — appends a putid()-style-quoted role name. Same rules as backend's `acl.c::putid()`: quote unless `[A-Za-z0-9_]+`; double quotes inside the name are doubled. [verified-by-code, dumputils.c:587-613]
- `buildShSecLabelQuery(catalog_name, objectId, sql)` (681) — emits a SELECT against `pg_shseclabel`. `catalog_name` is interpolated raw via `%s` (it is a small enum of compile-time strings: `pg_database`, `pg_authid`, `pg_tablespace`, etc — verified by grep of pg_dump.c). `objectId` is an OID. [verified-by-code, dumputils.c:680-688]
- `emitShSecLabels(conn, res, buffer, objtype, objname)` (699) — emits `SECURITY LABEL FOR <provider> ON <objtype> <objname> IS <literal>`. `provider` and `objname` go through `fmtId`; `label` through `appendStringLiteralConn`. [verified-by-code, dumputils.c:698-719]
- `variable_is_guc_list_quote(name)` (733) — hard-coded list of seven GUC names. **Must be kept in sync with `guc_parameters.dat`.** [from-comment, dumputils.c:722-731]
- `SplitGUCList(rawstring, separator, ***namelist)` (768) — overwrites input; collapses `""` quote-quote pairs. [verified-by-code, dumputils.c:767-854]
- `makeAlterConfigCommand(conn, configitem, type, name, type2, name2, buf)` (868) — builds `ALTER <type> <fmtId(name)> [IN <type2> <fmtId(name2)>] SET <fmtId(varname)> TO …`. The value is either parsed via `SplitGUCList` + `appendStringLiteralConn` per element (for GUC_LIST_QUOTE) or fed as a single `appendStringLiteralConn`. [verified-by-code, dumputils.c:867-934]
- `create_or_open_dir(dirname)` (943) — wrapper over `pg_check_dir`/`mkdir`. [verified-by-code, dumputils.c:942-968]
- `generate_restrict_key()` (976) — 64-byte alphanumeric string from `pg_strong_random`. [verified-by-code, dumputils.c:975-993]
- `valid_restrict_key(key)` (1000) — `strspn` over `restrict_chars`. [verified-by-code, dumputils.c:999-1005]

## Static helpers

- `parseAclItem(item, type, name, subname, remoteVersion, grantee, grantor, privs, privswgo)` (423) — parses `username=privs/grantor` per the backend's `aclitemout` syntax. Big `CONVERT_PRIV` switch on `type`. `abort()` (559) on unknown object type — i.e. internal misuse, not data-driven. [verified-by-code, dumputils.c:422-581]
- `dequoteAclUserName(output, input)` (622) — companion to `quoteAclUserName`. `""` → `"`. Returns pointer to terminator or `=`. [verified-by-code, dumputils.c:621-655]
- `AddAcl(aclbuf, keyword, subname)` (661) — comma-separated privilege keyword list. [verified-by-code, dumputils.c:660-668]

## Phase D — surfaces of concern

- **`name`/`subname` in `buildACLCommands` are pre-quoted by the caller.** If a caller in `pg_dump.c` passes an unquoted server-derived name (or worse, a `%s` interpolation of one), the resulting `GRANT … ON <type> <unquoted>` becomes a SQL-injection vector at restore time. Auditing each caller belongs in the per-file doc for `pg_dump.c`. [from-comment, dumputils.c:75-78, 100-102] [Phase D concern — propagated to pg_dump.c]
- **`buildShSecLabelQuery` interpolates `catalog_name` raw.** Currently called only with compile-time strings; if a future caller passes a server-derived catalog name, it's an injection. The OID is constrained by `%u`. [verified-by-code, dumputils.c:684-687] [maybe]
- **`makeAlterConfigCommand` quoting of GUC name.** `fmtId(mine)` quotes the variable name from `configitem` — which is server-derived `pg_db_role_setting.setconfig` array elements. Quoting is correct (fmtId handles arbitrary text including embedded quotes). The VALUE goes through `appendStringLiteralConn` (full E-string escaping) or `SplitGUCList` + per-element `appendStringLiteralConn`. **Both paths are safe.** [verified-by-code, dumputils.c:886-933] [no concern]
- **`SplitGUCList` overwrites input** — the caller `makeAlterConfigCommand` passes `pos` (a pointer into a `pg_strdup`'d copy) so the original `configitem` is untouched. [verified-by-code, dumputils.c:768-771, 873-928] [no concern]
- **`quoteAclUserName` doubles `"` correctly** matching backend `putid`. [verified-by-code, dumputils.c:603-612]
- **`variable_is_guc_list_quote` is hard-coded.** If an extension declares its own GUC_LIST_QUOTE variable, this function returns false → its value is emitted as a single string literal which the server will then mis-parse on restore. **NOT a security issue, but a correctness one. The comment at 728-731 explicitly says "unsafe to use GUC_LIST_QUOTE for extension variables".** [from-comment, dumputils.c:727-731] [maybe — surfaces as a documented limitation]
- **`sanitize_line` does not quote.** The function header says "we currently don't bother to quote names, meaning that the name fields aren't automatically parseable". `pg_restore -L` examines only the dumpId. So an injected `\n` in an object name CAN'T smuggle a new TOC line because newlines are sanitized — but a `;` or `--` in the object name passes through into the SQL-comment line. SQL comments terminate at end-of-line, so a `--` in the comment is harmless. [verified-by-code, dumputils.c:51-69] [no concern, but the comment is the load-bearing reasoning]
- **ACL parse errors silently disable emission for one object.** `buildACLCommands` returns false on parse failure; the caller in `pg_dump.c::_printTocEntry` etc. typically pg_fatals. So a hostile ACL string that breaks `parseAclItem` aborts the entire dump rather than yielding a partial GRANT. [verified-by-code, dumputils.c:140-152, 218, 330] [no concern]
- **`generate_restrict_key` last byte is the NUL terminator** (line 990). But the loop `for (int i = 0; i < sizeof(buf) - 1; i++)` (984) writes 63 alphanumeric chars; the 64th is `\0`. The buffer is sized `palloc(sizeof(buf))` = 64 bytes. So a caller treating it as a 63-char key is fine. [verified-by-code, dumputils.c:978-991] [no concern]

## Cross-references

- All ACL/security-label/config emission in `pg_dump.c` and `pg_dumpall.c` funnels through this file.
- `fmtId` mechanics: `source/src/fe_utils/string_utils.c:97-251` — see also `knowledge/files/src/fe_utils/string_utils.c.md` (if/when written).
- See also `knowledge/files/src/bin/pg_dump/dumputils.h.md` (extern declarations).

## Open questions

- Whether the hard-coded `variable_is_guc_list_quote` list is fully in sync with `guc_parameters.dat` as of `4b0bf0788b0`. The comment explicitly says it must be — but no test asserts it. [unverified]
- Whether any caller in `pg_dump.c` violates the "name is already quoted" precondition of `buildACLCommands`. This is the single biggest residual Phase D question for pg_dump and demands a per-callsite audit of pg_dump.c. [unverified — flagged as ISSUE for the pg_dump.c per-file doc]

## Confidence tag tally
`[verified-by-code]=35 [from-comment]=8 [maybe]=3 [no concern]=6 [unverified]=2`
