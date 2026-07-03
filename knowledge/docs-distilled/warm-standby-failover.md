---
source_url: https://www.postgresql.org/docs/current/warm-standby-failover.html
fetched_at: 2026-07-03T20:47:00Z
anchor_sha: a5422fe3bd7e
distilled_by: pg-docs-miner (cloud routine)
docs_version: current (PG18)
primary: true
---

# Failover (§26.3)

Promoting a standby to primary. Short chapter, but it pins down the two things
that bite people: **PG does not detect failure or fence the old primary for you**,
and **the old primary can't casually rejoin** after a promotion.

## Triggering promotion

- Current mechanisms: **`pg_ctl promote`** and the SQL **`pg_promote()`**
  function. (The old `promote_trigger_file` GUC is **no longer** the documented
  path — removed in current versions.) [from-docs]
- Promotion makes the standby **finish replaying all available WAL**, then **fork
  a new timeline** and open for writes. The new timeline (and its `.history` file)
  is why downstream nodes must be told which timeline to follow. [from-docs] — see
  `knowledge/docs-distilled/continuous-archiving.md` §Timelines.

## PG does NOT provide the HA glue

- **PostgreSQL ships no failure detector and no notifier** — "PostgreSQL does not
  provide the system software required to identify a failure on the primary and
  notify the standby." That's the job of external tooling (Patroni,
  repmgr, pacemaker, …). [from-docs]
- **STONITH / split-brain:** you **must** have a mechanism to tell the old primary
  it is no longer primary ("Shoot The Other Node In The Head"). Without fencing,
  two nodes both believing they're primary ⇒ divergence ⇒ data loss. [from-docs]
- An optional **witness server** can suppress some inappropriate failovers, but
  the docs caution the added complexity is only worth it with careful setup and
  rigorous testing. [from-docs]

## After failover — the old primary problem

- Post-failover you're running on a **single node** (former standby); the former
  primary is down — a degraded, un-redundant state until you rebuild a standby.
  [from-docs]
- The old primary **cannot simply restart and rejoin as a standby**: while it was
  (briefly) still accepting writes / diverging, it and the new primary are on
  **different timelines**. Reconcile with **`pg_rewind`** (rewinds the old primary
  to the divergence point by replaying the new primary's WAL over the changed
  blocks) or take a **fresh base backup**. `pg_rewind` is the fast path on large
  clusters. [from-docs / inferred] — see
  `knowledge/docs-distilled/app-pgrewind.md`.
- With logical-slot sync in play, **verify synced slots are failover-ready on the
  standby before promoting** (§29.3 / §47.2.3). [from-docs] — see
  `knowledge/docs-distilled/logical-replication-failover.md`.
- **Regular planned switchovers** are recommended: they enable rolling
  maintenance and double as a live test of the failover path. [from-docs]

## Links into corpus

- `knowledge/docs-distilled/warm-standby.md` — the standby being promoted.
- `knowledge/docs-distilled/app-pgrewind.md` — rejoining the old primary across a
  timeline fork.
- `knowledge/docs-distilled/continuous-archiving.md` — timelines + `.history`
  files that a promotion creates.
- `knowledge/docs-distilled/logical-replication-failover.md` — the logical-slot
  pre-promotion check.
- `knowledge/subsystems/replication.md`.

## Citations

- All claims: source-URL anchor
  https://www.postgresql.org/docs/current/warm-standby-failover.html (PG18).
- The timeline-divergence rationale for needing `pg_rewind` is `[inferred]` from
  the promotion→new-timeline semantics; the page recommends `pg_rewind` without
  spelling out the timeline mechanics (those are in `app-pgrewind.md`).
