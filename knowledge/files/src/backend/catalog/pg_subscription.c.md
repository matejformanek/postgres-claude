# pg_subscription.c

- **Source path:** `source/src/backend/catalog/pg_subscription.c`
- **Lines:** ~700
- **Last verified commit:** `ef6a95c7c64`

## Purpose

"Replication subscriptions." pg_subscription (shared catalog) + pg_subscription_rel (per-DB) maintenance. Subscriptions identify a publisher conninfo + slot + a list of publications; pg_subscription_rel tracks per-table sync state (INIT, DATASYNC, FINISHEDCOPY, SYNCDONE, READY).

## Public surface

- `GetSubscription` (77) — fetch a Subscription struct by OID, decoding the text-array fields (publications, connection-info).
- `GetPublicationsStr` (46) — encode a publications list back to text.
- `CountDBSubscriptions` (205) — # subscriptions in a DB (used by DROP DATABASE check).
- `DisableSubscription` (237) — set subenabled=false.
- `textarray_to_stringlist` (278) — helper.
- `AddSubscriptionRelState` (304), `UpdateSubscriptionRelState` (358), `GetSubscriptionRelState` (424), `RemoveSubscriptionRel` (474) — per-(subid, relid) tablesync state row management.
- `HasSubscriptionTables` (553), `GetSubscriptionRelations` (602) — bulk lookups for the apply worker.
- `UpdateDeadTupleRetentionStatus` (679) — track whether the subscription needs cluster-wide dead-tuple retention for conflict detection.

## Confidence tag tally

`[verified-by-code]=3`
