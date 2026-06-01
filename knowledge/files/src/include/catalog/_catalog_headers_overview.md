# pg_*.h catalog headers — overview

- **Source path:** `source/src/include/catalog/pg_*.h`
- **Count:** 70 files
- **Last verified commit:** `ef6a95c7c64`

Each header declares one catalog via the `CATALOG(name, oid, oidmacro)` macro (defined in `genbki.h`). The macro is empty for the C compiler — what you see is a normal struct typedef'd to `FormData_pg_X` (with `Form_pg_X` as the pointer). genbki.pl reads the same text and emits the `.bki` bootstrap script plus `pg_X_d.h` (with the `Anum_pg_X_<col>` attnum macros and any column OID constants).

Markings to look for in each header:

- `BKI_BOOTSTRAP` — created during the bootstrap phase, before any other catalog exists.
- `BKI_SHARED_RELATION` — cluster-wide (lives in `global/` not `base/<dbid>/`).
- `BKI_ROWTYPE_OID(oid, oidmacro)` — fixed OID for the composite rowtype.
- `BKI_SCHEMA_MACRO` — generate a Schema_pg_X[] macro for use by relcache bootstrap.
- `BKI_DEFAULT(value)` — default value for a column in `.dat` rows.
- `BKI_LOOKUP(catalog)` / `BKI_LOOKUP_OPT(catalog)` — symbolic-name resolution against another catalog.
- `BKI_FORCE_NULL` / `BKI_FORCE_NOT_NULL` — override default nullability.

Below, headers are grouped by domain. Each entry: **file** — purpose; **PK**; **shared?**; **notable BKI markings**.

## Core relations & types

- **pg_class.h** — relations (tables/indexes/sequences/views/matviews/composites/foreign/partitioned/propgraphs). PK: oid. BOOTSTRAP, ROWTYPE_OID. Has a hand-maintained Schema_pg_class for bootstrap. Many columns LOOKUP into pg_namespace, pg_type, pg_am, pg_tablespace.
- **pg_attribute.h** — columns. PK: (attrelid, attnum). BOOTSTRAP, ROWTYPE_OID. attrelid LOOKUP→pg_class, atttypid LOOKUP→pg_type, attcollation LOOKUP→pg_collation.
- **pg_type.h** — types (base/composite/domain/enum/range/multirange/pseudo). PK: oid. BOOTSTRAP, ROWTYPE_OID. Many LOOKUP refs: typnamespace, typrelid, typelem, typarray, typinput/output/receive/send, typmodin/out, typanalyze, typsubscript, typbasetype, typcollation.
- **pg_proc.h** — functions/procedures/aggregates/window funcs. PK: oid. BOOTSTRAP. proowner→pg_authid, prolang→pg_language, prorettype→pg_type, proargtypes→pg_type, pronamespace→pg_namespace, prosupport→pg_proc.
- **pg_namespace.h** — schemas. PK: oid. nspowner→pg_authid.
- **pg_operator.h** — operators. PK: oid. oprcode/oprrest/oprjoin→pg_proc, oprleft/oprright/oprresult→pg_type, oprcom/oprnegate→pg_operator.
- **pg_aggregate.h** — aggregate metadata. PK: aggfnoid (→pg_proc). aggtransfn/aggfinalfn/aggcombinefn/etc.→pg_proc, aggtranstype→pg_type.
- **pg_cast.h** — type casts. PK: oid. castsource/casttarget→pg_type, castfunc→pg_proc.
- **pg_collation.h** — collations. PK: oid. collnamespace→pg_namespace, collowner→pg_authid.
- **pg_conversion.h** — encoding conversions. PK: oid. conproc→pg_proc.
- **pg_language.h** — procedural languages. PK: oid. laninline/lanvalidator/lanplcallfoid→pg_proc.
- **pg_constraint.h** — constraints (CHECK/PK/U/FK/EXCL/NOT NULL). PK: oid. conrelid→pg_class, contypid→pg_type, conindid→pg_class, confrelid→pg_class.
- **pg_attrdef.h** — column defaults. PK: oid. adrelid→pg_class, adnum→pg_attribute.attnum.
- **pg_index.h** — index metadata (one row per index). PK: indexrelid (→pg_class). indrelid→pg_class.
- **pg_inherits.h** — inheritance + partitioning relationships. PK: (inhrelid, inhseqno). Both→pg_class.
- **pg_partitioned_table.h** — per-partitioned-table key + default-partition info. PK: partrelid (→pg_class).
- **pg_sequence.h** — per-sequence parameters (start/min/max/increment/cycle/cache). PK: seqrelid (→pg_class).

## Access methods, opclasses, opfamilies

- **pg_am.h** — access methods (btree, hash, gist, gin, brin, spgist, heap, …). PK: oid. amhandler→pg_proc.
- **pg_opclass.h** — operator classes. PK: oid. opcmethod→pg_am, opcintype/opckeytype→pg_type, opcfamily→pg_opfamily.
- **pg_opfamily.h** — operator families. PK: oid. opfmethod→pg_am.
- **pg_amop.h** — opfamily-member operators. PK: oid. amopfamily→pg_opfamily, amoplefttype/righttype→pg_type, amopopr→pg_operator.
- **pg_amproc.h** — opfamily-member support functions. PK: oid. amprocfamily→pg_opfamily, amproc→pg_proc.

