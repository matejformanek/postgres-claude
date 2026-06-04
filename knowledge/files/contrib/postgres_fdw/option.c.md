# option.c

## One-line summary

postgres_fdw FDW / SERVER / USER MAPPING / FOREIGN TABLE option allowlist + validator: builds a single static `postgres_fdw_options` array (libpq options ∪ FDW-specific options) at first use, validates each `DefElem` against it on every `CREATE / ALTER`, plus the GUC `postgres_fdw.application_name` and the `%a/%c/%C/%d/%p/%u` expansion that gets it onto the remote server.

## Public API / entry points

- `Datum postgres_fdw_validator(PG_FUNCTION_ARGS)` (line 65, `PG_FUNCTION_INFO_V1`) — SQL-callable validator referenced by `postgres_fdw.control` / `postgres_fdw--1.0.sql`. Invoked by core during `CREATE FOREIGN DATA WRAPPER`, `CREATE SERVER`, `CREATE USER MAPPING`, `CREATE FOREIGN TABLE`, and the matching `ALTER` variants.
- `int ExtractConnectionOptions(List *defelems, const char **keywords, const char **values)` (line 419) — caller-allocated arrays. Filters `defelems` keeping only libpq-known options. Returns count.
- `List *ExtractExtensionList(const char *extensionsString, bool warnOnMissing)` (line 449) — parses the comma-separated `extensions` server option into a list of extension OIDs; the result feeds `PgFdwRelationInfo.shippable_extensions`.
- `char *process_pgfdw_appname(const char *appname)` (line 495) — expands `%a/%c/%C/%d/%p/%u` escapes against `application_name`, `MyStartTime.MyProcPid`, `cluster_name`, `MyProcPort->database_name`, `MyProcPid`, `MyProcPort->user_name`. Returns palloc'd.
- `void _PG_init(void)` (line 572) — module load; defines the `postgres_fdw.application_name` GUC (`PGC_USERSET`, no check hook) and calls `MarkGUCPrefixReserved("postgres_fdw")`.
- `char *pgfdw_application_name` — the GUC variable (line 46).

Internal:
- `InitPgFdwOptions(void)` (line 235) — builds the merged option list lazily and allocates it in `TopMemoryContext`.
- `is_valid_option(keyword, context)` (line 379) — linear scan.
- `is_libpq_option(keyword)` (line 398) — linear scan, only checks the `is_libpq_opt` flag.

## Key invariants

- INV-OPTLIST-INIT-ONCE: `InitPgFdwOptions` is idempotent (early return when `postgres_fdw_options != NULL` at line 304). The list lives in `TopMemoryContext` and survives all transaction boundaries — never freed. [verified-by-code]
- INV-PASSWORD-REQUIRED-SUPERUSER: only the superuser may set `password_required=false` on a USER MAPPING (line 194). A non-superuser may CLEAR the option (`pw_required=true`) on an ALTER. The check is hard-wired in the validator and cannot be bypassed by ALTER USER MAPPING ... OPTIONS (DROP password_required). [verified-by-code, security-critical]
- INV-SSLCERT-SSLKEY-SUPERUSER: at USER MAPPING context, `sslcert` / `sslkey` are superuser-only (line 200-208).
- INV-OAUTH-DISALLOWED: option keywords starting with `oauth_` are stripped from the allowlist entirely (lines 347-349 comment: "Disallow OAuth options for now, since the builtin flow communicates on stderr by default and can't cache tokens yet"). [from-comment + verified-by-code]
- INV-USER-CONTEXT-VS-SERVER-CONTEXT: libpq options where `*` appears in `dispchar` (the "secret" marker) AND `user` are USER MAPPING-only; everything else libpq-side is SERVER-only (lines 357-361).

## Notable internals

- The option allowlist is the **union** of:
  - All libpq options from `PQconndefaults()`, except `D`-debug options and the two postgres_fdw overrides (`fallback_application_name`, `client_encoding`) and the `oauth_*` family (lines 336-365).
  - The hand-rolled `non_libpq_options[]` table (lines 244-301).
  - Plus `sslcert`/`sslkey`/`gssdelegation` repeated explicitly so they're valid on USER MAPPING as well as the libpq-derived SERVER context (lines 287-298).
