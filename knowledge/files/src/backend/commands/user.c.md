# user.c

- **Source path:** `source/src/backend/commands/user.c`
- **Lines:** 2596
- **Last verified commit:** `ef6a95c7c64`

## Purpose

"Commands for manipulating roles (formerly called users)." [from-comment, user.c:3-4] CREATE ROLE / USER / GROUP (synonyms), ALTER ROLE, DROP ROLE, GRANT/REVOKE membership, CREATE/DROP role-attribute changes.

## Public surface

- `CreateRole`, `AlterRole`, `AlterRoleSet` (per-role GUC defaults), `DropRole`, `RenameRole`, `ReassignOwnedObjects` — DDL.
- `GrantRole` — GRANT role-membership: complex because of `WITH ADMIN OPTION`, `SET TRUE/FALSE`, `INHERIT TRUE/FALSE`, `GRANTED BY` clauses. Writes pg_auth_members.
- `check_password_hook` — pluggable password-strength check; the `passwordcheck` contrib extension uses it.
- `roles_is_member_of`, `is_member_of_role`, `has_privs_of_role` — internal helpers. Note the **separation of three concepts**: SET role (can become this role temporarily); INHERIT (automatically gets its privileges in addition to my own); ADMIN OPTION (can grant this membership to others). Each independently controlled per pg_auth_members row (since PG 16).

## Predefined roles

`pg_read_all_data`, `pg_write_all_data`, `pg_monitor`, `pg_signal_backend`, `pg_use_reserved_connections`, `pg_create_subscription`, etc. — these are baked into initdb; can be GRANTed but not dropped. `pg_authid.oid` < `FirstNormalObjectId` for them.

## SCRAM password storage

`AlterRole SET PASSWORD 'x'` runs the cleartext through `encrypt_password` (`libpq/crypt.c`) which by default produces a SCRAM-SHA-256 verifier. Older MD5 verifiers still accepted but emit a NOTICE.

## Confidence tag tally

`[verified-by-code]=4 [from-comment]=1`
