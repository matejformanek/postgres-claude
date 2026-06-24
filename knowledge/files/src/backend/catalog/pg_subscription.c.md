# pg_subscription.c

- **Source path:** `source/src/backend/catalog/pg_subscription.c`
- **Lines:** ~728
- **Last verified commit:** `9a60f295bcb1`

## Purpose

"Replication subscriptions." pg_subscription (shared catalog) + pg_subscription_rel (per-DB) maintenance. Subscriptions identify a publisher conninfo + slot + a list of publications; pg_subscription_rel tracks per-table sync state (INIT, DATASYNC, FINISHEDCOPY, SYNCDONE, READY).

## Public surface

- `GetSubscription` (88) — fetch a Subscription struct by OID, decoding the text-array fields (publications, connection-info).
- `GetPublicationsStr` (50) — encode a publications list back to text.
- `CountDBSubscriptions` (221) — # subscriptions in a DB (used by DROP DATABASE check).
- `DisableSubscription` (253) — set subenabled=false.
- `textarray_to_stringlist` (294) — helper.
- `AddSubscriptionRelState` (320), `UpdateSubscriptionRelState` (374), `GetSubscriptionRelState` (440), `RemoveSubscriptionRel` (490) — per-(subid, relid) tablesync state row management.
- `HasSubscriptionTables` (569), `GetSubscriptionRelations` (618) — bulk lookups for the apply worker. `GetSubscriptionRelations(subid, tables, sequences, not_ready)` now takes `bool tables` / `bool sequences` selectors (sequence-replication support added since `ef6a95c7c64`), returning rels filtered by kind.
- `UpdateDeadTupleRetentionStatus` (695) — track whether the subscription needs cluster-wide dead-tuple retention for conflict detection.

## Confidence tag tally

`[verified-by-code]=3`

## Synthesized by
<!-- backlinks:auto -->
- [subsystems/optimizer.md](../../../../subsystems/optimizer.md)
