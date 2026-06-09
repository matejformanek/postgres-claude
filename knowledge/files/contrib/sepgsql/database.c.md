# database.c

## One-line summary

`db_database` class hooks: assign default label + check
`getattr/create/drop/setattr/relabelfrom/relabelto` permissions on database
objects via libselinux-driven label computation.

## Public API / entry points

- `sepgsql_database_post_create(databaseId, dtemplate) → void` —
  `source/contrib/sepgsql/database.c:31-124`. Called from `hooks.c:111-112`
  on `OAT_POST_CREATE/DatabaseRelationId`. Looks up the template database's
  label, checks `db_database:{getattr}` on it, computes the new DB's label
  via `sepgsql_compute_create`, checks `db_database:{create}` on the new
  label, then `SetSecurityLabel` to bind.
- `sepgsql_database_drop(databaseId) → void` — `database.c:131-151`. Checks
  `db_database:{drop}` against the current label.
- `sepgsql_database_setattr(databaseId) → void` — `database.c:158-178`.
  Checks `db_database:{setattr}`.
- `sepgsql_database_relabel(databaseId, seclabel) → void` —
  `database.c:185-215`. Two-phase: `{setattr relabelfrom}` against current
  label, then `{relabelto}` against the new label.

## Key invariants

- The template DB lookup uses `dtemplate` from
  `sepgsql_context_info.createdb_dtemplate` (saved during the
  `ProcessUtility_hook` for `T_CreatedbStmt` — hooks.c:340-357). If
  `dtemplate` is NULL (e.g., default-template path), the routine forces it
  to `"template1"` (`database.c:49-50`). [verified-by-code]
- `sepgsql_get_label(DatabaseRelationId, templateOid, 0)` is the source of
  the parent label for `sepgsql_compute_create` — i.e., the new database
  *inherits from the template's label* via SELinux transition rules, not
  from the *creator's* label directly. The creator (client) appears as
  scontext; the template's label is tcontext.
- `SnapshotSelf` is used in the pg_database scan (`database.c:86`) because
  the new tuple is not visible under a regular snapshot during the
  post-create hook (the txn hasn't committed yet).
- All AVC checks use `abort_on_violation = true` — denial throws.
  [verified-by-code]

## Notable internals

`sepgsql_database_post_create` order of operations:

1. Resolve template OID via `get_database_oid(dtemplate, false)`.
2. Fetch template's label via `sepgsql_get_label`.
3. Check `db_database:{getattr}` on the template
   (`sepgsql_avc_check_perms_label`, `database.c:65-69`). Audit name is the
   quoted template identifier.
4. Re-scan pg_database with SnapshotSelf to get the new row (necessary
   because the post-create hook fires after the catalog insert in the same
   subxact).
5. Compute new label via `sepgsql_compute_create(client, tcontext,
   DB_DATABASE, dtName)`.
6. Check `db_database:{create}` against the *new* label
   (`database.c:104-108`).
7. `SetSecurityLabel` to persist the new label in `pg_shseclabel` (database
   labels are shared catalog entries).

`sepgsql_database_drop/setattr` both use
`sepgsql_avc_check_perms(&object, ...)` which internally fetches the label
via `GetSecurityLabel`. Audit name derives from `getObjectIdentity`.

`sepgsql_database_relabel` enforces the SELinux "relabel-from then
relabel-to" pattern: the subject must have permission to detach from the
current label AND attach to the new label.

## Trust boundary / Phase D surface

- **Two-step check pattern** (relabelfrom + relabelto). Standard SELinux
  idiom. Implementation is identical between database, schema, relation,
  proc, attribute. A future contributor copying this pattern who forgets
  one half = silent privilege bypass.

- **`db_database` labels live in `pg_shseclabel`** (shared catalog).
  Permission to write that catalog is governed by PG-side ACL on
  pg_shseclabel — which is normally read-only. The path is via
  `SetSecurityLabel` which checks the provider's relabel hook. This
  whole module is the relabel hook for "selinux" tag. Recursion is bounded
  because `SetSecurityLabel` writes directly to the catalog.

- **No `IsBootstrapProcessingMode` skip.** `sepgsql_database_post_create`
  unconditionally runs on every database creation, including the initial
  template0/template1. In a bootstrap context, sepgsql isn't loaded
  (`_PG_init` rejects `IsUnderPostmaster` and the bootstrap process has
  its own quirks — `is_selinux_enabled` typically returns false during
  initdb). So this path is unreachable at bootstrap. [inferred]

- **`get_database_oid(dtemplate, false)` will ereport** if the template
  doesn't exist. The error fires *before* any permission check on the
  source — a probe attack can use this to enumerate database names by
  observing error variant ("not found" vs "permission denied"). [ISSUE-
  audit-gap: error before permission check leaks existence of template
  databases (nit)]

- **`createdb_dtemplate` is captured from ProcessUtility once.** If a
  CREATE DATABASE is issued via SPI from inside another command, the
  ProcessUtility_hook fires for the *outer* command, possibly with a
  stale or NULL `createdb_dtemplate`. The `PG_TRY/PG_FINALLY` in
  `sepgsql_utility_command` (hooks.c) saves/restores
  `sepgsql_context_info`, so nested calls preserve outer state — but
  an inner CREATEDB whose dtemplate is NULL would fall through to
  "template1" silently. [ISSUE-correctness: nested CREATE DATABASE
  via SPI without dtemplate gets "template1" assumed; possibly the
  wrong source (maybe)]

## Cross-references

- hooks.c — `sepgsql_context_info.createdb_dtemplate` capture and
  `OAT_POST_CREATE/DatabaseRelationId` dispatch.
- uavc.c — `sepgsql_avc_check_perms_label`, `sepgsql_avc_check_perms`.
- selinux.c — `sepgsql_compute_create`.
- label.c — `sepgsql_get_label`.
- `source/src/backend/commands/dbcommands.c` — invokes the OAT_*
  callbacks for CREATE/DROP/ALTER DATABASE.
- `source/src/backend/catalog/pg_shseclabel.c` — storage of database
  labels (shared catalog).

## Issues spotted

- `[ISSUE-audit-gap: get_database_oid raises before sepgsql checks
  visibility, leaking template database existence (nit)]`
- `[ISSUE-correctness: nested CREATE DATABASE via SPI without explicit
  template defaults dtemplate to "template1" (database.c:49-50); the
  parent label may not be template1's (maybe)]`
- `[ISSUE-documentation: comment "XXX - upcoming version of libselinux
  supports to take object name" (database.c:75) is a long-standing TODO
  — sepgsql_compute_create is called with the new database name as
  objname so this is already done; comment is stale (nit)]`
