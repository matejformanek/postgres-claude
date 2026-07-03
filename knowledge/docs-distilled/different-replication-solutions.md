---
source_url: https://www.postgresql.org/docs/current/different-replication-solutions.html
fetched_at: 2026-07-03T20:47:00Z
anchor_sha: a5422fe3bd7e
distilled_by: pg-docs-miner (cloud routine)
docs_version: current (PG18)
primary: true
---

# Comparison of Different Solutions (§26.1)

The taxonomy chapter that frames the whole §26 High-Availability part: the menu
of replication/HA approaches and the axes that separate them (data-loss window,
whether replicas serve reads, per-table vs whole-cluster granularity, conflict
handling, version coupling, write overhead). Useful as the orienting map over the
already-distilled logical (§29) and physical (warm/hot-standby) chapters.

## The approaches

- **Shared-disk failover** — one physical copy on a shared array; **no
  synchronization overhead**, but the array is a **single point of failure** (its
  corruption takes primary *and* standby down at once). [from-docs]
- **File-system / block-device replication (e.g. DRBD)** — mirrors every fs write
  to the standby; correctness demands writes land in the **same order** as the
  primary. No PG-level logic; whole-device granularity. [from-docs]
- **Write-Ahead-Log shipping (warm/hot standby)** — ships WAL; **whole-cluster**
  granularity (not per-table); async (data-loss window) or sync (no loss). The
  built-in single-primary path. [from-docs]
- **Logical replication** — reconstructs **per-table** logical changes from WAL;
  supports **bidirectional** flows; replicas are fully writable. Built-in, per-
  table filtering + column lists. [from-docs] — see
  `knowledge/docs-distilled/logical-replication.md`.
- **Trigger-based primary-standby (e.g. Slony-I)** — per-table, replicas accept
  reads; **asynchronous batch** propagation ⇒ possible loss on failover. External.
  [from-docs]
- **SQL-based replication middleware (pgpool-II, Tungsten)** — intercepts SQL and
  broadcasts to all servers; read queries load-balance across replicas. The
  footgun: **non-deterministic functions** (`random()`, `CURRENT_TIMESTAMP`,
  sequence draws) **diverge** across servers unless routed from one source.
  [from-docs]
- **Asynchronous multimaster (e.g. Bucardo)** — every server writes independently,
  then periodically reconciles and **detects conflicting transactions**; needs
  conflict-resolution rules; tolerates slow/intermittent links. [from-docs]
- **Synchronous multimaster** — any server accepts writes, data goes to **all**
  before commit; **no non-deterministic divergence**, but heavy writes cause
  **excessive locking + commit latency**. **Not built into PostgreSQL** (needs
  application-level 2PC). [from-docs]

## The discriminating axes

- **Standby serves reads?** — only logical, trigger-based, SQL-middleware, and
  multimaster variants let replicas answer read queries; **shared-disk and
  block-device replication do not** (the standby's PG isn't running against the
  mirrored volume). Note: WAL **hot** standby *does* serve reads — that's the
  hot-standby chapter's whole point. [from-docs]
- **Conflict resolution needed?** — only the **multimaster** approaches;
  single-primary designs (shared-disk, WAL shipping, trigger-based) never conflict.
  [from-docs]
- **Granularity** — WAL shipping / block-device / shared-disk are **whole-cluster**;
  logical / trigger-based are **per-table**. [from-docs]
- **Data partitioning** is listed as an **orthogonal** option (split tables across
  servers by ownership, e.g. by region) that needs application logic — not
  replication per se. [from-docs]

## Links into corpus

- `knowledge/docs-distilled/warm-standby.md`,
  `.../hot-standby.md`, `.../warm-standby-failover.md` — the built-in physical
  path this chapter compares.
- `knowledge/docs-distilled/logical-replication.md`,
  `.../logical-replication-architecture.md` — the built-in logical path.
- `knowledge/docs-distilled/logicaldecoding-explanation.md` — the decoding layer
  logical replication is built on.
- `knowledge/subsystems/replication.md`.

## Citations

- All claims: source-URL anchor
  https://www.postgresql.org/docs/current/different-replication-solutions.html
  (PG18). Third-party tool names (DRBD, Slony-I, pgpool-II, Tungsten, Bucardo)
  are the docs' own examples, not endorsements.
