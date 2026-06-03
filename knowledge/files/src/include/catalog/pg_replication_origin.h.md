# pg_replication_origin.h

- **Source path:** `source/src/include/catalog/pg_replication_origin.h`
- **Last verified commit:** `4b0bf0788b0`

## Purpose

"Definition of the 'replication origin' system catalog (pg_replication_origin)." `[from-comment]` Names the upstream sources whose changes a logical apply worker (or any client) is replaying, so progress (LSN) can be tracked durably per source and so WAL records can be tagged with the origin that produced them.

## Catalog definition

- `CATALOG(pg_replication_origin,6000,ReplicationOriginRelationId) BKI_SHARED_RELATION` — **SHARED.** `[verified-by-code]` `pg_replication_origin.h:32`
- `FormData_pg_replication_origin` typedef. Pointer alias: `Form_pg_replication_origin`. `[verified-by-code]`
- No `oid` column. PK is `roident` (manually allocated, see below). `[verified-by-code]`

## Columns

| Column | Type | BKI marking | LOOKUP target |
|---|---|---|---|
| roident | Oid | — | — (locally-assigned WAL-embedded id; uint16-sized; manual allocation) |
| roname | text | `BKI_FORCE_NOT_NULL` (direct access allowed) | — |

The header explicitly notes `roname` is variable-length but direct-access is permitted; the `#ifdef CATALOG_VARLEN` block is empty (placeholder for future fields). `[from-comment]` `pg_replication_origin.h:46-54`

## Key declarations beyond FormData

- Header-comment invariant on `roident` (load-bearing): "Locally known id that gets included into WAL. This should never leave the system. Needs to fit into an uint16, so we don't waste too much space in WAL records. For this reason we don't use a normal Oid column here, since we need to handle allocation of new values manually." `[from-comment]` `pg_replication_origin.h:34-42`
- Indexes: `pg_replication_origin_roiident_index` (PK, 6001, btree on roident); `pg_replication_origin_roname_index` (6002, btree on roname). `[verified-by-code]`
- Syscaches: `REPLORIGIDENT`, `REPLORIGNAME`. `[verified-by-code]`
- No function prototypes here — the runtime API lives in `replication/origin.h`.

## Cross-refs

- Parent overview: `knowledge/files/src/include/catalog/_catalog_headers_overview.md`
- `knowledge/files/src/include/catalog/pg_subscription.h.md` (`suborigin` filters by origin name; values `LOGICALREP_ORIGIN_NONE`/`_ANY` are sentinels)
- Runtime: `source/src/include/replication/origin.h`, `source/src/backend/replication/logical/origin.c`
- `knowledge/subsystems/replication.md` (when written)

## Potential issues

- **[ISSUE-WAL-embedded-id-uint16-cap]** `pg_replication_origin.h:34-42` — `roident` is allocated by hand specifically to fit in a uint16 because WAL records carry it. A cluster with > ~65k origins will eventually run out of identifiers; allocation logic must reuse / refuse, and the header gives no link to where that logic actually lives (`origin.c`). Worth flagging in any future "many subscriptions" design.
- **[ISSUE-shared-catalog-WAL-leak-vector]** — because `roident` is shared and embedded in WAL, a logical decoding consumer that mis-translates origin ids across a basebackup / promotion boundary can attribute changes to the wrong upstream. The header comment "This should never leave the system" is the only guard. Cross-cluster logical-replication tooling that exports origin names is correct only if it re-resolves via `roname`, never via the numeric id.

## Tally

`[verified-by-code]=5 [from-comment]=3`