- `password_required` is validated at SET time: the check at line 194 is on the new value, not the old. A non-superuser cannot create a `password_required=false` mapping, but as the comment at lines 187-193 explicitly notes, they CAN clear it (set to true) because the validator doesn't see the old value during ALTER. That's intentional — clearing is harmless.
- `process_pgfdw_appname` `%C` expands to `cluster_name` (a regular GUC at the local side), `%a` to local `application_name`. **All "%" data comes from the local backend** — there is no remote-side substitution. The expanded string is sent to the remote in the libpq connection params.
- `_PG_init`'s GUC is `PGC_USERSET` with no `check_hook`. Comment at lines 575-582 explicitly defends letting `application_name` exceed NAMEDATALEN and contain non-ASCII: the REMOTE end truncates/sanitizes via libpq.
- `MarkGUCPrefixReserved("postgres_fdw")` at line 594 locks down the `postgres_fdw.*` namespace from squatting.

## Trust boundary / Phase D surface — the headline file

- **`password_required` is the load-bearing CVE-2023-5869 / similar primitive.** Two enforcement sites:
  - **At validation** (this file, line 194): `!superuser() && !pw_required → ERROR`. A non-superuser cannot CREATE or ALTER a user mapping with `password_required=false`. [verified-by-code]
  - **At connect** (`connection.c:759` `check_conn_params` AND `connection.c:446` `pgfdw_security_check`): if the connecting role is non-superuser AND no password was sent AND GSSAPI delegated creds absent AND SCRAM pass-through absent → ERROR. The `UserMappingPasswordRequired` lookup at `connection.c:705` reads back the option.
  - If a superuser created a user mapping with `password_required=false`, a non-superuser using that mapping **bypasses the password requirement** — that is the documented escape hatch, and the canonical loopback-bypasses-RLS attack class.
- **`sslcert`/`sslkey` at USER MAPPING** (lines 200-208): a non-superuser could otherwise read superuser-owned cert files via the postgres process. Hardened at validate time. Note: at SERVER context these are NOT superuser-only — a server-level cert is presumed to be the DBA's intent. Asymmetric on purpose.
- **No `sslmode` default-hardening**: `option.c` does not enforce a minimum `sslmode`. If neither server nor user mapping specifies it, libpq's default (`prefer`) is used. **Cross-cluster TLS is opt-in, downgrade-able.** A MITM on the LAN can strip TLS unless the DBA set `sslmode=require` or stronger.
- **No `connect_timeout` defaulting**: a hostile remote server can block the local backend on the SYN-ACK indefinitely (subject to OS TCP timeouts). Not a security bug per se, but a DoS amplification surface.
- **OAuth disallowed** (lines 347-349) — intentional sandbox: a remote that requests OAuth would otherwise force the postgres_fdw process to handle stderr-bound device-code flows.
- **`extensions` option is local-OID-list**: see `ExtractExtensionList`. Trust-class issue documented at `shippable.c.md`.
- **No quoting of option VALUES**: option values are libpq strings, validated only by libpq when the connection is made. A user-mapping value containing newlines, NULs, or `'` could in principle alter the connection string — but the canonical libpq connection-string parser handles quoting itself, and `postgres_fdw_connection` (the SQL function exposing the connection string) uses `appendEscapedValue` (`connection.c:2457`) to single-quote-escape backslashes and apostrophes.
- **`application_name` escape sequences**: `process_pgfdw_appname` is parsed by the LOCAL backend on every connection. There is no truncation here — the long string is shipped, and the REMOTE truncates. A long expanded `%C` value could in theory bloat the connection setup payload.

## Cross-references

