# objectaddress.c

- **Source path:** `source/src/backend/catalog/objectaddress.c`
- **Lines:** ~6 500
- **Last verified commit:** `ef6a95c7c64`

## Purpose

"Functions for working with ObjectAddresses." The `ObjectAddress { classId, objectId, objectSubId }` triple is PG's universal object identifier. This file is the **name ↔ ObjectAddress translation layer** plus uniform ownership/description helpers used by COMMENT, SECURITY LABEL, ALTER ... OWNER TO, event triggers, and `pg_get_object_address` (the SQL-facing inverse of `pg_identify_object`).

## Public surface

- `get_object_address` (1010) — **the main entry**: parses a parser-output object specifier (ObjectType + Node) and resolves it to an ObjectAddress, taking a lock per the per-class default. Recovery from race against concurrent DROP via the same retry-after-lock pattern as namespace.c.
- `get_object_address_rv` (1313) — convenience for cases where the object is identified by a RangeVar + sub-list (e.g., "table.column").
- `get_object_address_unqualified` (1335) — for objects that have no schema (databases, tablespaces, roles, etc.).
- `get_relation_by_qualified_name` (1426) — relation lookup that errors if the relkind doesn't match expected.
- `get_object_address_relobject` (1515) — table-sub-objects (rules, triggers, policies, RLS).
- `get_object_address_attribute` (1594), `get_object_address_attrdef` (1645) — columns, defaults.
- `get_object_address_type` (1703) — types and domains.
- `get_object_address_opcf` (1742) — opclass / opfamily.
- `get_object_address_opf_member` (1780) — opfamily member (operator or support function).
- `get_object_address_usermapping` (1892) — USER MAPPING FOR x SERVER y.
- `get_object_address_publication_rel` (1963), `get_object_address_publication_schema` (2016) — pub. relations / schemas.
- `get_object_address_defacl` (2058) — default privilege entries.
- `pg_get_object_address` (2204) — SQL function: text/text[]/text[] → object_address row.
- `check_object_ownership` (2487) — universal "is roleid the owner of this object" check used by ALTER … RENAME / OWNER TO / DROP.
- `get_object_namespace` (2670) — back-resolve namespace of an arbitrary object (used by COMMENT permissions).
- `read_objtype_from_string` (2706) — reverse of `stringify_objtype` for event triggers.
- `get_object_class_descr` (2726), `get_object_oid_index` (2734), `get_object_catcache_oid` (2742), `get_object_catcache_name` (2750) — lookups into the **ObjectProperty table** (a per-classid metadata array, defined earlier in this same file ~line 100-1000) that maps each catalog's classid to: catalog Relation OID, OID column attnum, name column attnum, namespace column attnum, owner column attnum, ACL column attnum, oid index, name-syscache id, oid-syscache id, alter-acl-relevant flag.

## The ObjectProperty table

The huge static array `ObjectProperty[]` at the top of this file is the **single source of truth** for "how do you locate / lock / rename / describe an object of class X". Every new catalog requires a row here. This is why `get_object_address` can be one switch over ObjectType: most actual work is data-driven from ObjectProperty.

## Confidence tag tally

`[verified-by-code]=4 [inferred]=2`
