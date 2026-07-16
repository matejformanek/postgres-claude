# Issues — `catalog` (src/include/catalog/)

Per-subsystem issue register for PostgreSQL catalog headers. See
`knowledge/issues/README.md` for the tag convention, severity scale,
and workflow.

**Parent docs:** `knowledge/files/src/include/catalog/_catalog_headers_overview.md`
+ per-header docs under `knowledge/files/src/include/catalog/`.

**Source:** All 68 entries below surfaced 2026-06-02 evening by the A1
catalog-headers parallel sweep (6 general-purpose agents reading the
72 previously-undocumented `pg_*.h` + infra headers). Each is mirrored
in the corresponding per-file doc's `## Potential issues` block.

## Open / Triaged

### High-priority (Phase D data-leak candidates)

| Date | File:line | Type | Severity | Summary | Status | Linked doc |
|---|---|---|---|---|---|---|
| 2026-06-02 | pg_statistic.h | leak | likely | `stavalues1..5` arrays hold verbatim sample values from user columns; only ACL on `pg_statistic` itself + `pg_stats` view filtering protect them | open · triaged 2026-07-16 | knowledge/files/src/include/catalog/pg_statistic.h.md |
| 2026-06-02 | pg_statistic_ext_data.h | leak | likely | `stxdmcv` + per-expression `stxdexpr` leak verbatim multi-column sample data; same surface as pg_statistic but across compound keys | open · triaged 2026-07-16 | knowledge/files/src/include/catalog/pg_statistic_ext_data.h.md |
| 2026-06-02 | pg_authid.h | question | maybe | `rolpassword` is unbounded `text` but the catalog has no TOAST table — password storage size implicitly capped at TOAST_TUPLE_THRESHOLD-ish | open · triaged 2026-07-16 | knowledge/files/src/include/catalog/pg_authid.h.md |
| 2026-06-02 | pg_largeobject_metadata.h | leak | maybe | `lomacl` is varlena `aclitem[]` but the catalog has no `DECLARE_TOAST` — anomaly relative to every other ACL-bearing catalog | open · triaged 2026-07-16 | knowledge/files/src/include/catalog/pg_largeobject_metadata.h.md |
| 2026-06-02 | pg_parameter_acl.h | question | likely | `parname` canonicalization at GRANT time vs SET time not documented; case-sensitive `text_ops` unique index suspicious for a case-insensitive GUC namespace — possible silent-bypass vector | open · triaged 2026-07-16 | knowledge/files/src/include/catalog/pg_parameter_acl.h.md |
| 2026-06-02 | pg_user_mapping.h | question | maybe | credentials stored in `umoptions text[]` — no encryption-at-rest invariant documented at the catalog layer | open · triaged 2026-07-16 | knowledge/files/src/include/catalog/pg_user_mapping.h.md |
| 2026-06-02 | pg_replication_origin.h | invariant | likely | `roident` is hand-allocated `uint16` and embedded in WAL — silent overflow risk if cluster accumulates >65535 origins over its lifetime; not documented in the header | open · triaged 2026-07-16 | knowledge/files/src/include/catalog/pg_replication_origin.h.md |
| 2026-06-02 | pg_control.h | invariant | confirmed | `ControlFileData` struct changes silently corrupt clusters unless `PG_CONTROL_VERSION` is bumped — header documents the version macro but not the obligation | open · triaged 2026-07-16 (claim overstated: obligation IS stated at `pg_control.h:33` "Changing this struct requires a PG_CONTROL_VERSION bump" + `:95`; downgrade to nit at next re-seed) | knowledge/files/src/include/catalog/pg_control.h.md |
| 2026-06-02 | pg_control.h | invariant | confirmed | XLOG rmgr info-byte renumbering in pg_control.h breaks replay; no anti-renumber warning | open · triaged 2026-07-16 | knowledge/files/src/include/catalog/pg_control.h.md |

### On-disk char-code invariants (undocumented across the corpus)

This is the dominant pattern from the sweep — 26 separate header lines
encode catalog values as single ASCII characters that are stored verbatim
in the table. **Only `dependency.h`'s `DependencyType` enum carries an
explicit "the character is the on-disk value" comment.** The others rely
on implicit knowledge; renumbering any of them is an on-disk format
break that won't be caught at compile time. Cataloged together because
a single doc-only patch series could fix all of them.

