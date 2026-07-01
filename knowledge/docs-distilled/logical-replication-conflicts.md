---
source_url: https://www.postgresql.org/docs/current/logical-replication-conflicts.html
fetched_at: 2026-06-30T19:58:00Z
anchor_sha: b7e4e3e7fa73
distilled_by: pg-docs-miner (cloud routine)
docs_version: current (PG18)
primary: true
---

# Logical Replication — Conflicts (§x.5)

What happens when an incoming change can't be applied cleanly. The key mental
model: **some conflicts ERROR and stop replication, others SILENTLY skip** —
which is which is not obvious.

## What causes a conflict

- **Constraint violations** (e.g. a unique/PK collision) stop replication.
  [from-docs]
- **Missing target tuple** on `UPDATE`/`DELETE` is *counted* as a conflict but
  does **NOT** error — the operation is **silently skipped**. [from-docs]
- **`NOT DEFERRABLE` unique-constraint** violations raise `insert_exists`,
  `update_exists`, or `multiple_unique_conflicts`. [from-docs]
- **RLS:** an enabled row-level-security policy on the target that rejects the
  operation (for the subscription owner) becomes a conflict. [from-docs]
- **Insufficient privileges** on the target table → conflict. [from-docs]

## The seven tracked conflict types

Recorded in **`pg_stat_subscription_stats`** [from-docs]:

| Type | Behaviour |
|---|---|
| `insert_exists` | ERROR — stops replication |
| `update_exists` | ERROR — stops replication |
| `multiple_unique_conflicts` | ERROR — stops replication |
| `update_missing` | silent skip |
| `delete_missing` | silent skip |
| `update_origin_differs` | applied anyway (no auto origin-resolution) |
| `delete_origin_differs` | applied anyway (no auto origin-resolution) |

- Other scenarios (e.g. **exclusion-constraint** violations) do **not** get
  detailed conflict logging. [from-docs]

## `track_commit_timestamp` — required for origin-differs detection

- **`update_origin_differs` / `delete_origin_differs` can ONLY be detected when
  `track_commit_timestamp` is enabled on the subscriber.** [from-docs] Without it,
  origin/xid/timestamp DETAIL is unavailable.
- When enabled, conflict logs include the **origin, transaction id, and commit
  timestamp** of the conflicting transaction. [from-docs]

## Logging detail

- **Large column values are truncated to 64 bytes** in conflict logs. [from-docs]
- **Column names appear in logs only if the user lacks privilege** to access all
  table columns (privilege-aware redaction inversion). [from-docs]

## Resolving a conflict

- **`ALTER SUBSCRIPTION ... SKIP (lsn = <finish_lsn>)`** — skip the whole
  conflicting transaction, using the *finish LSN* printed in the error log.
  [from-docs]
- **`pg_replication_origin_advance()`** — disable the subscription first
  (`... DISABLE`, or pre-arm with the `disable_on_error` option), then advance the
  origin past the bad LSN. [from-docs]
- **Fix the data / permissions** so the incoming change no longer conflicts.
  [from-docs]
- **Risk:** SKIP discards **all** changes in that transaction — can leave the
  subscriber inconsistent. [from-docs]

## Streaming-mode caveat

- With **`streaming = parallel`**, the **finish LSN of a failed transaction may
  not be logged** — switch to `streaming = on`/`off` and reproduce to obtain it
  before using SKIP. [from-docs]

## Links into corpus

- `knowledge/docs-distilled/logical-replication-subscription.md` —
  `disable_on_error`, slot, apply worker.
- `knowledge/docs-distilled/replication-origins.md` — the origin mechanism SKIP /
  `pg_replication_origin_advance()` manipulate.
- `knowledge/docs-distilled/monitoring-stats.md` —
  `pg_stat_subscription_stats` lives in the cumulative-stats system.
- `knowledge/subsystems/replication.md` — apply-side conflict handling in code.

## Citations

- All claims: source-URL anchor
  https://www.postgresql.org/docs/current/logical-replication-conflicts.html
  (PG18). The ERROR-vs-skip split per type and the `track_commit_timestamp`
  gate are the two most plan-relevant facts; verify apply-side behaviour against
  `source/src/backend/replication/logical/worker.c` at anchor `b7e4e3e7fa73`.
