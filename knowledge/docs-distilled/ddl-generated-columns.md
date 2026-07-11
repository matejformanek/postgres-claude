---
source_url: https://www.postgresql.org/docs/current/ddl-generated-columns.html
fetched_at: 2026-07-11T19:54:35Z
anchor_sha: 54cd6fc83176d7c03abf95554aef26b0b24acc7d
distilled_by: pg-docs-miner (cloud routine)
docs_version: current (PG18)
section: "5.4 Generated Columns"
---

# Docs distilled — Generated Columns (ddl-generated-columns)

A column whose value is computed from other columns rather than written
directly. As of **PG18 there are two kinds — `VIRTUAL` (the new default) and
`STORED`** — and the split is a real catalog value on `pg_attribute`.

## Non-obvious claims

- **`attgenerated` is a single `char` on `pg_attribute`** with three states:
  `'\0'` = not generated, `'s'` = STORED, `'v'` = VIRTUAL. That one column is
  the whole storage cost of the feature at the catalog level. [verified-by-code]
  `src/include/catalog/pg_attribute.h:137` (`attgenerated`), `:233`
  (`ATTRIBUTE_GENERATED_STORED 's'`), `:234` (`ATTRIBUTE_GENERATED_VIRTUAL 'v'`).
- **VIRTUAL is now the default** (PG18): "a virtual generated column occupies no
  storage and is computed when it is read"; STORED "is computed when it is
  written (inserted or updated) and occupies storage as if it were a normal
  column." The doc's analogy: virtual ≈ a view, stored ≈ an always-fresh
  materialized view. [from-docs]
- **STORED values are literally in the heap tuple** — a stored generated column
  costs the same row space as an ordinary column and is written at
  INSERT/UPDATE time. VIRTUAL columns cost zero heap bytes and are re-evaluated
  every read. [from-docs]
- **Generation happens *after* BEFORE triggers, and BEFORE triggers may not
  read generated columns.** "changes made to base columns in a `BEFORE` trigger
  will be reflected in generated columns", but "it is not allowed to access
  generated columns in `BEFORE` triggers." The value simply doesn't exist yet
  at BEFORE-trigger time. [from-docs]
- **You cannot write a generated column directly.** INSERT/UPDATE may not supply
  a value; the only accepted token is the keyword `DEFAULT`. [from-docs]
- **The generation expression is heavily restricted**: immutable functions
  only, no subqueries, no reference to anything but the current row, may not
  reference *another* generated column, and may not reference a system column
  except `tableoid`. [from-docs]
- **VIRTUAL columns carry extra restrictions STORED does not**: a virtual
  generated column "cannot have a user-defined type, and the generation
  expression … must not reference user-defined functions or types … it can only
  use built-in functions or types." [from-docs]
- **Access privileges are tracked separately** from the base columns, so a role
  can be granted read on the generated column while being denied the underlying
  base columns — but for VIRTUAL columns this only holds if the expression uses
  leakproof functions, "and this is not enforced by the system." [from-docs]
- **Logical replication of generated columns is opt-in and STORED-only**:
  governed by the `CREATE PUBLICATION` parameter `publish_generated_columns`,
  and "currently only supported for stored generated columns." [from-docs]

## Links into corpus

- [[knowledge/files/src/include/access/htup_details.h.md]] — where a STORED
  generated value physically lands (the heap tuple).
- [[knowledge/subsystems/access-heap.md]] — heap write path that materializes
  STORED values at INSERT/UPDATE.
- [[knowledge/subsystems/executor.md]] — expression evaluation that computes the
  generation expression (VIRTUAL = at read/scan time, STORED = at ModifyTable).
- [[knowledge/docs-distilled/trigger-definition.md]] — BEFORE-trigger ordering
  vs. generated-column computation.
- [[knowledge/idioms/catalog-conventions.md]] — `pg_attribute.attgenerated` as a
  catalog char-enum discriminator.
- [[knowledge/docs-distilled/logical-replication-publication.md]] —
  `publish_generated_columns` on `CREATE PUBLICATION`.
