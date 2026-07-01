# src/backend/utils/adt/ddlutils.c

- **Last verified commit:** `b7e4e3e7fa73` (cites re-pinned after
  d6ed87d19890 replaced `parse_ddl_options` VARIADIC parsing with
  named boolean parameters; 977 lines)

## Purpose

Generates DDL statements that recreate cluster-level objects (roles,
tablespaces, databases) — i.e. the `pg_get_role_ddl(roleid)`,
`pg_get_tablespace_ddl(name|oid)`, `pg_get_database_ddl(dboid)` family.
Shares option-parsing and pretty-printing infrastructure for
"pretty"/"no_owner"/"memberships" flags. Companions to the
`pg_get_*def` functions in `ruleutils.c` for relations and constraints.
[from-comment] (`ddlutils.c:3-9`)

## Role in PG

Backend SRF helpers; consumer is `pg_dumpall --cluster-objects` and
similar tooling. The whole file is **PG 18+ new surface** (no equivalent in
PG ≤ 17 — confirmed by file presence in the batch manifest's "if present
in this version").

## Key functions

Public SQL entry points (all SRFs returning `text` per statement).
As of d6ed87d19890 (2026-06-29) the option arguments are **named
boolean parameters**, not a `VARIADIC any[]` list — the former
`parse_ddl_options` helper is gone:
- `pg_get_role_ddl(roleid, pretty, memberships)` (`:426`). One
  CREATE ROLE plus optional ALTER ROLE … IN DATABASE … SET … and
  optional GRANT memberships.
- `pg_get_tablespace_ddl_oid(oid, pretty, no_owner)` (`:626`) /
  `pg_get_tablespace_ddl_name(name, pretty, no_owner)` (`:638`).
  CREATE TABLESPACE plus optional ALTER TABLESPACE SET (reloptions).
- `pg_get_database_ddl(dbid, pretty, no_owner)` (`:932`). CREATE
  DATABASE WITH … plus per-database GUCs from pg_db_role_setting.

Internal helpers:
- `append_ddl_option` (`:65`), `append_guc_value` (`:102`) —
  pretty-print glue.
- `pg_get_role_ddl_internal(roleid, pretty, memberships) → List` (`:149`).
  Permission gate at `:172`:
  `pg_class_aclcheck(AuthIdRelationId, GetUserId(), ACL_SELECT) !=
  ACLCHECK_OK` → `ERRCODE_INSUFFICIENT_PRIVILEGE`. I.e. SELECT on
  pg_authid (effectively superuser or pg_read_server_files-flavour
  membership) is required.
- `pg_get_tablespace_ddl_internal(tsid, pretty, no_owner)` (`:479`).
  Permission gate at `:502`: `pg_class_aclcheck(TableSpaceRelationId,
  GetUserId(), ACL_SELECT)` → `aclcheck_error(...)` at `:505`.
- `pg_get_database_ddl_internal(dbid, pretty, no_owner)` (`:655`).
  Permission gate at `:680`: `object_aclcheck(DatabaseRelationId,
  dbid, GetUserId(), ACL_CONNECT)` — i.e. CONNECT privilege on the
  named database.

## State / globals

None.

## Phase D notes

- **Three different privilege models** in one file:
  - Roles: SELECT on `pg_authid` (`:172`). Pretty restrictive; default
    is `pg_read_all_settings`/`pg_read_server_files`-class roles or
    explicit GRANT.
  - Tablespaces: SELECT on `pg_tablespace` (`:502`). Default PG ACL
    on `pg_tablespace` is `pg_read_all_settings` + superuser.
  - Databases: CONNECT on the database (`:680`). Weakest — anyone
    who can log in can dump the DDL.
- Output may include **passwords** if a role has an encrypted
  password (`pg_get_role_ddl` re-emits `PASSWORD '…'`). Anyone
  with SELECT on pg_authid sees the hash anyway; this just makes it
  copy-pasteable. Information disclosure risk roughly identical to
  pg_authid SELECT.
- Includes `pg_db_role_setting` per-database GUCs in
  `pg_get_database_ddl`. These can encode connection-string secrets
  via custom GUCs (rare but possible).

## Potential issues

- [ISSUE-info-disclosure: `pg_get_database_ddl` gates on ACL_CONNECT;
  this is weaker than SELECT on pg_database. Any role with login +
  CONNECT can dump the DDL including any per-db role GUCs. If an
  admin has set sensitive values via `ALTER DATABASE … SET
  custom.api_key = …`, those leak (low to medium)]
- [ISSUE-info-disclosure: `pg_get_role_ddl` re-emits encrypted
  password hashes (SCRAM verifiers etc.) when the caller has SELECT
  on pg_authid. Hashes are normally already accessible to that
  caller via direct query; this isn't new leakage but worth knowing
  (low)]
- [ISSUE-undocumented-invariant: option arguments are now named
  boolean parameters (d6ed87d19890 replaced the earlier
  `VARIADIC ANY[]` parsing); if pg_proc declares the function
  `PARALLEL UNSAFE` by default this is OK, but if it's later marked
  SAFE the per-call ACL check would happen in every worker. Not
  currently an issue (low)]

## Cross-references

<!-- issues:auto:begin -->
- [Issue register — `utils-adt`](../../../../../issues/utils-adt.md)
<!-- issues:auto:end -->
