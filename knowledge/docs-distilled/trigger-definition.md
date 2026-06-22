---
source_url: https://www.postgresql.org/docs/current/trigger-definition.html
fetched_at: 2026-06-19T18:50:00Z
anchor_sha: bdae2c20e88d
distilled_by: pg-docs-miner (cloud routine)
docs_version: current (PG18)
primary: true
---

# Overview of Trigger Behavior (triggers ch. 39.1)

The firing-semantics overview of §39 — *which triggers fire, in what order,
what they see, and what their return value does.* The corpus had the C-ABI
leaf (`trigger-interface.md` §39.4) and the transition-table leaf
(`trigger-datachanges.md`) but **not** this behavioral matrix. Pairs with the
`trigger-*` idioms and the `executor-and-planner` skill.

## The event / timing / level matrix

- **Tables & foreign tables:** `BEFORE`/`AFTER` × `INSERT`/`UPDATE`/`DELETE`
  may be row-level **or** statement-level. `TRUNCATE` triggers are
  **statement-level only — never per-row.** [from-docs]
- **`UPDATE` triggers can be column-scoped:** set to fire only if certain
  columns are named in the `SET` clause. [from-docs]
- **Views:** `INSTEAD OF` × `INSERT`/`UPDATE`/`DELETE` is **row-level only**.
  `BEFORE`/`AFTER` on a view is **statement-level only, and only allowed if an
  `INSTEAD OF` trigger also exists** on that view. [from-docs]
- **Views without an `INSTEAD OF` trigger:** the statement is rewritten into one
  against the base table(s), and it is the *base-table* triggers that fire — not
  any view trigger. [from-docs]

## Return value (row-level BEFORE / INSTEAD OF only)

- **Return `NULL`** → skip the operation for *this row*; the executor performs no
  row-level operation, and **subsequent BEFORE/INSTEAD OF triggers for that row do
  not fire.** [from-docs]
- **Return a modified row** (INSERT/UPDATE) → that row becomes what is
  inserted / replaces the updated row. For an unchanged proceed, return `NEW`
  (INSERT/UPDATE) or `OLD` (DELETE) as-is. [from-docs]
- **Row-level AFTER and all statement-level triggers:** return value is
  **ignored**; per-statement trigger functions should always return `NULL`.
  [from-docs]
- The trigger function takes **no ordinary arguments** and returns type
  `trigger`; input arrives via a specially-passed `TriggerData` struct.
  [from-docs] → see `trigger-interface.md`.

## Ordering & chaining

- Multiple triggers on the same event fire **in alphabetical order by trigger
  name.** [from-docs]
- For `BEFORE`/`INSTEAD OF`, the possibly-modified row returned by each trigger
  is the **input to the next** trigger (a chain). [from-docs]
- Cascades: a trigger's SQL can fire more triggers; **no direct limit on cascade
  depth**, and recursive re-invocation of the same trigger is possible —
  avoiding infinite recursion is the programmer's responsibility. [from-docs]

## Visibility / snapshot semantics

- **Stored generated columns are computed *after* BEFORE triggers and *before*
  AFTER triggers.** So in a BEFORE row trigger `NEW`'s generated value is not yet
  set and must not be read; an AFTER trigger sees the final generated value.
  [from-docs]
- **AFTER row triggers fire at end of statement**, but *before* statement-level
  AFTER triggers. Statement-level AFTER triggers fire at the very end of the
  statement. [from-docs]
- A `WHEN` condition on an **AFTER** trigger is the queue gate: if it is not
  true, **no event is queued and the row need not be re-fetched at end of
  statement** — a significant speedup on many-row statements. A `WHEN` on a
  BEFORE trigger is just evaluated immediately before the function. **`WHEN` is
  not allowed on `INSTEAD OF` triggers.** [from-docs]

## Zero-row, ON CONFLICT, MERGE

- A statement affecting **zero rows still fires applicable per-statement
  triggers.** [from-docs]
- `INSERT ... ON CONFLICT DO UPDATE`: statement-level UPDATE triggers fire
  regardless of whether any row was updated; order is BEFORE INSERT → BEFORE
  UPDATE → AFTER UPDATE → AFTER INSERT (statement-level). [from-docs]
- `MERGE`: statement-level BEFORE/AFTER triggers fire for **every** action named
  in the command, whether or not that action ever runs; row-level triggers fire
  only when a row is actually inserted/updated/deleted. [from-docs]

## Partition row movement & inheritance

- An `UPDATE` that moves a row to another partition runs as DELETE-then-INSERT:
  row-level BEFORE UPDATE + BEFORE DELETE fire on the **origin** partition, then
  BEFORE INSERT on the **destination**. For **statement-level** triggers, only
  the target table's UPDATE triggers fire — no DELETE/INSERT statement triggers,
  even with row movement. [from-docs]
- A statement on a parent (inheritance/partition) table fires only the
  **parent's** statement-level triggers, but **row-level triggers of affected
  children do fire.** [from-docs]

## Other

- **Deferred (constraint) triggers:** an AFTER trigger defined as a *constraint
  trigger* can defer to end-of-transaction instead of end-of-statement; either
  way it runs in the **same transaction**, so an error rolls back both statement
  and trigger effects. [from-docs] → see `trigger-constraint-deferral.md`.
- **Transition tables** (`REFERENCING OLD/NEW TABLE`) give statement-level (and
  row-level) AFTER triggers access to the set of affected rows. [from-docs] →
  see `trigger-transition-tables.md`.
- **Security context:** a trigger runs as the role that queued the event, unless
  the function is `SECURITY DEFINER` (then as the function owner). [from-docs]

## Links into corpus

- [[knowledge/idioms/trigger-firing-order.md]] — the alphabetical-by-name +
  BEFORE→AFTER ordering, in executor-C terms.
- [[knowledge/idioms/trigger-constraint-deferral.md]] — the deferred
  constraint-trigger queue this §39.1 paragraph summarizes.
- [[knowledge/idioms/trigger-transition-tables.md]] — REFERENCING OLD/NEW TABLE
  machinery.
- [[knowledge/idioms/trigger-during-error.md]] — rollback-of-both semantics.
- [[knowledge/docs-distilled/trigger-interface.md]] — the `TriggerData` C-ABI
  the return-value rules above feed.
- [[knowledge/docs-distilled/trigger-datachanges.md]] — visibility of data
  changes (companion to the snapshot section here).
- [[knowledge/subsystems/executor.md]] — AfterTriggerBeginQuery / event-queue
  flush at end of statement.

## Open questions

- Map "alphabetical by trigger name" and the AFTER-event-queue gate to their
  `trigger.c` / `commands/trigger.c` sites at anchor `bdae2c20e88d` on a future
  trigger-subsystem deep read.
