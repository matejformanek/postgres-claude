---
source_url: https://www.postgresql.org/docs/current/logical-replication-col-lists.html
fetched_at: 2026-06-30T20:00:00Z
anchor_sha: b7e4e3e7fa73
distilled_by: pg-docs-miner (cloud routine)
docs_version: current (PG18)
primary: true
---

# Logical Replication — Column Lists (§x.4)

Per-table list restricting *which columns* replicate. The column-level analogue of
row filters; the sharp edges are the **replica-identity mandate**, the
**no-different-lists-per-table** rule, and **future-column** behaviour.

## Specification + defaults

- Specified per table inside `CREATE PUBLICATION ... FOR TABLE t1 (id, b, a, d)`.
  Only the **named columns replicate**; unlisted columns are not synchronized.
  [from-docs]
- **No column list ⇒ all publisher columns replicate** (the default). [from-docs]
- **Column order in the list does not matter and is not preserved.** [from-docs]
- A column list may contain **only simple column references** — no expressions.
  [from-docs]

## Replica-identity mandate

- A column list on a publication that publishes **`UPDATE`/`DELETE`** **must
  include the table's replica-identity columns**. For **`INSERT`-only**
  publications the list **may omit** them. [from-docs] (PK columns per se are not
  separately mandated — only replica-identity columns are.) [from-docs]
- The subscriber table must have **at least all the published columns**.
  [from-docs]

## Future columns (a real surprise)

- **If a column list is specified — even one naming every current column — newly
  added columns are NOT auto-replicated.** Only **having no column list at all**
  replicates future columns automatically. [from-docs]

## Combining across publications (stricter than row filters)

- Unlike row filters (which OR), **a table published with *different* column lists
  across multiple publications is unsupported**: `CREATE SUBSCRIPTION` **disallows**
  it. [from-docs]
- Changing a publication's column list **after** a subscription exists can produce
  **errors on the subscriber** if different lists then exist for the same table.
  [from-docs]
- A column list **cannot** be combined with `FOR TABLES IN SCHEMA` publishing the
  same table. [from-docs]

## Partitions, TRUNCATE, generated columns

- **Partitioned tables:** `publish_via_partition_root` picks the **root** list if
  `true`, else (`false`, the default) **each partition's** own list. [from-docs]
- **Column lists have no effect on `TRUNCATE`.** [from-docs]
- **Generated columns** *can* be named in a column list to publish them,
  **regardless of `publish_generated_columns`**. [from-docs]

## Version-skew in initial sync (back-compat traps)

- Subscribers **older than v15** ignore column lists and copy **all** columns at
  initial sync. [from-docs]
- Subscribers **older than v18** do **not** copy generated columns at initial sync
  even when the publisher defines them. [from-docs]

## Links into corpus

- `knowledge/docs-distilled/logical-replication-row-filter.md` — the row-level twin
  (note: row filters OR; column lists must match — opposite combining rules).
- `knowledge/docs-distilled/logical-replication-publication.md`,
  `logical-replication-subscription.md` — the objects this constrains.
- `knowledge/subsystems/replication.md` — column projection in `pgoutput`.

## Citations

- All claims: source-URL anchor
  https://www.postgresql.org/docs/current/logical-replication-col-lists.html
  (PG18). The future-column-not-replicated rule and the no-different-lists
  constraint are the two most plan-relevant; verify against
  `source/src/backend/replication/pgoutput/pgoutput.c` + `subscriptioncmds.c`
  at anchor `b7e4e3e7fa73`.
