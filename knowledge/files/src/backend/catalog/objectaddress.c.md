# objectaddress.c

- **Source path:** `source/src/backend/catalog/objectaddress.c`
- **Lines:** ~6 626
- **Last verified commit:** `d774576f6f05`

## Purpose

"Functions for working with ObjectAddresses." The `ObjectAddress { classId, objectId, objectSubId }` triple is PG's universal object identifier. This file is the **name ↔ ObjectAddress translation layer** plus uniform ownership/description helpers used by COMMENT, SECURITY LABEL, ALTER ... OWNER TO, event triggers, and `pg_get_object_address` (the SQL-facing inverse of `pg_identify_object`).

## Public surface

- `get_object_address` (1016) — **the main entry**: parses a parser-output object specifier (ObjectType + Node) and resolves it to an ObjectAddress, taking a lock per the per-class default. Recovery from race against concurrent DROP via the same retry-after-lock pattern as namespace.c.
- `get_object_address_rv` (1319) — convenience for cases where the object is identified by a RangeVar + sub-list (e.g., "table.column").
- `get_object_address_unqualified` (1341) — for objects that have no schema (databases, tablespaces, roles, etc.).
- `get_relation_by_qualified_name` (1432) — relation lookup that errors if the relkind doesn't match expected.
- `get_object_address_relobject` (1521) — table-sub-objects (rules, triggers, policies, RLS).
- `get_object_address_attribute` (1600), `get_object_address_attrdef` (1651) — columns, defaults.
- `get_object_address_type` (1709) — types and domains.
- `get_object_address_opcf` (1748) — opclass / opfamily.
- `get_object_address_opf_member` (1786) — opfamily member (operator or support function).
- `get_object_address_usermapping` (1898) — USER MAPPING FOR x SERVER y.
- `get_object_address_publication_rel` (1969), `get_object_address_publication_schema` (2022) — pub. relations / schemas.
- `get_object_address_defacl` (2064) — default privilege entries.
- `pg_get_object_address` (2210) — SQL function: text/text[]/text[] → object_address row.
- `check_object_ownership` (2493) — universal "is roleid the owner of this object" check used by ALTER … RENAME / OWNER TO / DROP.
- `get_object_namespace` (2676) — back-resolve namespace of an arbitrary object (used by COMMENT permissions).
- `read_objtype_from_string` (2712) — reverse of `stringify_objtype` for event triggers.
- `get_object_class_descr` (2730), `get_object_oid_index` (2738), `get_object_catcache_oid` (2746), `get_object_catcache_name` (2754) — lookups into the **ObjectProperty table** (a per-classid metadata array, defined earlier in this same file ~line 124-714) that maps each catalog's classid to: catalog Relation OID, OID column attnum, name column attnum, namespace column attnum, owner column attnum, ACL column attnum, oid index, name-syscache id, oid-syscache id, alter-acl-relevant flag.

## The ObjectProperty table

The huge static array `ObjectProperty[]` at the top of this file (124-714) is the **single source of truth** for "how do you locate / lock / rename / describe an object of class X". Every new catalog requires a row here. This is why `get_object_address` can be one switch over ObjectType: most actual work is data-driven from ObjectProperty. Property-graph catalogs (`pg_propgraph_element`, `pg_propgraph_element_label`, `pg_propgraph_label`, `pg_propgraph_label_property`, `pg_propgraph_property`) carry their own ObjectProperty rows (379-441); their readable identity/description strings are produced by the `Propgraph*RelationId` cases in `getObjectIdentityParts` (6169+) / `getObjectDescription` (4077+) — added by upstream 2a7e95b6.

## Confidence tag tally

`[verified-by-code]=4 [inferred]=2`

## Synthesized by
<!-- backlinks:auto -->
- [subsystems/optimizer.md](../../../../subsystems/optimizer.md)
