---
source_url: https://www.postgresql.org/docs/current/logical-replication.html
fetched_at: 2026-06-30T19:55:00Z
anchor_sha: b7e4e3e7fa73
distilled_by: pg-docs-miner (cloud routine)
docs_version: current (PG18)
primary: true
---

# Logical Replication — chapter intro (§29 / §31 parent)

The top of the built-in pub/sub chapter. Frames *what* logical replication is and
*how it differs from physical/streaming replication*; the operating mechanics live
in the child leaves (`logical-replication-publication`,
`-subscription`, `-conflicts`, `-row-filter`, `-col-lists`, `-restrictions`,
`-failover`, `-architecture`). **Note:** current docs render this as Chapter 29;
the 06-20 architecture leaf was distilled when it was Chapter 31 — same chapter,
renumbered. Cite by slug, not by number.

## Logical vs physical replication (the core distinction)

- Logical replication is based on a **replication identity** (usually a primary
  key) and replicates **data objects and their changes** — NOT exact block
  addresses + byte-by-byte copy the way physical/streaming replication does.
  [from-docs] This is the line that separates it from the WAL-shipping physical
  path (see `runtime-config-replication.md`).
- Because it is change-based (logical-decoding driven, not block-image driven),
  it can replicate **across major versions** and **across platforms** (e.g. Linux
  → Windows) — impossible for physical replication, which requires identical
  binary page layout. [from-docs]

## The pub/sub model

- **Publish/subscribe:** one or more **subscribers** subscribe to one or more
  **publications** on a **publisher** node. [from-docs]
- **Pull model:** subscribers *pull* data from the publications they subscribe to.
  [from-docs] (Contrast with physical streaming where the standby connects but the
  framing is WAL-record shipping, not per-publication logical change pulls.)
- **Cascading:** a subscriber may itself **re-publish** the data it received, to
  build cascading or more complex topologies. [from-docs]

## Initial sync + steady state

- On a new subscription PG **takes a snapshot of the publisher table's data and
  copies it to the subscriber**, then continually sends subsequent changes. The
  per-table COPY-then-catch-up handshake is the `-architecture` leaf's subject.
  [from-docs]
- The subscriber **applies changes in the same order as the publisher**, so
  **transactional consistency is guaranteed for publications within a single
  subscription**. [from-docs] (The "within a single subscription" scope is
  load-bearing — ordering guarantees do not span subscriptions.)

## Conflicts (only when the subscriber is written to)

- If the subscriber is **read-only** to applications, a single subscription
  produces **no conflicts**. [from-docs]
- Conflicts arise only when **other writes** hit the same tables — local
  application writes, or writes from other subscribers. Conflict semantics are the
  `-conflicts` leaf. [from-docs]

## Typical use cases (as the intro lists them)

- Sending incremental changes to subscribers as they happen; firing **subscriber
  triggers** on individual changes; consolidating many databases into one;
  replicating between **different PG major versions / platforms**; giving access
  to a **subset** of data per user group; sharing a database subset across many
  databases. [from-docs]

## What the intro does NOT settle (read the leaves)

- DDL is **not** replicated, sequence-value handling, TRUNCATE behaviour, and the
  full restriction list are in `logical-replication-restrictions.md`, not here.
  [inferred — not asserted on this page]
- The walsender + apply-worker + tablesync-worker process model is the
  `-architecture` leaf. [from-docs cross-ref]

## Links into corpus

- `knowledge/docs-distilled/logical-replication-architecture.md` — the §x.10
  process model (walsender / apply / tablesync).
- `knowledge/docs-distilled/logicaldecoding-explanation.md`,
  `logicaldecoding-output-plugin.md` — the §49 decoding layer `pgoutput` sits on.
- `knowledge/docs-distilled/protocol-logical-replication.md` — the wire format.
- `knowledge/docs-distilled/runtime-config-replication.md` — the GUC surface.
- `knowledge/subsystems/replication.md`,
  `knowledge/idioms/apply-worker-loop-and-dispatch.md` — code-level.

## Citations

- All claims carry the source-URL anchor
  https://www.postgresql.org/docs/current/logical-replication.html (PG18).
  DDL/sequence/TRUNCATE claims are explicitly deferred to the restrictions leaf
  rather than asserted here.