- `source/contrib/postgres_fdw/connection.c:705` `UserMappingPasswordRequired` — reads `password_required` back.
- `source/contrib/postgres_fdw/connection.c:759` `check_conn_params` AND `:446` `pgfdw_security_check` — enforce `password_required`.
- `source/contrib/postgres_fdw/connection.c:494` `construct_connection_params` — uses `ExtractConnectionOptions` and `process_pgfdw_appname`.
- `source/contrib/dblink/dblink.c` — parallel `dblink_connstr_check` and `dblink_security_check` (referenced in comments at this file's lines 443 and 752-757).
- `source/src/backend/utils/misc/guc.c` — `MarkGUCPrefixReserved`.
- `source/src/backend/libpq/auth.c` + libpq client `fe-connect.c` — for `PQconndefaults` shape.

## Issues spotted

- [ISSUE-security: ALTER USER MAPPING does not let the validator see the OLD value; comment at lines 187-193 makes this explicit. Combined with the fact that DROP USER MAPPING + CREATE USER MAPPING is also subject to the password_required check, this is the correct behavior — but the asymmetry deserves a regression test. (nit — defensive)] — `source/contrib/postgres_fdw/option.c:187`.
- [ISSUE-security: no enforcement of minimum `sslmode`. `sslmode=disable` for a non-superuser USER MAPPING is silently accepted. Recommendation: optional GUC `postgres_fdw.min_sslmode` would harden cross-cluster postgres_fdw deployments. (maybe defense-in-depth)] — `source/contrib/postgres_fdw/option.c:244-301`.
- [ISSUE-security: `hostaddr` and `host` options are SERVER-level (assigned to `ForeignServerRelationId` via the libpq "everything else" branch at line 361). A SERVER is created by superuser (or owner-of-FDW with USAGE). Once created, a non-superuser with USAGE on the SERVER can create user mappings and use them. If the SERVER has `hostaddr=127.0.0.1, port=5432`, **any non-superuser with a `password_required=false` mapping (set by superuser) gets a loopback connection that may bypass `pg_hba.conf` peer/ident rules**. The canonical loopback attack. (likely — well-known, but documenting per Phase D)] — `source/contrib/postgres_fdw/option.c:244-301`, root cause is SERVER-level option scoping per FDW design.
- [ISSUE-security: `process_pgfdw_appname` interpolates `MyProcPort->user_name` and `MyProcPort->database_name` into the remote `application_name` string. These come from the local connection and are user-controlled (an attacker can set `application_name` on the LOCAL conn, then `%a` interpolates it). Sent to the remote where it lands in `pg_stat_activity.application_name`, log_line_prefix `%a`, and any monitoring. Truncation is at the remote, NAMEDATALEN. This is mostly cosmetic — no SQL is run from `application_name` — but it's an information-flow channel from local user → remote logs. (nit)] — `source/contrib/postgres_fdw/option.c:496`.
- [ISSUE-correctness: `is_valid_option` and `is_libpq_option` are O(N) linear scans (lines 385, 404). N is ~30. Trivial. (nit)] — `source/contrib/postgres_fdw/option.c:379`.
- [ISSUE-defense-in-depth: `ExtractExtensionList` calls `get_extension_oid(name, true)` (missingOk=true) — silently ignores unknown extension names except for a WARNING when `warnOnMissing=true` (validator path only). A typo in `extensions 'pg_trgm'` → `extensions 'pg_tgm'` is a WARNING at create time, silently treats nothing as shippable at planning time. Could surprise (worse: it could mask a downgrade where extension was removed locally). (nit)] — `source/contrib/postgres_fdw/option.c:469-481`.
- [ISSUE-api-shape: `postgres_fdw.application_name` GUC has no `check_hook` (line 587), so any string is accepted at SET time and only failed (via libpq) at next connection. (nit)] — `source/contrib/postgres_fdw/option.c:583`.
- [ISSUE-correctness: `MemoryContextStrdup(TopMemoryContext, lopt->keyword)` (line 351) but `non_libpq_options` is memcpy'd straight (line 371). The string pointers in `non_libpq_options[]` point at static C-string literals, which is fine, but the asymmetry would be a foot-gun if someone added a runtime-built keyword there. (nit)] — `source/contrib/postgres_fdw/option.c:351,371`.
