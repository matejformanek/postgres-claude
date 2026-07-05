---
source_url: https://www.postgresql.org/docs/current/monitoring-locks.html
fetched_at: 2026-07-04
anchor_sha: a5422fe3bd7e
chapter: "§28.3 Viewing Locks (pg_locks)"
maps_to_skills: [locking, debugging]
maps_to_corpus: [knowledge/subsystems/storage-lmgr.md, knowledge/docs-distilled/monitoring-stats.md, knowledge/docs-distilled/pgrowlocks.md]
---

# Viewing locks — the pg_locks view (§28.3)

The runtime window into the lock manager: one row per held-or-awaited lock
object across every backend. The definitional reference for the `locking` skill's
diagnosis loop.

## Non-obvious claims

- **`granted` splits held from waited.** `granted=true` → the lock is currently
  held; `granted=false` → the backend is *blocked* waiting for it. A blocked
  query is therefore visible as `NOT granted` rows joined to its pid.
  `[from-docs]`
- **pg_locks shows two different lock worlds.** Both **regular (heavyweight)**
  lock-manager entries *and* **predicate `SIReadLock`** rows from Serializable
  Snapshot Isolation (SSI) appear in the same view — so an SSI investigation and
  a heavyweight-deadlock investigation both start here. `[from-docs]`
- **Every transaction takes two identity locks.** A `virtualxid` lock row always
  exists for an active transaction, and a second `transactionid` row appears
  *once a real XID is assigned* (i.e. after the first write). Waiters on a
  row-lock block on the holder's `transactionid` — the classic
  "waiting on transactionid" pattern. `[from-docs]`
- **`fastpath=true` marks fast-path weak locks.** Weak relation locks
  (AccessShare/RowShare/RowExclusive) are taken through the per-backend fast-path
  array, bypassing the shared lock-manager partitions; they still surface in
  pg_locks with `fastpath` set. `[from-docs]`
- **`waitstart`** is the timestamp the wait began — lets you rank waiters by age
  without polling deltas. `[from-docs]`
- **`locktype` is the discriminator** for which of `relation/page/tuple/
  virtualxid/transactionid/advisory/…` columns are meaningful; advisory locks
  show `locktype=advisory`. `[from-docs]`
- **Blocker discovery two ways:** join `pg_locks` to `pg_stat_activity` on `pid`
  filtering `NOT granted`, or call `pg_blocking_pids(pid)` for the direct blocker
  set. `[from-docs]`

## Links into corpus

- [[knowledge/subsystems/storage-lmgr.md]] — the heavyweight lock manager +
  fast-path array this view reflects (`pg_lock_status()` in lock.c is the SRF
  backing pg_locks).
- [[knowledge/docs-distilled/pgrowlocks.md]] — row-level lock decode that
  complements the transactionid rows here.
- [[knowledge/docs-distilled/monitoring-stats.md]] — the sibling
  cumulative-stats view surface.
</content>
