# `src/include/utils/rel.h`

**Pin:** `4b0bf0788b066a4ca1d4f959566678e44ec93422`

## Role

THE backend's per-relation cache entry — `RelationData` (a/k/a
"relcache entry") [from-comment: lines 1-5]. Every open relation in
this backend is represented by exactly one `RelationData`. Holds
file locator, AM dispatch, tupdesc, trigger desc, RLS desc, partition
key/desc, FK list, index/stats lists, attribute bitmaps, publication
desc, reloptions — basically every cached fact about a relation.

## Public API (selected — file is 731 lines)

### `RelationData` [verified-by-code: lines 55-256]

Physical: `rd_locator` (RelFileLocator), `rd_smgr` (cached file
handle), `rd_backend` (proc# for temp rels), `rd_islocaltemp`,
`rd_isnailed` (cannot be evicted), `rd_isvalid`.

Subxact tracking (lines 68-109): `rd_createSubid`,
`rd_newRelfilelocatorSubid`, `rd_firstRelfilelocatorSubid`,
`rd_droppedSubid` — control whether `RelationNeedsWAL()` may skip
WAL by relying on copying the whole relation at commit.

Core: `rd_rel` (Form_pg_class), `rd_att` (TupleDesc), `rd_id` (OID),
`rd_lockInfo`.

Caches:
- `rd_rules` + `rd_rulescxt` — rewrite rules.
- `trigdesc` — TriggerDesc, or NULL.
- `rd_rsdesc` — RowSecurityDesc (RLS), or NULL.
- `rd_fkeylist` + `rd_fkeyvalid` — ForeignKeyCacheInfo list.
- `rd_partkey` + `rd_partkeycxt`, `rd_partdesc` + `rd_pdcxt`,
  `rd_partdesc_nodetached` + `rd_pddcxt` (partitioning).
- `rd_partcheck` + `rd_partcheckvalid` + `rd_partcheckcxt`
  (partition CHECK quals).
- `rd_indexlist`, `rd_pkindex`, `rd_ispkdeferrable`,
  `rd_replidindex`, `rd_statlist`.
- Attribute bitmaps: `rd_keyattr`, `rd_pkattr`, `rd_idattr`,
  `rd_hotblockingattr`, `rd_summarizedattr`.
- `rd_pubdesc` — PublicationDesc.

Options: `rd_options` (parsed `pg_class.reloptions`, `bytea *`,
NULL ⇒ defaults) [lines 170-175].

AM: `rd_amhandler`, `rd_tableam` (TableAmRoutine), `rd_indam`
(IndexAmRoutine, indexes only), `rd_opfamily`, `rd_opcintype`,
`rd_support`, `rd_supportinfo`, `rd_indoption`, `rd_indexprs`,
`rd_indpred`, `rd_exclops`, `rd_exclprocs`, `rd_exclstrats`,
`rd_indcollation`, `rd_opcoptions`, `rd_amcache` (AM-private cache,
resetable).

Foreign: `rd_fdwroutine` (FdwRoutine *).

Rewrite hack: `rd_toastoid` (lines 242-251) — non-Invalid when
writing a CLUSTER/rewrite version, redirects toast inserts to the
existing TOAST OID.

Stats: `pgstat_enabled`, `pgstat_info`.

### Reloption variants

- `StdRdOptions` (lines 343-359) — heap reloptions:
  `fillfactor`, `toast_tuple_target`, embedded `AutoVacOpts`,
  `user_catalog_table`, `parallel_workers`,
  `vacuum_index_cleanup`, `vacuum_truncate`,
  `vacuum_max_eager_freeze_failure_rate`.
- `AutoVacOpts` (lines 311-333) — per-table autovacuum knobs.
- `ViewOptions` (lines 426-432) — view reloptions:
  `security_barrier`, `security_invoker`, `check_option`.
- `ViewOptCheckOption` enum — NOT_SET / LOCAL / CASCADED.

### Macros

- `RelationGetFillFactor(rel, default)`, `RelationGetToastTupleTarget`,
  `RelationGetTargetPageUsage`, `RelationGetTargetPageFreeSpace`,
  `RelationIsUsedAsCatalogTable`, `RelationGetParallelWorkers`,
  `RelationIsSecurityView`, `RelationHasSecurityInvoker`,
  `RelationHasCheckOption`, `RelationHasLocalCheckOption`,
  `RelationHasCascadedCheckOption`.
- `RelationIsValid`, `RelationHasReferenceCountZero`,
  `RelationGetForm`, `RelationGetRelid`.

All these macros have the **multiple-eval-of-argument** warning in
their comments — must be passed a simple variable, not a function
call.

## Invariants

- **INV-NAILED** [from-comment: line 62] Nailed catalogs cannot be
  evicted from relcache; required for bootstrap circularity.
- **INV-AMCACHE** [from-comment: lines 220-228] `rd_amcache` is
  reset on relcache inval — AMs must tolerate sudden NULL.
- **INV-FDWROUTINE** [from-comment: lines 232-237] `rd_fdwroutine`
  is a single palloc'd chunk in `CacheMemoryContext`; reset on
  relcache invalidation.
- **INV-SUBXACT** [from-comment: lines 68-109] Accuracy of
  `rd_*Subid` is *critical to* `RelationNeedsWAL()`. Code that
  changes `rd_locator` must call `RelationAssumeNewRelfilelocator()`.
- **INV-VIEWOPT-RELKIND** [verified-by-code: lines 440-485] All
  `RelationIs*` view-option macros assert
  `relkind == RELKIND_VIEW` — using them on non-views is a bug
  caught only by `AssertMacro` in cassert builds.

## Trust boundary (Phase D)

- **`rd_options` deserialization** [lines 170-175]: `bytea *` parsed
  from `pg_class.reloptions`. Parsing happens in
  `relation_parse_reloptions` (in `reloptions.c`, not here). A
  malformed reloption blob in the catalog (only writable by
  superuser via direct `pg_class` UPDATE) could in principle confuse
  downstream macros that cast it to `StdRdOptions` / `ViewOptions`.
- **`rd_indpred`/`rd_indexprs` node trees** [lines 212-213]: loaded
  from `pg_index.indexprs` / `indpred` (`pg_node_tree` text);
  re-parsed via `stringToNode`. A corrupted catalog node tree can
  crash backend at index-open time. (Catalog corruption requires
  superuser or direct file modification.)
- **A7 finding — view re-emission gap**: `ViewOptions`
  (security_barrier, security_invoker, check_option) live in
  `rd_options` AND are surfaced via the macros here, but
  `pg_get_viewdef` (in `ruleutils.c`, declared in `ruleutils.h`)
  does **NOT** re-emit them when reconstructing the view DDL.
  Confirmed at header level: `ruleutils.h` shows no
  `pg_get_viewdef` *header* declaration (it's a SQL-callable in
  `ruleutils.c`); the omission of these clauses from the re-emitted
  text is a behavioral gap, not a header-level one.
- **Trigger / RLS / publication descriptors** are loaded from
  catalogs at relcache build; they carry function OIDs and qual
  trees that run later in caller's security context. The relcache
  itself doesn't enforce ACLs.
- **`rd_toastoid` rewrite hack** (lines 242-251): a stray non-Invalid
  value would misroute toast inserts to a foreign TOAST OID —
  reserved for CLUSTER/REWRITE codepaths.

## Cross-refs

- `utils/relcache.h` — public open/close API
  (`RelationIdGetRelation`, `RelationClose`, `RelationGetIndexList`,
  etc.).
- `access/tableam.h` / `access/amapi.h` — `rd_tableam`, `rd_indam`
  vtables.
- `utils/inval.h` — relcache invalidation broadcast.
- `catalog/pg_class.h`, `catalog/pg_index.h`, `catalog/pg_publication.h`
  — source-of-truth catalogs.
- `partitioning/partdefs.h` — partition key/desc.
- A8/A12 — pg_upgrade catalog-trust angle.

## Issues

- [ISSUE-PHASE-D: `ViewOptions` (security_barrier / security_invoker
  / check_option) are stored as reloptions and surfaced via macros,
  but `pg_get_viewdef` (ruleutils.c) does NOT round-trip them — a
  pg_dump'd view loses these security clauses unless the dumper
  pulls them from pg_class.reloptions separately (high, A7
  cross-finding)] — lines 426-485.
- [ISSUE-INV: every `RelationIs*View` macro asserts `relkind ==
  RELKIND_VIEW` only under `AssertMacro` (cassert-only);
  release-mode callers can silently read garbage (medium)] —
  lines 440-485.
- [ISSUE-DOC: multiple-eval-of-argument warning is repeated on every
  macro but not enforced — inline functions would be safer (low)] —
  passim.
- [ISSUE-DESIGN: `rd_toastoid` is documented as a "hack" — a
  release-mode mis-set would silently send toast pointers to the
  wrong OID (medium)] — lines 242-251.

## Synthesized by
<!-- backlinks:auto -->
- [idioms/relcache-build.md](../../../../idioms/relcache-build.md)
