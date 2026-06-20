---
source_url: https://www.postgresql.org/docs/current/logicaldecoding-example.html
fetched_at: 2026-06-19T18:50:00Z
anchor_sha: bdae2c20e88d
distilled_by: pg-docs-miner (cloud routine)
docs_version: current (PG18)
primary: true
---

# Logical Decoding Examples (logical-decoding ch. 49.1)

The worked walkthrough that opens §49 — the operational lessons (slot lifecycle,
WAL retention, get-vs-peek, two-phase) distilled from the example transcript,
not the transcript itself. Uses the `test_decoding` contrib plugin (the canonical
reference output plugin).

## Slot lifecycle (the operational arc)

- **Create:** `pg_create_logical_replication_slot('regression_slot',
  'test_decoding', false, true)` — binds the slot to an output plugin; from this
  point the slot **holds back WAL**. [from-docs]
- **Inspect:** `pg_replication_slots` shows `restart_lsn` (oldest WAL the slot
  needs) and `confirmed_flush_lsn` (consumer's confirmed position). [from-docs]
- **Consume:** `pg_logical_slot_get_changes(...)` returns and advances;
  `pg_logical_slot_peek_changes(...)` returns the same rows without advancing.
  [from-docs]
- **Drop:** `pg_drop_replication_slot('regression_slot')` — **required** to stop
  the slot consuming server resources. [from-docs]
- **The headline hazard:** an unconsumed (or never-dropped) slot retains WAL back
  to `restart_lsn` **indefinitely**, bloating `pg_wal`. A logical slot is a
  standing WAL pin until consumed or dropped. [from-docs]

## test_decoding output shape

```
BEGIN <xid>
table public.data: INSERT: id[integer]:1 data[text]:'1'
table public.data: INSERT: id[integer]:2 data[text]:'2'
COMMIT <xid>
```

- Each change is `table <schema>.<table>: <OP>: <col>[<type>]:<value> ...`
  wrapped in `BEGIN <xid>` / `COMMIT <xid>`. [from-docs]
- Options tune the framing: `'include-timestamp', 'on'` appends the commit
  timestamp (`COMMIT 10299 (at ...)`); `include-xids` controls the xid display.
  [from-docs]

## pg_recvlogical (the streaming client)

- `pg_recvlogical --slot=NAME --create-slot` creates over the replication
  protocol; `--start -f -` streams continuously to stdout. [from-docs]
- Requires `max_wal_senders` configured and replication authentication; uses the
  walsender commands internally (see `logicaldecoding-walsender.md`). [from-docs]

## Two-phase decoding

- Enable with the slot's `twophase` flag (`pg_create_logical_replication_slot(...,
  true)`) or `pg_recvlogical --enable-two-phase`; needs
  `max_prepared_transactions >= 1`. [from-docs]
- Output then includes `PREPARE TRANSACTION '<name>', txid <xid>`,
  `COMMIT PREPARED '<name>', txid <xid>`, `ROLLBACK PREPARED '<name>', txid
  <xid>`. If a prepared xact was not already decoded, the **entire transaction is
  streamed after the commit**. [from-docs]

## Links into corpus

- [[knowledge/docs-distilled/logicaldecoding-sql.md]] — get/peek/drop function
  reference behind this walkthrough.
- [[knowledge/docs-distilled/logicaldecoding-walsender.md]] — the protocol
  commands `pg_recvlogical` drives.
- [[knowledge/docs-distilled/logicaldecoding-explanation.md]] — concepts
  (slots, restart_lsn, catalog_xmin) the WAL-retention hazard rests on.
- [[knowledge/idioms/replication-slot-advance.md]] — confirmed_flush advance =
  WAL release.
- [[knowledge/subsystems/contrib-pg_logicalinspect.md]] — inspecting decoded
  output / slots.
- [[knowledge/idioms/prepare-transaction-2pc.md]] — the 2PC machinery the
  two-phase decoding mirrors.

## Open questions

- The example implies a slot pins `catalog_xmin` as well as `restart_lsn`;
  confirm the catalog-xmin retention path against
  `logicaldecoding-explanation.md` at anchor `bdae2c20e88d`.
