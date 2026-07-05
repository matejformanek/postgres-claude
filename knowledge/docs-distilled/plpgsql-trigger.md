---
source_url: https://www.postgresql.org/docs/current/plpgsql-trigger.html
fetched_at: 2026-07-05T20:47:00Z
anchor_sha: e0ff7fd9aa2e
distilled_by: pg-docs-miner (cloud routine)
docs_version: current (PG18)
primary: true
---

# PL/pgSQL trigger functions (internals §43.10 — page body says §41.10)

How a PL/pgSQL trigger function talks to the executor: the auto-injected `NEW` /
`OLD` / `TG_*` variables, and — the load-bearing part — **what the return value
does when it flows back into the trigger manager** (a BEFORE row trigger
returning NULL *suppresses* the operation; returning a modified `NEW` *rewrites*
the row). Pairs with `trigger-interface.md` (the C `TriggerData` ABI) and
`trigger-datachanges.md`. Subsections: §43.10.1 Triggers on Data Changes,
§43.10.2 Triggers on Events.

## Non-obvious claims

- **`NEW` / `OLD` are `record` variables, null in the cases where they don't
  apply.** `NEW` = new row for INSERT/UPDATE row-level triggers, **null** for
  DELETE and for all statement-level triggers; `OLD` = old row for UPDATE/DELETE
  row-level triggers, **null** for INSERT and statement-level. [from-docs]
- **The `TG_*` context variables** are auto-created: `TG_NAME` (name), `TG_WHEN`
  (`BEFORE`/`AFTER`/`INSTEAD OF`), `TG_LEVEL` (`ROW`/`STATEMENT`), `TG_OP`
  (`INSERT`/`UPDATE`/`DELETE`/`TRUNCATE`), `TG_RELID` (oid of the table),
  `TG_TABLE_NAME`, `TG_TABLE_SCHEMA`, `TG_NARGS` (int), `TG_ARGV` (text[],
  **0-indexed**, out-of-range index → null). These are the PL/pgSQL surface over
  the C `TriggerData` struct. [from-docs]
- **BEFORE row trigger return value is control flow, not just data.** *"Row-level
  triggers fired `BEFORE` can return null to signal the trigger manager to skip
  the rest of the operation for this row (i.e., subsequent triggers are not
  fired, and the `INSERT`/`UPDATE`/`DELETE` does not occur for this row). If a
  nonnull value is returned then the operation proceeds with that row value.
  Returning a row value different from the original value of `NEW` alters the row
  that will be inserted or updated."* So NULL = veto, modified `NEW` = rewrite,
  `NEW` unchanged = proceed. [from-docs]
- **BEFORE DELETE must return nonnull (idiom: `OLD`).** *"the returned value has
  no direct effect, but it has to be nonnull to allow the trigger action to
  proceed."* `NEW` is null in DELETE, so the idiom is `RETURN OLD`. [from-docs]
- **INSTEAD OF triggers: return `NEW` for INSERT/UPDATE (drives `RETURNING` +
  `EXCLUDED`), `OLD` for DELETE.** A modified `NEW` from an INSTEAD OF trigger
  even feeds the `EXCLUDED` alias in `INSERT ... ON CONFLICT DO UPDATE`.
  [from-docs]
- **AFTER and statement-level trigger return values are ignored entirely.** *"The
  return value of a row-level trigger fired `AFTER` or a statement-level trigger
  fired `BEFORE` or `AFTER` is always ignored; it might as well be null."*
  [from-docs]
- **Transition tables are read-only ephemeral relations, AFTER-only.** *"`AFTER`
  triggers can also make use of transition tables ... the function can refer to
  those names as though they were read-only temporary tables."* Named via
  `CREATE TRIGGER ... REFERENCING OLD TABLE AS ... NEW TABLE AS ...` — the
  set-oriented alternative to per-row `NEW`/`OLD`, typically on
  `FOR EACH STATEMENT`. [from-docs]
- **Event triggers get `TG_EVENT` + `TG_TAG`** instead of `NEW`/`OLD` (§43.10.2),
  for DDL-level triggering. [from-docs]

## Why this matters for a hacker

The BEFORE-return-value semantics are the exact seam where PL data meets executor
control flow: `ExecBRInsertTriggers` / `ExecBRUpdateTriggers` in the C trigger
manager interpret a NULL return as "skip this tuple" and a non-NULL return as
"use this (possibly rewritten) tuple." A PL/pgSQL trigger is just the SQL-visible
way to produce that return tuple; the transition-table mechanism is the same
ephemeral-named-relation (Tuplestore) plumbing statement-level AFTER triggers use
at the C level. [inferred, cross-ref trigger-interface.md]

## Links into corpus

- [[knowledge/docs-distilled/trigger-interface.md]] — §39.4: the C `TriggerData`
  / `HeapTuple` return ABI these variables + return values map onto.
- [[knowledge/docs-distilled/trigger-datachanges.md]] — §39.x: transition-table
  behavior at the SQL level.
- [[knowledge/docs-distilled/trigger-definition.md]] — §39.1: trigger firing
  semantics (BEFORE/AFTER/INSTEAD OF, ROW/STATEMENT).
- [[knowledge/docs-distilled/event-trigger-definition.md]] /
  [[knowledge/docs-distilled/event-trigger-interface.md]] — the event-trigger
  side (`TG_EVENT`/`TG_TAG`).

## Open questions

- The `pl_exec.c` `plpgsql_exec_trigger` return-tuple handling and where a NULL
  return becomes the executor's "skip tuple" signal — pin at anchor
  `e0ff7fd9aa2e`.
