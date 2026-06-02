---
source_url: https://wiki.postgresql.org/wiki/Hot_Standby
fetched_at: 2026-06-02T20:47:00Z
wiki_last_edited: 2016-06-30
anchor_sha: 4b0bf0788b066a4ca1d4f959566678e44ec93422
distilled_by: pg-docs-miner (cloud routine)
primary: false
staleness: wiki page is a PG 9.0/9.1-era quick-start (last edited 2016). It uses
  the retired `recovery.conf` + `standby_mode` + `wal_level=hot_standby`
  spellings, omits the modern `standby.signal` file, and barely covers the
  replay-vs-query conflict knobs. Supplemented below with [verified-by-code]
  facts from the corpus and the current parameter names.
---

# Wiki distilled — Hot Standby

What Hot Standby is, the central tension between WAL replay and read-only
queries on the standby, and how that conflict is resolved. The wiki page is a
dated quick-start; the load-bearing mechanics come from the corpus supplement.

## What the wiki page says

- **Hot Standby = running read-only queries on a standby while it is performing
  archive/streaming recovery.** Authored by Simon Riggs (2ndQuadrant); committed
  for **PostgreSQL 9.0**, the first release where a standby was queryable rather
  than purely passive ("warm standby"). [from-wiki]
- **Minimum config (9.0/9.1 spellings, now dated):** on the primary
  `wal_level = hot_standby`, `archive_mode = on` + `archive_command`,
  `max_wal_senders ≥ 3`; on the standby `hot_standby = on`,
  `standby_mode = 'on'` and a `restore_command` in `recovery.conf`. [from-wiki]
  **(Modern equivalent: `wal_level = replica`, a `standby.signal` marker file,
  and `primary_conninfo`/`restore_command` in `postgresql.conf`. — corpus note,
  see staleness header.)**
- **Diagnostics it recommends:** look for the "startup process" (the recovery
  process), `SELECT pg_is_in_recovery()`, `txid_current_snapshot()`, and
  inspect `pg_locks` / `pg_stat_activity`. [from-wiki]
- **Backup method note:** prefer `pg_basebackup` (9.1+) over hand-rolled
  `pg_start_backup`/`rsync`/`pg_stop_backup`. [from-wiki]

## What the wiki page omits — corpus supplement

The page does **not** explain the replay-vs-query conflict machinery, the
modern delay/feedback knobs, or the on-standby restrictions. These are the
load-bearing details:

- **The central conflict:** the standby's startup process replays WAL that can
  invalidate data a read-only query still needs — chiefly **snapshot/cleanup
  conflicts** (replay of a VACUUM/HOT-prune record that removes tuples a standby
  snapshot can still see), plus **AccessExclusiveLock conflicts** (replay of a
  DDL lock the primary took), **buffer-pin conflicts**, **dropped
  database/tablespace**, and **dropped relation** records. [from-comment]
- **The resolution is a tunable race** between two bad options — *delay replay*
  vs *cancel the conflicting query*:
  - `max_standby_archive_delay` / `max_standby_streaming_delay` — how long
    replay will wait for queries before it cancels them. `-1` = wait forever
    (replay can fall arbitrarily behind); `0` = cancel immediately. The
    canceled backend gets *"canceling statement due to conflict with
    recovery"* (SQLSTATE 40001). [from-docs]
  - `hot_standby_feedback = on` — the standby reports its oldest snapshot xmin
    back to the primary, so the primary's VACUUM won't remove tuples the standby
    still needs. **Eliminates cleanup conflicts at the cost of bloat / delayed
    cleanup on the primary** (and is defeated if there's a cascading standby
    without feedback). [from-docs]
- **AccessExclusiveLock replay is special-cased in the lock manager.** During
  recovery the standby refuses to grant any lock stronger than `RowExclusiveLock`
  on a relation/object to normal backends, reserving the strong modes for replay
  of the primary's locks. [verified-by-code,
  source/src/backend/storage/lmgr/lock.c:861-869, via
  knowledge/files/src/backend/storage/lmgr/lock.c.md] The primary, conversely,
  WAL-logs AccessExclusiveLock acquisition on a relation so the standby can
  reproduce it. [verified-by-code, lock.c:965-972; `StandbyAcquireAccessExclusiveLock`
  / `LogAccessExclusiveLock` in
  knowledge/files/src/include/storage/standby.h.md:49,80]
- **What is forbidden on a standby:** any write (INSERT/UPDATE/DELETE/DDL),
  sequence advancement (`nextval`), `SELECT … FOR UPDATE/SHARE` row locks,
  two-phase commit, LISTEN/NOTIFY, and writing advisory locks — all rejected
  because they would emit WAL the standby cannot generate. Read-only `SELECT`
  and read-only function calls are allowed. [from-docs]

## Why it matters operationally

- **The fundamental Hot Standby trade-off is lag vs cancellation.** A reporting
  replica wants long `max_standby_*_delay` (tolerate replay lag to let big
  queries finish); a near-real-time HA replica wants short delays (keep replay
  current, accept query cancellations). `hot_standby_feedback` shifts the cost
  onto the primary's bloat instead of either. [inferred, from-docs]
- The "canceling statement due to conflict with recovery" error on a replica is
  almost always a snapshot/cleanup conflict — the fix is feedback or a larger
  streaming-delay, not a query rewrite. [inferred]

## Links into corpus

- [[knowledge/subsystems/replication.md]] — walsender/walreceiver/startup-process
  recovery machinery behind streaming to the standby.
- [[knowledge/architecture/replication.md]] — PG-wide replication overview
  (physical vs logical, the recovery/replay path).
- [[knowledge/files/src/backend/storage/lmgr/lock.c.md]] — the recovery-mode
  lock-strength clamp (lines 861-869) and standby AccessExclusiveLock WAL prep
  (965-972) that resolve DDL-lock conflicts.
- [[knowledge/files/src/include/storage/standby.h.md]] — `StandbyAcquireAccessExclusiveLock`,
  `LogAccessExclusiveLock`, the standby-side replay of primary locks.
- [[knowledge/data-structures/snapshot-lifecycle.md]] — the standby snapshot
  xmin that `hot_standby_feedback` ships back to the primary to prevent cleanup
  conflicts.
- [[knowledge/architecture/wal.md]] — the WAL records (VACUUM/prune/lock) whose
  replay is what conflicts with standby queries.

## Confidence note

The wiki content is `[from-wiki]` and is accurate for its era (PG 9.0/9.1,
2016) but dated: it predates `standby.signal` (PG 12 retired `recovery.conf`)
and `wal_level` was renamed (`hot_standby` → `replica`, PG 9.6). The conflict
machinery, delay/feedback knobs, and on-standby restrictions are `[from-docs]`
from the current Hot Standby docs chapter; the lock-manager recovery clamp is
`[verified-by-code]` against the per-file corpus. The lag-vs-cancel framing is
`[inferred]`. A future run should distill the official
`hot-standby.html` docs chapter to replace this dated wiki page as the primary
source.
