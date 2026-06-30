---
source_url: https://www.postgresql.org/docs/current/logical-replication-failover.html
fetched_at: 2026-06-30T20:02:00Z
anchor_sha: b7e4e3e7fa73
distilled_by: pg-docs-miner (cloud routine)
docs_version: current (PG18)
primary: true
---

# Logical Replication — Failover (§x.7)

The newest leaf of the chapter (slot-sync to a physical standby, PG17+). Solves
the long-standing problem: if the **publisher** fails over to its physical standby,
a logical subscriber's slot lived only on the old primary and is lost. Slot
synchronization copies the logical slot to the standby so the subscriber can
continue against the **promoted** primary.

## The mechanism

- A logical slot can be **synchronized to the publisher's physical standby** so the
  subscriber keeps working after the standby is promoted. [from-docs]
- **Slot sync is asynchronous** — slots are copied to the standby in the
  background, so you must **explicitly verify** the standby's slots are ready
  **before** promoting. [from-docs]
- **The standby must be ahead of the subscriber** for a clean failover; enforce
  this via **`synchronized_standby_slots`** (the publisher waits for the standby
  before acknowledging the subscriber). [from-docs]

## What you must set

- **`failover = true`** on the **subscription** (or the slot) — required for the
  logical slot to be eligible for synchronization to the standby. With it,
  subscriptions can continue against the new primary after promotion. [from-docs]
- (Cross-ref, not on this page) the standby runs a **slot-sync worker**
  (`sync_replication_slots = on`) or you call **`pg_sync_replication_slots()`**
  manually; the standby needs `hot_standby_feedback` + `primary_slot_name`.
  [unverified — named on the config/function pages, flagged here so a plan cites
  the right source.]

## Pre-promotion verification (the three-step check)

1. Identify the **subscription's main slots** on each subscriber via
   `pg_subscription`. [from-docs]
2. Identify **tablesync slots** — but **only those whose table copy is finished**
   (`srsubstate = 'f'`); unfinished ones will be **dropped/re-created on the new
   primary** anyway. [from-docs]
3. On the standby, confirm each slot is present and ready:
   **`synced AND NOT temporary AND invalidation_reason IS NULL`**. [from-docs]
- Run the check on **every** subscriber node to get the complete slot list.
  [from-docs]
- For **planned** failover with mixed PG / non-PG subscribers, query the
  **primary's** `pg_replication_slots WHERE failover = true AND NOT temporary` to
  enumerate what must be synced. [from-docs]

## Version note

- Page targets **PG18**, referencing v17/v19/devel. Slot-sync + `failover`
  subscription parameter were introduced in **PG17**; treat as **not available
  pre-17**. [from-docs / inferred]

## Links into corpus

- `knowledge/docs-distilled/logical-replication-subscription.md` — the subscription
  + its slot that this synchronizes.
- `knowledge/docs-distilled/logical-replication-restrictions.md` — sequences are
  NOT advanced on a promoted subscriber (the companion failover gotcha).
- `knowledge/docs-distilled/runtime-config-replication.md` —
  `synchronized_standby_slots` / `sync_replication_slots` GUC surface.
- `knowledge/docs-distilled/replication-origins.md` — apply progress that survives
  the failover.
- `knowledge/subsystems/replication.md` — slot-sync worker in code.

## Citations

- All claims: source-URL anchor
  https://www.postgresql.org/docs/current/logical-replication-failover.html
  (PG18). GUC/function names for the standby side (`sync_replication_slots`,
  `pg_sync_replication_slots()`, `hot_standby_feedback`, `primary_slot_name`) are
  flagged as NOT fully specified on this page — verify against
  runtime-config-replication + `source/src/backend/replication/logical/slotsync.c`
  at anchor `b7e4e3e7fa73`.