| Date | File:line | Type | Severity | Summary | Status | Linked doc |
|---|---|---|---|---|---|---|
| 2026-06-02 | pg_class.h | undocumented-invariant | maybe | `RELKIND_*`, `RELPERSISTENCE_*`, `REPLICA_IDENTITY_*` are on-disk single chars; header doesn't say so | open · triaged 2026-07-16 | knowledge/files/src/include/catalog/pg_class.h.md |
| 2026-06-02 | pg_attribute.h | undocumented-invariant | maybe | `ATTRIBUTE_IDENTITY_*`, `ATTRIBUTE_GENERATED_*` are on-disk single chars | open · triaged 2026-07-16 | knowledge/files/src/include/catalog/pg_attribute.h.md |
| 2026-06-02 | pg_type.h | undocumented-invariant | maybe | `TYPTYPE_*`, `TYPCATEGORY_*`, `TYPALIGN_*`, `TYPSTORAGE_*` are on-disk single chars | open · triaged 2026-07-16 | knowledge/files/src/include/catalog/pg_type.h.md |
| 2026-06-02 | pg_proc.h | undocumented-invariant | maybe | `PROKIND_*`, `PROVOLATILE_*`, `PROPARALLEL_*`, `PROARGMODE_*` are on-disk single chars | open · triaged 2026-07-16 | knowledge/files/src/include/catalog/pg_proc.h.md |
| 2026-06-02 | pg_partitioned_table.h | undocumented-invariant | maybe | `partstrat` on-disk chars defined in another header with no cross-ref | open | knowledge/files/src/include/catalog/pg_partitioned_table.h.md |
| 2026-06-02 | pg_operator.h | undocumented-invariant | maybe | `oprkind` chars ('l'/'b') are on-disk values | open · triaged 2026-07-16 | knowledge/files/src/include/catalog/pg_operator.h.md |
| 2026-06-02 | pg_am.h | undocumented-invariant | maybe | `amtype` chars ('i'/'t') are on-disk values | open · triaged 2026-07-16 | knowledge/files/src/include/catalog/pg_am.h.md |
| 2026-06-02 | pg_collation.h | undocumented-invariant | maybe | `collprovider_name` array omits `COLLPROVIDER_DEFAULT` ('d') | open · triaged 2026-07-16 | knowledge/files/src/include/catalog/pg_collation.h.md |
| 2026-06-02 | pg_opclass.h | undocumented-invariant | maybe | `opcdefault` uniqueness per (opcmethod, opcintype) not enforced by schema | open | knowledge/files/src/include/catalog/pg_opclass.h.md |
| 2026-06-02 | pg_default_acl.h | undocumented-invariant | maybe | `DEFACLOBJ_*` chars are on-disk | open | knowledge/files/src/include/catalog/pg_default_acl.h.md |
| 2026-06-02 | pg_init_privs.h | undocumented-invariant | maybe | `InitPrivsType` chars are on-disk | open | knowledge/files/src/include/catalog/pg_init_privs.h.md |
| 2026-06-02 | pg_largeobject.h | undocumented-invariant | maybe | direct bytea access bypasses TOAST | open | knowledge/files/src/include/catalog/pg_largeobject.h.md |
| 2026-06-02 | pg_seclabel.h | undocumented-invariant | maybe | label text opaque to PG; provider semantics not documented | open | knowledge/files/src/include/catalog/pg_seclabel.h.md |
| 2026-06-02 | pg_policy.h | undocumented-invariant | maybe | `polcmd` chars come from `ACL_*_CHR` (cross-header) — not local enum | open | knowledge/files/src/include/catalog/pg_policy.h.md |
| 2026-06-02 | pg_publication.h | undocumented-invariant | maybe | `pubgencols` (PUBLISH_GENCOLS_*) on-disk chars | open | knowledge/files/src/include/catalog/pg_publication.h.md |
| 2026-06-02 | pg_subscription.h | undocumented-invariant | maybe | `substream`, `subtwophasestate`, `suborigin` on-disk chars (LOGICALREP_STREAM_*, TWOPHASE_STATE_*, ORIGIN_*) | open · triaged 2026-07-16 | knowledge/files/src/include/catalog/pg_subscription.h.md |
| 2026-06-02 | pg_subscription_rel.h | undocumented-invariant | maybe | `SUBREL_STATE_*` on-disk; some chars are IPC-only — mixing is undocumented | open · triaged 2026-07-16 | knowledge/files/src/include/catalog/pg_subscription_rel.h.md |
| 2026-06-02 | pg_statistic_ext.h | undocumented-invariant | maybe | `stxkind` chars ('d'/'f'/'m'/'e') not flagged as on-disk | open | knowledge/files/src/include/catalog/pg_statistic_ext.h.md |
| 2026-06-02 | pg_rewrite.h | undocumented-invariant | maybe | `ev_type` / `ev_enabled` char meanings defined in other headers, no cross-ref | open | knowledge/files/src/include/catalog/pg_rewrite.h.md |
| 2026-06-02 | pg_trigger.h | undocumented-invariant | likely | `tgtype` bit positions are on-disk format with `AFTER==0` implicit; non-adjacent `TIMING_MASK` bits; no "do not renumber" warning | open · triaged 2026-07-16 | knowledge/files/src/include/catalog/pg_trigger.h.md |
| 2026-06-02 | pg_trigger.h | undocumented-invariant | maybe | `tgenabled` 'O'/'D'/'R'/'A' chars never given symbolic names in the header | open · triaged 2026-07-16 | knowledge/files/src/include/catalog/pg_trigger.h.md |
| 2026-06-02 | pg_event_trigger.h | undocumented-invariant | maybe | `evtenabled` reuses `pg_trigger.h` constants silently; cross-header coupling not flagged | open | knowledge/files/src/include/catalog/pg_event_trigger.h.md |
| 2026-06-02 | pg_event_trigger.h | undocumented-invariant | maybe | `evtevent` strings are on-disk values | open | knowledge/files/src/include/catalog/pg_event_trigger.h.md |
| 2026-06-02 | pg_event_trigger.h | question | maybe | ordering among event triggers for the same event not specified at the catalog level | open | knowledge/files/src/include/catalog/pg_event_trigger.h.md |

