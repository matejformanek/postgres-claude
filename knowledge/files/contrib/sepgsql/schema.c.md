# schema.c

## One-line summary

`db_schema` class hooks: label-assign + check
`create/drop/setattr/search/add_name/remove_name/relabelfrom/relabelto` on
namespace (pg_namespace) objects.

## Public API / entry points

- `sepgsql_schema_post_create(namespaceId) → void` —
  `source/contrib/sepgsql/schema.c:35-106`. Special-cases `pg_temp_*` and
  `pg_toast_temp_*` schema names by collapsing to `pg_temp`/`pg_toast_temp`
  for the libselinux name lookup (`schema.c:72-75`).
- `sepgsql_schema_drop(namespaceId) → void` — `schema.c:113-133`. Checks
  `db_schema:{drop}`.
- `sepgsql_schema_relabel(namespaceId, seclabel) → void` —
  `schema.c:141-171`. Two-phase relabelfrom/relabelto pattern.
- `sepgsql_schema_setattr(namespaceId) → void` — `schema.c:201-205`.
- `sepgsql_schema_search(namespaceId, abort_on_violation) → bool` —
  `schema.c:208-214`. Checks `db_schema:{search}`. Called from
  `hooks.c:268-270` on `OAT_NAMESPACE_SEARCH`.
- `sepgsql_schema_add_name(namespaceId) → void` — `schema.c:217-220`.
- `sepgsql_schema_remove_name(namespaceId) → void` — `schema.c:223-226`.
- `sepgsql_schema_rename(namespaceId) → void` — `schema.c:229-235`.
  Combines `{add_name remove_name}`.

Static helper `check_schema_perms(Oid, uint32, bool)` factors out the
common object setup + `sepgsql_avc_check_perms` call (`schema.c:178-198`).

## Key invariants

- The label parent for `sepgsql_compute_create` is the *current database's*
  label (`schema.c:77`) — schemas inherit from their database, not from a
  parent schema (PG doesn't have nested schemas).
- `pg_temp_<sessionid>` schemas get the canonical "pg_temp" name for label
  computation (`schema.c:72-73`); same for `pg_toast_temp_*`. The actual
  catalog name retains the suffix. This means *all* temporary schemas
  receive the same default label (modulo the policy's response to the name
  "pg_temp"). [verified-by-code]
- All checks use `abort_on_violation = true` except `sepgsql_schema_search`
  which passes through the caller's value (`schema.c:208-214`).
  [verified-by-code]

## Notable internals

`sepgsql_schema_post_create` reads the new pg_namespace row with
`SnapshotSelf` (necessary because the tuple isn't visible in the current
snapshot during the post-create hook). The flow:

1. Fetch namespace row by OID.
2. Collapse temp-namespace names to canonical form for label compute.
3. Get database label via `sepgsql_get_label(DatabaseRelationId,
   MyDatabaseId, 0)`.
4. Compute new label via `sepgsql_compute_create(client, dbLabel,
   DB_SCHEMA, nsp_name)`.
5. Check `db_schema:{create}` against new label.
6. `SetSecurityLabel` to persist.

`OAT_NAMESPACE_SEARCH` deserves special attention: it's the only branch
where sepgsql implements *visibility control* rather than just allow/deny
on a specific operation. When a query references a relation by qualified
name `schema.relation`, the namespace search hook fires; if sepgsql denies
search on the namespace, the name resolution returns "not found" (when
`ereport_on_violation=false`) or raises. The wrapping in hooks.c short-
circuits if a prior provider denied — sepgsql then doesn't run its check.

## Trust boundary / Phase D surface

- **`db_schema:{search}` is the visibility filter.** A user whose label
  lacks `search` on `public` schema cannot resolve any unqualified name
  there. **This is the only place sepgsql touches name visibility** —
  pg_class entries themselves are visible (catalog access checks fall
  under different rules). [verified-by-code]

- **Temp-schema label collapse** (`schema.c:72-75`). All `pg_temp_*`
  schemas share one label. **Cross-session leakage risk: if the policy
  is configured so that temp objects are accessible via "pg_temp"
  label, the same label applies to every session's temp schema —
  intended.** A misconfigured policy could allow one session to read
  another's pg_temp via the shared label. Policy concern, not code. [verified-by-code]

- **`db_schema:{add_name}` and `{remove_name}`** are checked from
  `relation.c` and `proc.c` on object creation/drop into a schema —
  *separate from* the schema's own `create/drop` perm. So a user with
  `create` on a schema but lacking `add_name` cannot put objects in
  it; conversely, lacking `create` on the schema doesn't prevent
  add_name. The two-perm split lets the policy express "you can put
  things here but not own here". [verified-by-code]

- **No `IsBootstrapProcessingMode` skip** — same logic as database.c.
  Reaches this path only via OAT hooks, which only fire when
  sepgsql is loaded, which only happens after initdb. [inferred]

- **No special protection on `pg_catalog`.** A user with appropriate
  label can issue `SECURITY LABEL ON SCHEMA pg_catalog IS ...` and
  the standard relabel check applies. There's no hardwired refusal —
  the policy must encode it. [verified-by-code]

- **`pg_temp` is treated as a regular schema** for label compute —
  the policy author must decide whether to treat temp objects as
  special. Without a pg_temp-specific transition rule, temp objects
  inherit from the database label, which may not be what the policy
  intends. [ISSUE-defense-in-depth: pg_temp objects are labeled by
  default DB rules; policies that don't explicitly handle pg_temp
  may grant unexpected access (maybe)]

## Cross-references

- hooks.c — `OAT_POST_CREATE/NamespaceRelationId`,
  `OAT_NAMESPACE_SEARCH`, `OAT_DROP`, `OAT_POST_ALTER` dispatchers.
- uavc.c — permission check funnel.
- label.c — `sepgsql_get_label`.
- `source/src/backend/catalog/namespace.c` — invokes
  `OAT_NAMESPACE_SEARCH` from `LookupExplicitNamespace`.
- `source/src/backend/commands/schemacmds.c` — CREATE/DROP/ALTER
  SCHEMA path.

## Issues spotted

- `[ISSUE-defense-in-depth: pg_temp schemas all share one
  canonical-name label compute; policies must explicitly handle
  pg_temp or risk default-DB-label transitions allowing
  cross-session access via temp objects (maybe)]`
- `[ISSUE-audit-gap: sepgsql_schema_search returns bool through
  the OAT_NAMESPACE_SEARCH machinery, but if the caller passes
  ereport_on_violation=false, a denied search produces no
  ereport — only the AVC audit record fires; if log_min_messages
  filters that, denial is invisible (likely)]`