## Dependency / description / security

- **pg_depend.h** — per-DB dependency edges. No PK (multi-column). classid+objid+refclassid+refobjid (LOOKUP varies by class). [from-comment, the BIG GRAPH]
- **pg_shdepend.h** — cross-DB dependency edges. **SHARED.** Includes dbid.
- **pg_description.h** — COMMENT ON. PK: (objoid, classoid, objsubid). classoid→pg_class.
- **pg_shdescription.h** — COMMENT ON for shared objects. **SHARED.**
- **pg_seclabel.h** — SECURITY LABEL. Per-DB.
- **pg_shseclabel.h** — SECURITY LABEL on shared objects. **SHARED.**
- **pg_init_privs.h** — extension-member privileges snapshot.
- **pg_default_acl.h** — ALTER DEFAULT PRIVILEGES rows.

## Roles & permissions (shared)

- **pg_authid.h** — roles. PK: oid. **SHARED.** Has password column.
- **pg_auth_members.h** — role membership. **SHARED.** member/grantor/roleid→pg_authid.
- **pg_database.h** — databases. **SHARED.** dattablespace→pg_tablespace, datdba→pg_authid.
- **pg_db_role_setting.h** — per-(DB, role) GUC overrides. **SHARED.**
- **pg_tablespace.h** — tablespaces. **SHARED.** spcowner→pg_authid.
- **pg_parameter_acl.h** — GUC parameter ACLs. **SHARED.**

## Replication

- **pg_replication_origin.h** — replication origins. **SHARED.** Used by logical apply workers to track LSN.
- **pg_publication.h** — publications. PK: oid. pubowner→pg_authid.
- **pg_publication_rel.h** — pub ↔ table edges. prrelid→pg_class, prpubid→pg_publication.
- **pg_publication_namespace.h** — pub ↔ schema edges. pnpubid→pg_publication, pnnspid→pg_namespace.
- **pg_subscription.h** — subscriptions. **SHARED.** PK: oid.
- **pg_subscription_rel.h** — per-(sub, rel) sync state. PER-DB.

## Foreign data wrappers

- **pg_foreign_data_wrapper.h** — FDWs. PK: oid. fdwhandler/fdwvalidator→pg_proc, fdwowner→pg_authid.
- **pg_foreign_server.h** — servers. srvfdw→pg_foreign_data_wrapper.
- **pg_foreign_table.h** — per-FTable settings. ftrelid→pg_class, ftserver→pg_foreign_server.
- **pg_user_mapping.h** — role↔server mapping. umuser→pg_authid, umserver→pg_foreign_server.

## Triggers, rules, policies, events

- **pg_trigger.h** — triggers. tgrelid→pg_class, tgfoid→pg_proc.
- **pg_rewrite.h** — rules. ev_class→pg_class.
- **pg_policy.h** — RLS policies. polrelid→pg_class, polroles→pg_authid[].
- **pg_event_trigger.h** — event triggers. evtfoid→pg_proc, evtowner→pg_authid.

## Statistics

- **pg_statistic.h** — per-column stats from ANALYZE. PK: (starelid, staattnum, stainherit).
- **pg_statistic_ext.h** — extended-statistics definitions. stxrelid→pg_class.
- **pg_statistic_ext_data.h** — extended-statistics computed data.

## Full text search

- **pg_ts_parser.h** — TS parsers (prsstart/prstoken/prsend/prsheadline→pg_proc).
- **pg_ts_dict.h** — TS dictionaries.
- **pg_ts_template.h** — TS templates.
- **pg_ts_config.h** — TS configurations.
- **pg_ts_config_map.h** — TS config token-type mappings.

## Misc per-DB

- **pg_enum.h** — enum labels. enumtypid→pg_type.
- **pg_range.h** — range types. rngtypid→pg_type, rngsubtype→pg_type, rngmultitypid→pg_type.
- **pg_largeobject.h** — LO chunks. loid→pg_largeobject_metadata.
- **pg_largeobject_metadata.h** — LO ACL+owner.
- **pg_extension.h** — installed extensions. extowner→pg_authid, extnamespace→pg_namespace.
- **pg_transform.h** — type↔language transforms. trftype→pg_type, trflang→pg_language.

## Property graphs (PG 18+)

- **pg_propgraph_element.h** — graph elements (vertices/edges). pgepgid→pg_class, pgerelid→pg_class.
- **pg_propgraph_element_label.h** — element-to-label edges.
- **pg_propgraph_label.h** — labels.
- **pg_propgraph_label_property.h** — label-property edges.
- **pg_propgraph_property.h** — properties.

## Non-CATALOG headers in this directory

- **pg_control.h** — `ControlFileData` struct, NOT a CATALOG — defines `pg_control` (the binary file in `global/`, not a relation).
- **catversion.h** — `CATALOG_VERSION_NO` macro; bumped whenever on-disk catalog format changes (so initdb refuses to use a mismatched data directory).
- **binary_upgrade.h** — `binary_upgrade_next_*` globals used by pg_upgrade.

## Confidence tag tally

`[verified-by-code]=3 [from-comment]=4 [inferred]=12`
