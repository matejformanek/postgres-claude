# `src/backend/commands/propgraphcmds.c`

- **Last verified commit:** `e18b0cb7344`
- **Lines:** ~1882
- **Source:** `source/src/backend/commands/propgraphcmds.c`

PG18+ addition: implements `CREATE PROPERTY GRAPH` and `ALTER PROPERTY
GRAPH` (SQL/PGQ — Property Graph Queries). A property graph is a
catalog-only relation (`RELKIND_PROPGRAPH`) that bundles together one
or more underlying vertex tables and edge tables, optional labels, and
optional property exposure clauses. The actual graph is materialized
at query time via rewrites; this file is the DDL side. [verified-by-code]

## API / entry points

- `CreatePropGraph(pstate, stmt)` — handles `CREATE PROPERTY GRAPH`.
  Two-pass: pass 1 resolves all vertex element_info structs (key
  array, alias-uniqueness), pass 2 resolves edges (looks up source
  and destination by alias in the just-built vertex list). Calls
  `DefineRelation(..., RELKIND_PROPGRAPH, ...)`, then inserts one
  `pg_propgraph_element` row per element via `insert_element_record`.
  Finally runs `check_element_properties` and
  `check_all_labels_properties` to validate property type unification.
  [verified-by-code]
- `AlterPropGraph(pstate, stmt)` — handles `ALTER PROPERTY GRAPH`
  variants: `ADD VERTEX/EDGE TABLES`, `DROP VERTEX/EDGE TABLES`,
  `ADD LABEL`, `DROP LABEL`, `ADD PROPERTIES`, `DROP PROPERTIES`.
  Uses `performDeletion` for the drops, including orphan cleanup of
  `pg_propgraph_label` and `pg_propgraph_property` entries.
  CacheInvalidates relcache at the end for cached-plan rewrite.
  [verified-by-code]

## Static helpers (selected)

- `propgraph_element_get_key` — process the optional `KEY (cols)`
  clause; if absent, fall back to the relation's primary key.
  [verified-by-code]
- `propgraph_edge_get_ref_keys` — resolve edge SOURCE/DESTINATION
  KEYS REFERENCES. If explicit columns given, look up equality
  operators (BT then HASH default opclass), enforce same-collation
  rule (stricter than FK). If no columns, scan `RelationGetFKeyList`
  for a unique matching FK. [from-comment]
- `insert_element_record` — write a `pg_propgraph_element` row with
  source/dest vertex id, key, srckey/srcref/srceqop arrays and dest
  equivalents (all NULL for vertices). Records dependencies on the
  base relation, key columns, source/dest vertex elements + their
  key columns + equality operators. [verified-by-code]
- `insert_label_record`, `insert_property_records`,
  `insert_property_record` — catalog-row insertion helpers for the
  label/property catalogs. [verified-by-code]
- `check_element_properties`, `check_element_label_properties`,
  `check_all_labels_properties` — type-unification validation: all
  elements that expose a label-property pair must agree on the
  property's resolved type. [verified-by-code]
- `get_vertex_oid`, `get_edge_oid`, `get_element_relid` — syscache
  lookups by `(graphid, alias)`. Distinct functions for the
  vertex-required and edge-required ereport messages. [verified-by-code]
- `get_graph_label_ids`, `get_label_element_label_ids`,
  `get_element_label_property_names`, `get_graph_property_ids` —
  systable scan helpers used by the orphan cleanup paths.

## Notable invariants / details

- New catalogs touched: `pg_propgraph_element`,
  `pg_propgraph_element_label`, `pg_propgraph_label`,
  `pg_propgraph_label_property`, `pg_propgraph_property`. See the
  catalog headers for column layout. [from-comment]
- Persistence: a propgraph is auto-temped if any of its component
  tables are temporary (lines 254-262). Cannot be `UNLOGGED` (line
  115-118) because it has no storage. [from-comment]
- Locks: vertex/edge tables opened with `AccessShareLock` via
  `RangeVarGetRelidExtended(... RangeVarCallbackOwnsRelation, ...)`
  (line 131-174). On `ALTER`, the property graph itself is locked
  `ShareRowExclusiveLock` (line 1297-1301). [verified-by-code]
- Equality operator resolution mirrors `ATAddForeignKeyConstraint`
  with the loosening that opclass is sourced from the *vertex* (PK)
  type, not the edge type, and HASH is a fallback if BTREE has no
  default opclass. Includes a last-resort implicit-cast attempt
  (lines 442-446). [from-comment]
- Collation rule: edge key vs vertex key must match collation if
  both are non-default and valid; stricter than FK/PK. [from-comment]
- `array_of_attnums_to_objectaddrs` / `array_of_opers_to_objectaddrs`
  unpack the ArrayType keys/opers and record `pg_depend` entries on
  each underlying column / operator (sub-OID style for columns).
- Final step of `AlterPropGraph` is `CacheInvalidateRelcacheByRelid`
  on the propgraph relid (line 1652-1654) so cached plans
  referencing the graph get rewritten. [from-comment]
- Comment "XXX no suitable index" at line 1620 — orphan
  `pg_propgraph_property` sweep uses a sequential `systable_beginscan`
  without an index on `plppropid`. [from-comment]

## Potential issues

- Lines 302-305. Four `Assert`s after the second-pass vertex lookup
  with no comment about why they can't fail. [ISSUE-undocumented-invariant:
  vertex-lookup post-condition (maybe)]
- Line 1620 "XXX no suitable index" — O(N) systable scan per orphan
  check. Acceptable today (small N) but will hurt large graphs.
  [ISSUE-stale-todo: XXX needs index (nit)]
- The lookup-by-alias pattern in `CreatePropGraph` for edges (line
  199-211, then again 285-301) is repeated; first pass collects
  relids for FK setup, second pass collects new element OIDs. The
  re-walk is clearly intentional (OIDs only assigned after first
  inserts) but a comment helps.
- `array_in_safe` / `escape_yaml` patterns are not used here; the
  file uses `construct_array_builtin` and friends directly.

## Synthesized by
<!-- backlinks:auto -->

## Cross-references

<!-- issues:auto:begin -->
- [Issue register — `commands`](../../../../issues/commands.md)
<!-- issues:auto:end -->
