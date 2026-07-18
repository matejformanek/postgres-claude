---
source_url: https://www.postgresql.org/docs/current/app-pgcreatesubscriber.html
fetched_at: 2026-07-18
anchor_sha: 03480907e9ff
app: src/bin/pg_basebackup/pg_createsubscriber.c
---

# pg_createsubscriber — convert a physical standby into a logical subscriber

Added PG 17. Takes an existing **physical streaming-replication standby** and
turns it into a **logical-replication subscriber** of its former primary, with
**no initial table-data copy** — the standby already *has* all the data, so the
tool only has to establish a consistent LSN handoff from physical replay to
logical apply. For a large database this skips the single most expensive part of
standing up a logical replica (the tablesync COPY).

## Non-obvious claims

- The whole trick is a **consistency-point handoff**: it creates a replication
  slot on the primary, captures that slot's LSN as `consistent_lsn`, then drives
  the standby's recovery to exactly that LSN and promotes — so logical apply
  begins precisely where physical replay stopped, with zero gap and zero overlap.
  `[verified-by-code source/src/bin/pg_basebackup/pg_createsubscriber.c:2674-2696]`
- Operational sequence (each a distinct function): `setup_publisher` creates one
  `CREATE PUBLICATION … FOR ALL TABLES` + one slot **per database** on the
  primary and returns `consistent_lsn`; `setup_recovery` writes
  `recovery_target_lsn = '<consistent_lsn>'` + `recovery_target_action = promote`
  and restarts the standby to catch up + promote; `setup_subscriber` creates a
  disabled subscription per database (reusing the existing slot, `copy_data =
  false`), advances each subscription's replication origin to `consistent_lsn`
  via `pg_replication_origin_advance`, then enables it.
  `[verified-by-code source/src/bin/pg_basebackup/pg_createsubscriber.c:1418,1427,1843,2112]`
- Default target (subscriber) port is **50432**, same "keep clients off the
  half-converted server" convention as pg_upgrade — during conversion the target
  runs with modified settings and normal client connections should fail.
  `[verified-by-code source/src/bin/pg_basebackup/pg_createsubscriber.c:35]`
- Auto-generated object names follow `pg_createsubscriber_%u_%x` where `%u` is the
  database **OID** and `%x` a random int — for publications, subscriptions, and
  slots alike (unless `--publication`/`--subscription`/`--replication-slot`
  override, in which case count and order must match the `-d` list exactly).
  `[verified-by-code source/src/bin/pg_basebackup/pg_createsubscriber.c:822]`
- **Post-promotion failure is fatal**: if the tool dies after the standby is
  promoted, the data directory is likely unrecoverable → build a fresh standby.
  Failures *before* promotion clean up the primary-side publications/slots
  (best-effort; a warning is logged if the target can't reach the primary to
  clean up). `[from-docs]`
- It runs `pg_resetwal` on the target at the end to **change the system
  identifier**, deliberately severing the target from the primary's WAL files so
  it can never accidentally consume them — which also means any *downstream*
  standbys of the target break and must be rebuilt.
  `[from-docs]`
- Primary-side prerequisites: `wal_level = logical`, enough `max_replication_slots`
  and `max_wal_senders` for (existing + one-per-database), and
  `max_slot_wal_keep_size = -1` recommended so the just-created slots' WAL can't be
  pruned mid-handoff. It also drops the standby's `primary_slot_name` on the
  primary afterward. `[from-docs][verified-by-code …:159,1210,2699]`
- `-a`/`--all` fans out over every non-template connectable database with
  auto-generated names, and is mutually exclusive with `-d`/`--publication`/
  `--subscription`/`--replication-slot`. `-n`/`--dry-run` runs every step except
  writing the target directory. `[from-docs]`
- Because logical replication does **not** replicate DDL, schema must stay frozen
  during conversion; two-phase commit is off unless `-T`/`--enable-two-phase`.
  `[from-docs]`

## Links into corpus

- Logical-replication apply / subscription / slot machinery this bootstraps:
  the `logical-replication` skill,
  `[[knowledge/docs-distilled/logical-replication-subscription.md]]`,
  `[[knowledge/docs-distilled/logical-replication-publication.md]]`.
- Replication origins advanced to the consistency LSN:
  `[[knowledge/docs-distilled/replication-origins.md]]`.
- Physical standby / promotion / `recovery_target_lsn` it drives:
  `[[knowledge/docs-distilled/hot-standby.md]]`,
  `[[knowledge/docs-distilled/warm-standby-failover.md]]`, the
  `physical-replication` skill.
- `pg_resetwal` system-identifier rewrite: `[[knowledge/docs-distilled/app-pgresetwal.md]]`.