### Direct C-struct access puns (fragile invariants)

| Date | File:line | Type | Severity | Summary | Status | Linked doc |
|---|---|---|---|---|---|---|
| 2026-06-02 | pg_attribute.h | undocumented-invariant | maybe | `attlen`/`attbyval`/`attalign` must mirror `pg_type`; enforcement only in prose | open · triaged 2026-07-16 | knowledge/files/src/include/catalog/pg_attribute.h.md |
| 2026-06-02 | pg_proc.h | undocumented-invariant | maybe | `proargtypes` direct C-struct access pun is fragile; no static-assert on offset | open · triaged 2026-07-16 | knowledge/files/src/include/catalog/pg_proc.h.md |
| 2026-06-02 | pg_index.h | undocumented-invariant | maybe | `indkey` direct C-struct access pun is fragile | open · triaged 2026-07-16 | knowledge/files/src/include/catalog/pg_index.h.md |
| 2026-06-02 | pg_partitioned_table.h | undocumented-invariant | maybe | `partattrs` direct C-struct access pun (with rationale comment, but no enforcement) | open · triaged 2026-07-16 | knowledge/files/src/include/catalog/pg_partitioned_table.h.md |

### Cross-header / parallel-array / coupling invariants

| Date | File:line | Type | Severity | Summary | Status | Linked doc |
|---|---|---|---|---|---|---|
| 2026-06-02 | pg_auth_members.h | undocumented-invariant | maybe | `grantor` is part of row identity; (roleid, member, grantor) uniqueness not stated explicitly | open | knowledge/files/src/include/catalog/pg_auth_members.h.md |
| 2026-06-02 | pg_foreign_data_wrapper.h | doc-drift | maybe | callback signature drift risk: handler/validator/connection prototypes live elsewhere with no version contract | open | knowledge/files/src/include/catalog/pg_foreign_data_wrapper.h.md |
| 2026-06-02 | pg_foreign_table.h | undocumented-invariant | likely | invariant `pg_class.relkind='f'` ⇔ `pg_foreign_table` row exists is not enforced by schema | open · triaged 2026-07-16 | knowledge/files/src/include/catalog/pg_foreign_table.h.md |
| 2026-06-02 | pg_extension.h | undocumented-invariant | likely | `extconfig` / `extcondition` are parallel arrays — same-length invariant not stated in header | open · triaged 2026-07-16 | knowledge/files/src/include/catalog/pg_extension.h.md |
| 2026-06-02 | pg_subscription.h | doc-drift | maybe | ACL on `subconninfo` enforced in `system_views.sql` GRANT — easy to miss when adding columns | open · triaged 2026-07-16 | knowledge/files/src/include/catalog/pg_subscription.h.md |
| 2026-06-02 | pg_subscription_rel.h | undocumented-invariant | maybe | state↔LSN coupling: some states require LSN, others not; no machine-checkable invariant | open · triaged 2026-07-16 | knowledge/files/src/include/catalog/pg_subscription_rel.h.md |
| 2026-06-02 | pg_statistic.h | undocumented-invariant | maybe | `STATISTIC_KIND_*` integer codes are cross-project on-disk contract (PostGIS, ESRI namespaces) — phrased as allocation map, not stability contract | open | knowledge/files/src/include/catalog/pg_statistic.h.md |
| 2026-06-02 | pg_statistic_ext_data.h | doc-drift | maybe | serialized `pg_ndistinct` / `pg_dependencies` / `pg_mcv_list` formats undocumented in this header (live in `statistics/`) | open | knowledge/files/src/include/catalog/pg_statistic_ext_data.h.md |
| 2026-06-02 | pg_seclabel.h | question | nit | no `Form_pg_seclabel` typedef — unusual for a CATALOG header | open | knowledge/files/src/include/catalog/pg_seclabel.h.md |
| 2026-06-02 | pg_shseclabel.h | question | nit | PK does not include `objsubid` — divergent from `pg_seclabel` | open | knowledge/files/src/include/catalog/pg_shseclabel.h.md |
| 2026-06-02 | pg_policy.h | question | maybe | `polroles` with embedded 0 means PUBLIC under `BKI_LOOKUP_OPT` semantics — non-obvious | open | knowledge/files/src/include/catalog/pg_policy.h.md |
| 2026-06-02 | pg_parameter_acl.h | question | nit | `paracl BKI_DEFAULT(_null_)` — empty-ACL semantics not documented | open | knowledge/files/src/include/catalog/pg_parameter_acl.h.md |
| 2026-06-02 | pg_propgraph_element.h | doc-drift | maybe | minimal header comment for new PG18 catalog; key invariants live in `propgraphcmds.c` only | open | knowledge/files/src/include/catalog/pg_propgraph_element.h.md |
| 2026-06-02 | pg_propgraph_element.h | undocumented-invariant | maybe | equality-operator OID arrays lack `BKI_LOOKUP` | open | knowledge/files/src/include/catalog/pg_propgraph_element.h.md |
| 2026-06-02 | pg_propgraph_element_label.h | doc-drift | nit | empty header comment block | open | knowledge/files/src/include/catalog/pg_propgraph_element_label.h.md |
| 2026-06-02 | pg_propgraph_element_label.h | question | nit | no by-oid syscache | open | knowledge/files/src/include/catalog/pg_propgraph_element_label.h.md |
| 2026-06-02 | pg_propgraph_label.h | doc-drift | nit | empty header comment block | open | knowledge/files/src/include/catalog/pg_propgraph_label.h.md |
| 2026-06-02 | pg_propgraph_label_property.h | doc-drift | nit | empty header comment block | open | knowledge/files/src/include/catalog/pg_propgraph_label_property.h.md |
| 2026-06-02 | pg_propgraph_label_property.h | undocumented-invariant | likely | serialized expr in catalog forces catversion bumps on `primnodes.h` changes; not stated in header | open | knowledge/files/src/include/catalog/pg_propgraph_label_property.h.md |
| 2026-06-02 | pg_propgraph_property.h | doc-drift | nit | empty header comment block | open | knowledge/files/src/include/catalog/pg_propgraph_property.h.md |
| 2026-06-02 | pg_control.h | undocumented-invariant | likely | 512-byte atomicity ceiling is hardware-defined; comment doesn't make this explicit | open · triaged 2026-07-16 | knowledge/files/src/include/catalog/pg_control.h.md |

