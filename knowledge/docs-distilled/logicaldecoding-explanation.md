---
source_url: https://www.postgresql.org/docs/current/logicaldecoding-explanation.html
fetched_at: 2026-06-13T19:50:00Z
anchor_sha: e18b0cb
distilled_by: pg-docs-miner (cloud routine)
docs_version: current (PG18)
primary: true
---

# Logical Decoding Concepts (internals ch. 49.1–49.2)

The conceptual front door to logical decoding: what a logical slot *is*, what it
retains, and the durability/idempotency contract a consumer signs up for. Pairs
with the output-plugin and streaming chapters and the `replication.md` subsystem
doc. This is the "why" layer under `reorderbuffer.c` / `snapbuild.c` / `logical.c`.

## Non-obvious claims

- **A logical slot streams changes from exactly one database**, but its identifier
  is **unique across all databases in the cluster**. Only **one receiver may
  consume a slot at a time**. [from-docs]
- **Slot position is persisted only at checkpoint.** After a crash a slot can
  rewind to an earlier LSN and **re-send already-delivered changes** — so the
  consumer is **responsible for idempotency / dedup**. Each change is emitted
  "just once" only in normal (no-crash) operation. [from-docs] This is the single
  most load-bearing fact for anyone building on top of decoding.
- **Slots hold back resource reclamation.** A slot prevents `VACUUM` from removing
  still-needed WAL *and* system-catalog rows, and can ultimately force a shutdown
  to avoid XID wraparound. **Unused slots must be dropped** — they are not
  self-cleaning. [from-docs]
- **`catalog_xmin`** is the minimum XID whose catalog rows must be retained so the
  decoder can still interpret old tuples. On a standby, the slot's `catalog_xmin`
  must be fed back to the primary (`hot_standby_feedback = on`) or the primary may
  vacuum away rows the standby's decoder still needs → slot invalidation. [from-docs]
- **Snapshot export at slot creation:** creating a slot via the streaming-replication
  command `CREATE_REPLICATION_SLOT` exports a snapshot marking the exact DB state
  after which all changes appear in the stream; combine with
  `SET TRANSACTION SNAPSHOT` to take a consistent base dump, or suppress with
  `SNAPSHOT 'nothing'`. This is how you build a replica with no gap. [from-docs]
- **Changes are decoded in commit order**, and only for **committed** transactions
  on **non-unlogged, non-temporary user tables**. Aborted transactions are never
  decoded. [from-docs] (Detail elaborated in the output-plugin chapter.)
- **Slots on hot standby** (PG16+): creatable, but invalidated if the primary
  drops below `wal_level = logical`, or if required catalog rows are removed.
  Creation can block waiting for primary WAL activity; `pg_log_standby_snapshot()`
  on the primary unblocks it. [from-docs]
- **Failover slot sync** (PG17+): set `failover` on the slot + `sync_replication_slots
  = on` on the standby; requires a physical slot via `primary_slot_name`,
  `hot_standby_feedback = on`, and a valid `dbname` in `primary_conninfo`. Only
  **persistent** slots with `synced = true` survive a failover — temporary synced
  slots cannot be decoded post-promotion. `pg_sync_replication_slots()` is
  test/debug-only (no cyclic retries). [from-docs]

## Links into corpus

- Subsystem: [[knowledge/subsystems/replication.md]] (physical + logical overview),
  [[knowledge/subsystems/access-transam.md]] (XID/`catalog_xmin` retention context).
- Per-file: [[knowledge/files/src/backend/replication/logical/snapbuild.c.md]]
  (the exported-snapshot / consistent-point machinery),
  [[knowledge/files/src/backend/replication/logical/reorderbuffer.c.md]]
  (commit-order reassembly), [[knowledge/files/src/backend/replication/logical/logical.c.md]],
  [[knowledge/files/src/backend/replication/slot.c.md]] (slot persistence at checkpoint),
  [[knowledge/files/src/backend/replication/logical/slotsync.c.md]] (failover sync).
- Siblings: `knowledge/docs-distilled/logicaldecoding-output-plugin.md`,
  `knowledge/docs-distilled/logicaldecoding-streaming.md`,
  `knowledge/docs-distilled/protocol-logical-replication.md`.
- Code anchors [unverified — not line-pinned this run]:
  `source/src/backend/replication/slot.c`,
  `source/src/backend/replication/logical/snapbuild.c`.
