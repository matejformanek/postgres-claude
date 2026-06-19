---
source_url: https://www.postgresql.org/docs/current/xoper.html
fetched_at: 2026-06-18T20:47:00Z
anchor_sha: ab3023ad1e68
distilled_by: pg-docs-miner (cloud routine)
docs_version: current (PG18)
primary: true
---

# User-Defined Operators (extending-SQL ch. 38.14)

The Extending-SQL leaf on `CREATE OPERATOR`. Complements
`xoper-optimization.md` (§38.15, the planner-hint clauses) — this page is the
base mechanism: an operator is a thin catalog wrapper over a function. Pairs
with the `catalog-conventions` and `fmgr-and-spi` skills.

## Non-obvious claims

- **An operator is syntactic sugar over a function — but not *merely* sugar.**
  `a + b` is a call to an underlying function, so **the function must exist
  before** you `CREATE OPERATOR`. The operator additionally carries planner
  metadata (commutator, selectivity, index-support hints) that a bare function
  call cannot. [from-docs]
- **Two shapes only: prefix (unary) and infix (binary).** Provide `rightarg`
  for a prefix operator; provide both `leftarg` and `rightarg` for an infix
  one. (Postfix operators were removed in PG14 and are not offered here.)
  [from-docs]
- **Required clauses are minimal:** `function` plus the argument clause(s).
  Everything else (`commutator`, `negator`, `restrict`, `join`, `hashes`,
  `merges`) is an optional optimizer hint covered in the next section. [from-docs]
- **Operators overload by operand count and types.** The same operator name can
  name different operators with different operand signatures; the system resolves
  which to call from the number and types of the actual operands at parse time.
  [from-docs]
- **Operators are schema-qualified catalog objects** (live in `pg_operator`),
  so they obey `search_path`; you can write `OPERATOR(schema.+)` to disambiguate.
  [from-docs/inferred]
- **Canonical example** (complex-number addition): declare
  `complex_add(complex, complex) RETURNS complex` in C, then
  `CREATE OPERATOR + (leftarg = complex, rightarg = complex, function =
  complex_add, commutator = +)`. Note the operator is its own commutator here
  (`+` commutes with `+`). After that, `SELECT (a + b) FROM test_complex;`
  dispatches through `complex_add`. [from-docs]

## Links into corpus

- [[knowledge/docs-distilled/xoper-optimization.md]] — §38.15 commutator /
  negator / restrict / join / hashes / merges hints (why an operator beats a
  bare function for the planner).
- [[knowledge/files/src/backend/commands/operatorcmds.c.md]] —
  `DefineOperator()`, the executor of `CREATE OPERATOR`.
- [[knowledge/files/src/backend/catalog/pg_operator.c.md]] —
  `OperatorCreate()` / `pg_operator` row construction and the
  commutator/negator self-reference shell-operator trick.
- [[knowledge/idioms/catalog-conventions.md]] — how a new operator's
  `pg_operator.dat` / OID entry is declared for built-ins.
- [[knowledge/idioms/fmgr.md]] — the underlying-function call machinery.

## Open questions

- `pg_operator.c` line for the two-pass "create shell operator for the
  commutator, then back-patch" handling of self/mutual commutators — verify on a
  future deep read at anchor `ab3023ad1e68`.
