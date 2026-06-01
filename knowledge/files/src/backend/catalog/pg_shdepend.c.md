# pg_shdepend.c

- **Source path:** `source/src/backend/catalog/pg_shdepend.c`
- **Lines:** ~1 740
- **Last verified commit:** `ef6a95c7c64`

## Purpose

"Routines to support manipulation of the pg_shdepend relation." pg_shdepend is the **cross-database / shared-object dependency** catalog. It's the only one that uses both `dbid` and `(classid, objid)` keys: a per-database object can reference a cluster-wide object (role, tablespace, parameter ACL). Drives `DROP OWNED BY`, `REASSIGN OWNED`, `DROP TABLESPACE` (which must check no DB depends on it), and `DROP ROLE`.

## Public surface

- `recordSharedDependencyOn` (125), `recordDependencyOnOwner` (168), `recordDependencyOnTablespace` (370) — single-row insert helpers. Owner dep is SHARED_DEPENDENCY_OWNER; ACL grants insert SHARED_DEPENDENCY_ACL; tablespace dep SHARED_DEPENDENCY_TABLESPACE; INIT_PRIVS variants for extensions.
- `shdepChangeDep` (206) — update one dep row in place (used for ALTER ... OWNER TO).
- `changeDependencyOnOwner` (316), `changeDependencyOnTablespace` (391) — wrappers.
- `updateAclDependencies` (491), `updateInitAclDependencies` (512), `updateAclDependenciesWorker` (525) — keep pg_shdepend in sync with the granted roles in an ACL column. Called from aclchk.c after every GRANT/REVOKE.
- `checkSharedDependencies` (676) — pre-DROP-ROLE check: "is roleX referenced anywhere in the cluster" — returns a human-readable list of objects in each database.
- `copyTemplateDependencies` (895) — CREATE DATABASE: copy template DB's shared-dep rows for the new dbid.
- `dropDatabaseDependencies` (999) — DROP DATABASE: remove all rows with dbid=dropped.
- `deleteSharedDependencyRecordsFor` (1047) — DROP object: remove rows pointing to it.
- `shdepAddDependency` (1069), `shdepDropDependency` (1124) — low-level add/drop.
- `classIdGetDbId` (1190) — for a per-DB classid, return the DB OID; for a shared classid, return 0.
- `shdepLockAndCheckObject` (1211) — lock + recheck pattern for shared objects.
- `shdepDropOwned` (1342) — backend of `DROP OWNED BY role` across all DBs the current session is in.
- `shdepReassignOwned` (1530), `shdepReassignOwned_Owner` (1647) — backend of `REASSIGN OWNED BY a TO b`.

## Key shape

pg_shdepend rows: `(dbid, classid, objid, objsubid, refclassid, refobjid, deptype)`. `dbid=0` for shared catalog objects. `refclassid` is always a *shared* catalog (pg_authid, pg_tablespace, pg_database, pg_parameter_acl). `deptype` ∈ {o owner, a acl, i internal-pin, t tablespace, …}.

## Confidence tag tally

`[verified-by-code]=4 [inferred]=2`
