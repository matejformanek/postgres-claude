---
source_url: https://www.postgresql.org/docs/current/logical-replication-subscription.html
fetched_at: 2026-06-30T19:57:00Z
anchor_sha: b7e4e3e7fa73
distilled_by: pg-docs-miner (cloud routine)
docs_version: current (PG18)
primary: true
---

# Logical Replication — Subscription (§x.2)

The downstream side. A **subscription** is the node-local object that names a
publisher connection + a list of publications and drives the apply worker.

## What a subscription is

- A subscription defines a **connection to another database** and names **one or
  more publications** to subscribe to; the node holding it is the **subscriber**.
  [from-docs]
- Created with `CREATE SUBSCRIPTION ... CONNECTION '<conninfo>'`; paused/resumed
  with `ALTER SUBSCRIPTION ... DISABLE/ENABLE`; removed with `DROP SUBSCRIPTION`.
  [from-docs]

## Subscription ↔ replication slot (the load-bearing relationship)

- **Each subscription receives changes via exactly one replication slot** on the
  publisher. [from-docs]
- That remote slot is **created automatically when the subscription is created and
  dropped automatically when the subscription is dropped** — the normal path. The
  apply worker holds it open. [from-docs]
- **Tablesync slots are separate and internal**: extra slots are created for
  initial sync and dropped automatically when done. Their generated name pattern
  is **`pg_%u_sync_%u_%llu`** (subscription OID, table relid, system identifier).
  [from-docs]
- **`create_slot = false`** → bind to an already-existing slot instead of creating
  one. **`connect = false`** → define the subscription without contacting the
  publisher at all; you must then create the slot manually and activate via
  `ALTER SUBSCRIPTION ... ENABLE` + `... REFRESH PUBLICATION`. [from-docs]
- **Slot cleanup footgun:** if the publisher is **unreachable at `DROP
  SUBSCRIPTION` time**, the auto-drop can't run — disassociate the slot first
  (`ALTER SUBSCRIPTION ... SET (slot_name = NONE)` then drop the subscription) and
  drop the slot manually, **or the orphaned slot pins WAL and can fill the
  publisher's disk**. [from-docs]

## Schema / data matching rules (subscriber must be pre-built)

- **Schema is NOT replicated** — published tables must **already exist** on the
  subscriber. Only **regular tables** are valid targets (no views). [from-docs]
- Tables match by **fully-qualified name** (no rename mapping). **Columns match by
  name; column order need not match.** [from-docs]
- **Data types need not match exactly** — replication works as long as the **text
  representation converts** to the target type (e.g. `integer` → `bigint`). The
  **binary** format is stricter about type matching. [from-docs]
- The subscriber table may carry **extra columns** absent on the publisher; those
  get **default values**. [from-docs]

## Initial sync vs steady state (mirrors the publication leaf)

- **Initial COPY ignores** the publication's `publish` restrictions **and** row
  filters — all rows copy. **Steady-state apply enforces** `publish` ops and
  respects row filters. [from-docs]

## pg_dump behaviour (a real gotcha)

- **`pg_dump` dumps subscriptions only if the running user is a superuser.**
  Non-superusers can't read all of `pg_subscription`, so subscriptions are
  **skipped with a warning**. [from-docs] (Backup/restore of a subscriber can
  silently lose subscriptions if dumped as a non-superuser.)

## Links into corpus

- `knowledge/docs-distilled/logical-replication-publication.md` — the upstream
  object this attaches to.
- `knowledge/docs-distilled/logical-replication-conflicts.md` — what happens when
  apply hits a constraint/missing-tuple.
- `knowledge/docs-distilled/logical-replication-architecture.md` — apply +
  tablesync worker model.
- `knowledge/docs-distilled/replication-origins.md` — crash-safe apply progress.
- `knowledge/subsystems/replication.md`,
  `knowledge/idioms/apply-worker-loop-and-dispatch.md` — code-level.

## Citations

- All claims: source-URL anchor
  https://www.postgresql.org/docs/current/logical-replication-subscription.html
  (PG18). The two_phase / streaming / disable_on_error option *semantics* are on
  the `CREATE SUBSCRIPTION` reference page + the `-conflicts` leaf; verify against
  `source/src/backend/commands/subscriptioncmds.c` at anchor `b7e4e3e7fa73`.
