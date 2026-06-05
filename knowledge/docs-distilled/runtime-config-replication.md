---
source_url: https://www.postgresql.org/docs/current/runtime-config-replication.html
fetched_at: 2026-06-04T18:55:00Z
anchor_sha: 4b0bf0788b066a4ca1d4f959566678e44ec93422
distilled_by: pg-docs-miner (cloud routine)
docs_version: current (PG18)
primary: true
---

# Docs distilled — §20.6 Replication configuration

The replication GUC reference, distilled to the surprising semantics. This
chapter directly reinforces several `knowledge/issues/include-replication.md`
findings (the `max_slot_wal_keep_size=-1` unbounded-retention trap and the
`primary_conninfo` plaintext-password concern), so it's cross-linked there.

## Sending server

- **`max_slot_wal_keep_size=-1` (default) = slots may retain WAL without bound.**
  Only a positive value caps it. An abandoned persistent slot whose `restart_lsn`
  falls behind can hold `pg_wal` until the disk fills. There is no per-role slot
  quota. [from-docs] [cross-link knowledge/issues/include-replication.md — same
  finding surfaced from xlog.c:142 / postgresql.conf.sample]
- **`wal_keep_size=0` (default) keeps no extra segments for standbys** —
  retention is then a side effect of checkpoint position + archiving status, not
  an explicit guarantee. Slots (above) are the durable mechanism. [from-docs]
- **`max_replication_slots` below the current slot count blocks startup**; same
  shape for `max_wal_senders` and orphaned sender slots, which linger until
  `wal_sender_timeout` — so set senders slightly above expected client count to
  allow immediate reconnect. [from-docs]
- **`track_commit_timestamp` is start-only** and carries always-on overhead once
  enabled — can't be toggled per-session. [from-docs]

## Primary server — synchronous replication

- **`synchronous_standby_names` `FIRST k (...)` is priority-based**: commit waits
  for the k highest-priority listed standbys; a disconnected sync standby is
  *immediately* replaced by the next-highest candidate. [from-docs]
- **`ANY k (...)` is quorum-based**: commit proceeds once *any* k of the listed
  standbys reply, ignoring priority. [from-docs]
- **`*` matches any standby name; names are not required unique** — duplicates
  give indeterminate priority. [from-docs]
- **`synchronized_standby_slots`**: a logical walsender waits for the named
  *physical* slots to confirm receipt before sending decoded changes; if a listed
  slot is missing or invalidated, logical replication blocks entirely. [from-docs]

## Standby server

- **`primary_conninfo` carries the connection string including a plaintext
  password** (or uses `~/.pgpass`); a valid `dbname` is needed only for slot sync
  (ignored for streaming WAL receipt). [from-docs] [cross-link
  knowledge/issues/include-replication.md — the walreceiver shared-memory
  plaintext-window finding (walreceiverfuncs.c:311 → walreceiver.c:278 memset)]
- **`max_standby_archive_delay` / `max_standby_streaming_delay` are per-WAL-data
  budgets, NOT per-query timeouts.** The grace time is for applying a whole
  segment's data; an early slow query eats into the budget left for later
  conflicting queries. Delay accumulates, not reset per query. [from-docs]
- **`hot_standby_feedback` is throttled to once per
  `wal_receiver_status_interval`**; if the standby clock jumps, feedback timing
  breaks down and dead rows can accumulate on the primary. [from-docs]
- **`recovery_min_apply_delay` delays only COMMIT records** — other WAL replays
  immediately (MVCC keeps the early replay invisible). WAL must accumulate on
  disk until applied, so a long delay inflates `pg_wal`. Combined with
  `synchronous_commit=remote_apply`, every COMMIT waits for *both* replication
  and the apply delay. [from-docs]
- **`sync_replication_slots=true`** on a physical standby is what lets it receive
  logical failover-slot changes so logical subscribers can resume after a
  promotion. [from-docs]

## Subscriber

- **One worker pool, three claimants.** `max_logical_replication_workers` counts
  leader apply workers **plus** parallel apply workers **plus** table-sync
  workers — all drawn from `max_worker_processes`.
  `max_sync_workers_per_subscription` and
  `max_parallel_apply_workers_per_subscription` carve from that *same* pool, so
  they contend rather than getting separate allocations. [from-docs]

## Links into corpus

- [[knowledge/issues/include-replication.md]] — the corpus issue register that
  this chapter reinforces (`max_slot_wal_keep_size=-1`, `primary_conninfo`
  plaintext window, REPLICATION-role WAL reach).
- [[knowledge/subsystems/replication.md]] — walsender/walreceiver/slot internals.
- [[knowledge/architecture/replication.md]] — physical vs logical overview.
- [[knowledge/docs-distilled/runtime-config-wal.md]] — `max_wal_senders` /
  `wal_keep_size` are introduced there too.
- Skill: `replication-overview` — code-level walsender/walreceiver/decoding map.

## Confidence note

All claims `[from-docs]` (§20.6, fetched 2026-06-04). The two cross-links into
`issues/include-replication.md` are the strongest reinforcement value of this
doc — the docs chapter confirms, from the user-facing side, two security
findings the A8 sweep surfaced from source. Defaults quoted as on the page.
</content>
