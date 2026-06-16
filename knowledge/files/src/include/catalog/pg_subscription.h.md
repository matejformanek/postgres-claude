# pg_subscription.h

- **Source path:** `source/src/include/catalog/pg_subscription.h`
- **Last verified commit:** `4b0bf0788b0`

## Purpose

"Definition of the 'subscription' system catalog (pg_subscription)." `[from-comment]` Per the header comment: "Technically, the subscriptions live inside the database, so a shared catalog seems weird, but the replication launcher process needs to access all of them to be able to start the workers, so we have to put them in a shared, nailed catalog." `[from-comment]` `pg_subscription.h:32-37`

## Catalog definition

- `CATALOG(pg_subscription,6100,SubscriptionRelationId) BKI_SHARED_RELATION BKI_ROWTYPE_OID(6101,SubscriptionRelation_Rowtype_Id) BKI_SCHEMA_MACRO` — **SHARED, nailed.** `[verified-by-code]` `pg_subscription.h:45`
- `FormData_pg_subscription` typedef. Pointer alias: `Form_pg_subscription`. `[verified-by-code]`
- **CAUTION (per header):** "There is a GRANT in system_views.sql to grant public select access on all columns except subconninfo. When you add a new column here, be sure to update that…" `[from-comment]` `pg_subscription.h:38-42`

## Columns

| Column | Type | BKI marking | LOOKUP target |
|---|---|---|---|
| oid | Oid | — | — |
| subdbid | Oid | `BKI_LOOKUP` | `pg_database` |
| subskiplsn | XLogRecPtr | — | — (LSN past which to skip) |
| subname | NameData | — | — |
| subowner | Oid | `BKI_LOOKUP` | `pg_authid` |
| subenabled | bool | — | — |
| subbinary | bool | — | — |
| substream | char | — | — (see `LOGICALREP_STREAM_*`) |
| subtwophasestate | char | — | — (see `LOGICALREP_TWOPHASE_STATE_*`) |
| subdisableonerr | bool | — | — |
| subpasswordrequired | bool | — | — |
| subrunasowner | bool | — | — |
| subfailover | bool | — | — (slot sync to standbys) |
| subretaindeadtuples | bool | — | — (conflict detection) |
| submaxretention | int32 | — | — (ms) |
| subretentionactive | bool | — | — |
| subserver | Oid | `BKI_LOOKUP_OPT` | `pg_foreign_server` |
| subconninfo | text | (varlena) | — (libpq conninfo; PUBLIC SELECT denied) |
| subslotname | NameData | (varlena) `BKI_FORCE_NULL` | — |
| subsynccommit | text | (varlena) `BKI_FORCE_NOT_NULL` | — |
| subwalrcvtimeout | text | (varlena) `BKI_FORCE_NOT_NULL` | — |
| subpublications | text[1] | (varlena) `BKI_FORCE_NOT_NULL` | — |
| suborigin | text | (varlena) `BKI_DEFAULT(LOGICALREP_ORIGIN_ANY)` | — |

## Key declarations beyond FormData

- `DECLARE_TOAST_WITH_MACRO(pg_subscription, 4183, 4184, PgSubscriptionToastTable, PgSubscriptionToastIndex)` — shared TOAST. `[verified-by-code]`
- Indexes: `pg_subscription_oid_index` (PK, 6114); `pg_subscription_subname_index` (6115, unique on (subdbid, subname) — name uniqueness is per-DB even though the catalog is shared). `[verified-by-code]`
- Syscaches: `SUBSCRIPTIONOID`, `SUBSCRIPTIONNAME`. `[verified-by-code]`
- **On-disk char + string constants** (under `#ifdef EXPOSE_TO_CLIENT_CODE`) — changing any value silently corrupts existing subscriptions: `[verified-by-code]` `pg_subscription.h:176-213`
  - Two-phase state: `LOGICALREP_TWOPHASE_STATE_DISABLED 'd'`, `..._PENDING 'p'`, `..._ENABLED 'e'`.
  - Origin filter strings: `LOGICALREP_ORIGIN_NONE "none"`, `LOGICALREP_ORIGIN_ANY "any"` (stored in `suborigin`).
  - Stream mode: `LOGICALREP_STREAM_OFF 'f'`, `LOGICALREP_STREAM_ON 't'`, `LOGICALREP_STREAM_PARALLEL 'p'`.
- In-memory descriptor: `Subscription` struct — runtime cache form with its own `MemoryContext cxt`; mirrors all FormData fields plus `ownersuperuser`. `[verified-by-code]` `pg_subscription.h:131-174`
- Function prototypes: `GetSubscription`, `DisableSubscription`, `CountDBSubscriptions`, `GetPublicationsStr`. `[verified-by-code]`

## Cross-refs

- Parent overview: `knowledge/files/src/include/catalog/_catalog_headers_overview.md`
- `knowledge/files/src/include/catalog/pg_subscription_rel.h.md` (per-(sub, rel) sync state — per-DB sibling)
- `knowledge/files/src/include/catalog/pg_replication_origin.h.md` (tracks LSN per origin)
- `knowledge/files/src/include/catalog/pg_publication.h.md` (publisher side)
- `knowledge/subsystems/replication.md` (when written)

<!-- issues:auto:begin -->
- [Issue register — `catalog`](../../../../issues/catalog.md)
<!-- issues:auto:end -->

## Potential issues

- **[ISSUE-shared-but-name-scoped: subscription name uniqueness is per-DB on a shared catalog]** `pg_subscription.h:126` — the unique index is `(subdbid, subname)`, so two different databases can each have a subscription named "sub1". Code paths that look up by name alone must always pass `MyDatabaseId` for `subdbid` or they'll match the wrong row. The replication launcher walks the whole shared catalog (per the header comment), so this is load-bearing — any future "look up sub by name" helper needs the dbid scope.
- **[ISSUE-acl-coupling-with-system_views.sql: adding a column risks leaking secrets via PUBLIC SELECT]** `pg_subscription.h:38-42` — the in-header CAUTION says additions must be reflected in `system_views.sql` GRANT. If a new column (e.g. an auth token, a new conninfo-like field) is added without the matching GRANT-exclude, every database user can read it. This is a recurring foot-gun called out only in a comment block.
- **[ISSUE-undocumented-invariant: `substream` / `subtwophasestate` are on-disk chars]** `pg_subscription.h:182-211` — the `LOGICALREP_STREAM_*` and `LOGICALREP_TWOPHASE_STATE_*` macros are stored verbatim. The macros sit under `EXPOSE_TO_CLIENT_CODE` but neither block carries an "on-disk format" warning. Future maintainers reassigning letters (e.g. recycling 'p' across both groups) would break upgrades.

## Tally

`[verified-by-code]=10 [from-comment]=3`
