# `src/backend/utils/activity/pgstat_replslot.c`

- **Last verified commit:** `ef6a95c7c64`
- **Lines:** ~250
- **Source:** `source/src/backend/utils/activity/pgstat_replslot.c`

Backs `pg_stat_replication_slots`. **Identifier oddity**: replication
slots have no oid (must work on physical replicas), so the running key
is the **slot index** (`objid = slot_index`). But slot indexes can change
across restart, so the on-disk serialization uses the slot **name**
instead — via the `to_serialized_name_cb` / `from_serialized_name_cb`
vtable slots in `PgStat_KindInfo`.

On restart, if a serialized slot name doesn't resolve to a current slot
(e.g. slot was dropped), the entry is discarded. [from-comment]
(`pgstat_replslot.c:11-15`)

Counters: `spill_txns`, `spill_count`, `spill_bytes`, `stream_txns`,
`stream_count`, `stream_bytes`, `total_txns`, `total_bytes`, also
`stats_reset`. Updated by the logical-decoding ReorderBuffer.
