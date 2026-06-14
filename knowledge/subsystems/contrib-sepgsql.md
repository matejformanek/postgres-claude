# contrib-sepgsql (SELinux mandatory-access-control integration)

- **Source path:** `source/contrib/sepgsql/`
- **Last verified commit:** `e18b0cb7344` (2026-06-13 anchor)
- **Loading model:** `shared_preload_libraries` (no `.control`)
- **Trusted:** no (security-sensitive)
- **Build requirement:** Linux + libselinux

## 1. Purpose

Apply SELinux **mandatory access control (MAC)** to PostgreSQL
catalog objects. Every PG entity (database, schema, table,
column, function) gets a **SELinux security label** alongside
its standard PG ACL; the SELinux kernel module enforces label-
based access in addition to PG's discretionary checks.

The largest in-tree security extension: 9 .c files totaling
~5000 LOC [verified-by-code `wc -l`]. Targets high-security
environments (government, regulated industries) where SELinux
policy is the authoritative security mechanism.

## 2. The 9 C files

| File | LOC | Coverage |
|---|---|---|
| `hooks.c` | 486 | All PG object-access hooks |
| `selinux.c` | 888 | libselinux interaction |
| `label.c` | 915 | Security-label management |
| `relation.c` | 773 | Table + index labels |
| `uavc.c` | 521 | User-space Access Vector Cache |
| `dml.c` | 359 | INSERT/UPDATE/DELETE checks |
| `proc.c` | 333 | Function-execution checks |
| `schema.c` | 235 | Schema access checks |
| `database.c` | 215 | Database access checks |

[verified-by-code `wc -l source/contrib/sepgsql/*.c`]

## 3. The hook installation

[verified-by-code `hooks.c` structure]

`_PG_init` registers callbacks against PG's `ObjectAccessHook`
system. Every catalog mutation (CREATE/ALTER/DROP) fires a
hook; sepgsql checks the requesting client's SELinux context
against the target object's label.

Hooks installed:

- **Object access** — CREATE / ALTER / DROP / NAMESPACE_SEARCH.
- **Executor** — pre-query check on involved relations.
- **Function execution** — check function's domain on call.
- **DML access** — check per-column rights on
  INSERT/UPDATE/DELETE.

## 4. SELinux labels

Every PG object stores a **security label** in the
`pg_seclabel` (or `pg_shseclabel` for shared) catalog. The
label looks like a SELinux context:

```
system_u:object_r:sepgsql_table_t:s0
```

[user:role:type:level]

The mapping rules:
- Tables → `sepgsql_table_t` subclass.
- Columns → `sepgsql_table_t.col_t` (or specific column
  types).
- Functions → `sepgsql_proc_exec_t`.
- Schemas → `sepgsql_schema_t`.
- Databases → `sepgsql_db_t`.

## 5. The User-space Access Vector Cache (UAVC)

[verified-by-code `uavc.c` — 521 LOC]

For performance, sepgsql caches recent access decisions in a
**UAVC**. When a hook fires:

1. Compute the (source_context, target_context, requested_perm)
   tuple.
2. Look up in UAVC.
3. If hit, use cached decision.
4. If miss, query libselinux's `security_compute_av`.
5. Cache the decision.

The cache is invalidated on policy reload (SIGUSR1).

## 6. The `sepgsql_setting` GUC + permissive mode

- **`sepgsql.permissive = on`** — log denials but don't
  enforce. Useful for policy development.
- **`sepgsql.debug_audit = on`** — log every check, not
  just denials. Very verbose; for debugging only.

In production: permissive = off, debug_audit = off.

## 7. The dml access hook

[verified-by-code `dml.c` — 359 LOC]

INSERT/UPDATE/DELETE fire a hook that:

1. Identifies the target relation.
2. For each column being touched, checks per-column
   permission against the client's SELinux context.
3. Denies access (raises ERROR) if any column fails.

Per-column rights mean a user can have INSERT permission
on some columns of a table but not others. PG's standard
ACL supports this (`GRANT INSERT (col1, col2)`), but
sepgsql's enforcement happens at the SELinux level too.

## 8. Setup requirements

This extension is **complex to set up**:

1. SELinux must be enabled on the host.
2. Custom SELinux policy module for PG must be loaded.
3. `shared_preload_libraries = 'sepgsql'`.
4. Database must be initialized with SELinux labels
   (`initdb-postgres-sepgsql`).
5. All catalog entities labeled via SQL functions.

The official PG docs have a 30+ page section on sepgsql
deployment. It's not a "drop in and forget" extension.

## 9. Production-use guidance

- **For standard apps**, use PG's built-in roles + ACL +
  row-level security.
- **For SELinux-mandated environments**, sepgsql is the
  in-tree solution.
- **Test thoroughly** — SELinux misconfiguration can lock
  out admins.
- **Permissive mode first**, enforce only after policy is
  stable.
- **Document the policy** — what labels exist, what
  transitions are allowed.

## 10. The relationship to row-level security

PG's row-level security (RLS) is **discretionary** — the
database owner declares the policy. SELinux MAC is
**mandatory** — even superusers are constrained by SELinux.

They can coexist; sepgsql's enforcement is in addition to
PG's standard ACL + RLS. For environments needing both
sepgsql for inter-process MAC + RLS for in-database row
control, both are configured.

## 11. Invariants

- **[INV-1]** Linux + libselinux required.
- **[INV-2]** All catalog objects carry a SELinux label.
- **[INV-3]** Hooks fire on every catalog access; denials
  raise ERROR.
- **[INV-4]** UAVC caches recent decisions; invalidated on
  policy reload.
- **[INV-5]** sepgsql.permissive controls enforce vs
  log-only.

## 12. Useful greps

- All hook callbacks:
  `grep -n 'sepgsql_object_access\|sepgsql_executor' source/contrib/sepgsql/hooks.c | head -10`
- libselinux calls:
  `grep -n 'security_compute_av\|getcon' source/contrib/sepgsql/selinux.c | head -10`
- The seclabel storage:
  `grep -n 'pg_seclabel\|pg_shseclabel' source/contrib/sepgsql/label.c | head -10`

## 13. Cross-references

- `.claude/skills/bgworker-and-extensions/SKILL.md` —
  shared_preload_libraries + hook installation.
- `knowledge/subsystems/contrib-passwordcheck.md` —
  sibling security contrib.
- `knowledge/subsystems/contrib-auth_delay.md` — sibling
  security contrib.
- `knowledge/subsystems/contrib-sslinfo.md` — TLS-info
  for row-level decisions.
- `source/src/include/catalog/objectaccess.h` —
  ObjectAccessHook API.
- `source/contrib/sepgsql/` — implementation directory.