### Stale TODO / legacy

| Date | File:line | Type | Severity | Summary | Status | Linked doc |
|---|---|---|---|---|---|---|
| 2026-06-02 | pg_type.h | stale-todo | nit | `CASHOID` / `LSNOID` "ancient" backwards-compat aliases — flagged in comment but unaddressed | open | knowledge/files/src/include/catalog/pg_type.h.md |
| 2026-06-02 | pg_database.h | stale-todo | nit | `DATCONNLIMIT_INVALID_DB = -2` overload acknowledged in comment as "not clean" | open | knowledge/files/src/include/catalog/pg_database.h.md |
| 2026-06-02 | pg_authid.h | question | nit | "read rolsuper via superuser() only" rationale unexplained | open | knowledge/files/src/include/catalog/pg_authid.h.md |

## Wontfix / Submitted / Landed

| Date | File:line | Type | Summary | Status | Resolution |
|---|---|---|---|---|---|
| _(none yet)_ | | | | | |

## Notes

- **The on-disk char-code pattern is corpus-wide.** 26 of the 68 entries above flag undocumented "this character is the on-disk value, don't change it" invariants. Only `dependency.h`'s `DependencyType` enum has the explicit warning. A single small doc-only PR upstream adding a uniform `/* IMPORTANT: This is the on-disk value; do not change. */` comment to each block would close two-thirds of this register.
- **Phase D data-leak surface.** The five `likely`-severity entries (pg_statistic, pg_statistic_ext_data, pg_parameter_acl, pg_replication_origin overflow, pg_control versioning) are the most concrete starting points for the data-leak hardening project. The pg_parameter_acl canonicalization is probably the most interesting — if GRANT-time and SET-time normalize GUC names differently, it's a silent bypass vector.
- **Direct C-struct access pun.** pg_proc.proargtypes / pg_index.indkey / pg_partitioned_table.partattrs all rely on a fragile struct-offset invariant. A `StaticAssertStmt` on each offset would make it compile-time-checked.
- The propgraph family (5 new PG18+ catalogs) all have empty header comment blocks — clear documentation debt upstream. Possible coordinated docs patch.
