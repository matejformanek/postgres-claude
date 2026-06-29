# pg_subscription_rel.h

- **Source path:** `source/src/include/catalog/pg_subscription_rel.h`
- **Last verified commit:** `4b0bf0788b0`

## Purpose

"Definition of the system catalog containing the state for each replicated table in each subscription (pg_subscription_rel)." `[from-comment]` Tracks per-(subscription, relation) tablesync / apply progress. Per-DB even though `pg_subscription` itself is shared.

## Catalog definition

- `CATALOG(pg_subscription_rel,6102,SubscriptionRelRelationId)` — per-DB. No special BKI markings. `[verified-by-code]` `pg_subscription_rel.h:33`
- `FormData_pg_subscription_rel` typedef. Pointer alias: `Form_pg_subscription_rel`. `[verified-by-code]`

## Columns

| Column | Type | BKI marking | LOOKUP target |
|---|---|---|---|
| srsubid | Oid | `BKI_LOOKUP` | `pg_subscription` |
| srrelid | Oid | `BKI_LOOKUP` | `pg_class` |
| srsubstate | char | — | — (see `SUBREL_STATE_*`) |
| srsublsn | XLogRecPtr | (varlena pseudo) `BKI_FORCE_NULL` | — |

`srsublsn` is fixed-width but listed in the `#ifdef CATALOG_VARLEN` block because it is allowed to be NULL; the header comment notes this prevents direct C-struct access. `[from-comment]` `pg_subscription_rel.h:39-49`

## Key declarations beyond FormData

- No oid column → composite PK only: `pg_subscription_rel_srrelid_srsubid_index` (6117, unique on (srrelid, srsubid)). `[verified-by-code]`
- Syscache: `SUBSCRIPTIONRELMAP`. `[verified-by-code]`
- **On-disk char constants** under `#ifdef EXPOSE_TO_CLIENT_CODE` `pg_subscription_rel.h:60-80`:
  - **Stored states:** `SUBREL_STATE_INIT 'i'` (sublsn NULL), `SUBREL_STATE_DATASYNC 'd'` (NULL), `SUBREL_STATE_FINISHEDCOPY 'f'` (NULL), `SUBREL_STATE_SYNCDONE 's'` (sublsn set), `SUBREL_STATE_READY 'r'` (sublsn set). `[verified-by-code]`
  - **IPC-only (never stored)**, explicitly called out by header comment: `SUBREL_STATE_UNKNOWN '\0'`, `SUBREL_STATE_SYNCWAIT 'w'`, `SUBREL_STATE_CATCHUP 'c'`. `[from-comment]` `pg_subscription_rel.h:75`
- In-memory structs:
  - `SubscriptionRelState` — {relid, lsn, state}. `[verified-by-code]`
  - `LogicalRepSequenceInfo` — local + publisher-side sequence state used during sequence sync. `[verified-by-code]` `pg_subscription_rel.h:93-110`
- Function prototypes: `AddSubscriptionRelState`, `UpdateSubscriptionRelState`, `GetSubscriptionRelState`, `RemoveSubscriptionRel`, `HasSubscriptionTables`, `GetSubscriptionRelations`, `UpdateDeadTupleRetentionStatus`. `[verified-by-code]`

## Cross-refs

- Parent overview: `knowledge/files/src/include/catalog/_catalog_headers_overview.md`
- `knowledge/files/src/include/catalog/pg_subscription.h.md` (parent, shared)
- `knowledge/subsystems/replication.md` (when written)

<!-- issues:auto:begin -->
- [Issue register — `catalog`](../../../../issues/catalog.md)
<!-- issues:auto:end -->

## Potential issues

- **[ISSUE-undocumented-invariant: SUBREL_STATE_* letters are on-disk values]** `pg_subscription_rel.h:66-73` — the five stored state characters are written directly into `srsubstate` and persisted. The header does call out which states leave `sublsn` NULL vs set, but does not say "do not change these letters" — a future patch swapping 'd' and 'f' would silently mis-classify every existing replica's tablesync progress on upgrade.
- **[ISSUE-state-vs-LSN coupling]** `pg_subscription_rel.h:66-73` — INIT/DATASYNC/FINISHEDCOPY have NULL `srsublsn`; SYNCDONE/READY have a valid LSN. This invariant is encoded only as a parenthetical in the macro comments; nothing in `FormData_pg_subscription_rel` enforces it. Callers reading `srsublsn` must check `srsubstate` first or use the `Datum`-level NULL test (not the struct field, which is hidden behind CATALOG_VARLEN precisely to force this).

## Tally

`[verified-by-code]=8 [from-comment]=3`

## Synthesized by
<!-- backlinks:auto -->
- [idioms/tablesync-initial-copy.md](../../../../idioms/tablesync-initial-copy.md)
