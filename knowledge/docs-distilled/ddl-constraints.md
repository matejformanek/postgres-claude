---
source_url: https://www.postgresql.org/docs/current/ddl-constraints.html
fetched_at: 2026-07-11T19:54:35Z
anchor_sha: 54cd6fc83176d7c03abf95554aef26b0b24acc7d
distilled_by: pg-docs-miner (cloud routine)
docs_version: current (PG18)
section: "5.5 Constraints"
---

# Docs distilled — Constraints (ddl-constraints)

CHECK / NOT NULL / UNIQUE / PRIMARY KEY / FOREIGN KEY / EXCLUSION. Every type is
a `pg_constraint` row discriminated by a one-char `contype`, and several are
*implemented* by other subsystems — unique via a B-tree index, exclusion via a
GiST index, FK via system RI triggers.

## Non-obvious claims

- **`contype` is a single-char discriminator on `pg_constraint`.** `'c'` CHECK,
  `'f'` FOREIGN KEY, `'n'` NOT NULL, `'p'` PRIMARY KEY, `'u'` UNIQUE, `'t'`
  constraint TRIGGER, `'x'` EXCLUSION. [verified-by-code]
  `src/include/catalog/pg_constraint.h:198-204`.
- **NOT NULL is now a real catalogued constraint (`contype 'n'`), not just an
  `attnotnull` flag.** The docs frame it as "functionally equivalent to …
  `CHECK (column IS NOT NULL)`, but … an explicit not-null constraint is more
  efficient", and a column may have at most one explicit NOT NULL constraint.
  [from-docs] + [verified-by-code] `pg_constraint.h:200` (`CONSTRAINT_NOTNULL`).
- **CHECK treats NULL as *satisfied*.** "A check constraint is satisfied if the
  check expression evaluates to true or the null value." So `CHECK (col > 0)`
  does not reject a NULL `col`. CHECK conditions are *assumed immutable*; a
  user-defined function that changes behavior can leave rows silently violating
  the constraint (dump/restore won't re-detect). CHECK may not reference other
  rows. [from-docs]
- **UNIQUE is backed by an automatically-created unique B-tree index**, and
  **NULLs are distinct by default** — a unique constraint permits multiple rows
  with NULL in a constrained column. `NULLS NOT DISTINCT` flips that; partial
  unique indexes scope uniqueness to a subset of rows. [from-docs]
- **PRIMARY KEY = UNIQUE B-tree index + forced NOT NULL, one per table.** It
  also defines the default target columns for foreign keys that omit a column
  list. [from-docs]
- **FOREIGN KEY is enforced by *system RI triggers*, not inline checks.** The
  referential actions dispatch to functions in `ri_triggers.c`: insert/update
  checks (`RI_FKey_check_ins`), and per-action delete/update handlers
  (`RI_FKey_cascade_del`, `RI_FKey_noaction_del`, `RI_FKey_restrict_del`, …).
  [from-docs] + [verified-by-code] `src/backend/utils/adt/ri_triggers.c:628`
  (`RI_FKey_check_ins`), `:1064` (`RI_FKey_cascade_del`), `:793`
  (`RI_FKey_noaction_del`), `:813` (`RI_FKey_restrict_del`). These are wired as
  constraint triggers (`contype 't'` companions).
- **`NO ACTION` vs `RESTRICT` differ only in deferral timing.** Both forbid
  leaving a dangling reference, but "`RESTRICT` does not allow the check to be
  deferred until later in the transaction", whereas `NO ACTION` (the default)
  can be deferred — so a CASCADE-then-check sequence within a statement can
  succeed under NO ACTION but fail under RESTRICT. [from-docs]
- **FK NULL semantics: MATCH SIMPLE (default) vs MATCH FULL.** By default a
  referencing row is exempt if *any* referencing column is NULL; under
  `MATCH FULL` it is exempt only if *all* are NULL. [from-docs]
- **The referenced side must be a PK / unique constraint / non-partial unique
  index**; the referencing side gets no automatic index, but one is recommended
  because RI delete/update of a referenced row scans referencing rows.
  [from-docs]
- **EXCLUSION generalizes UNIQUE to arbitrary operators and is index-backed.**
  "if any two rows are compared on the specified columns … using the specified
  operators, at least one of these operator comparisons will return false or
  null", and it "will automatically create an index of the type specified" —
  typically GiST (e.g. `&&` for non-overlapping ranges). [from-docs] +
  [verified-by-code] `pg_constraint.h:204` (`CONSTRAINT_EXCLUSION 'x'`).
- **DEFERRABLE / INITIALLY DEFERRED detail lives elsewhere.** This page names
  deferral only in passing (RESTRICT vs NO ACTION); the full deferrable-trigger
  semantics are in the Data Manipulation / trigger docs. [from-docs]

## Links into corpus

- [[knowledge/files/src/include/catalog/pg_constraint.h.md]] — the `contype`
  char-enum + constraint catalog columns.
- [[knowledge/files/src/backend/utils/adt/ri_triggers.c.md]] — the RI
  (referential-integrity) trigger functions behind every FOREIGN KEY.
- [[knowledge/idioms/catalog-conventions.md]] — `pg_constraint` as a
  char-discriminated catalog.
- [[knowledge/docs-distilled/trigger-definition.md]] — constraint triggers are
  system triggers; deferral is trigger-timing.
- [[knowledge/docs-distilled/gist.md]] — the index type behind EXCLUSION
  constraints (non-overlap via `&&`).
- [[knowledge/docs-distilled/index-unique-checks.md]] — how the B-tree enforces
  UNIQUE / PRIMARY KEY uniqueness.
