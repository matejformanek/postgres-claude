---
source_url: https://www.postgresql.org/docs/current/plpgsql-declarations.html
chapter: "43.3 PL/pgSQL Declarations (plpgsql-declarations)"
fetched_at: 2026-07-22
anchor_sha: d774576f6f0
---

# PL/pgSQL declarations — plpgsql-declarations

The §43.3 variable-declaration chapter, read for the *timing* and *resolution*
semantics that bite: when `DEFAULT`/`:=` initializers run, what `%TYPE` copies
(and drops), how parameter aliases scope, how collation is chosen per call, and
the `RECORD`-vs-row-type substructure distinction. Compiler is `pl_comp.c`.

## Non-obvious claims

- **DEFAULT / `:=` initializers run on EACH block entry, not once per function
  call.** "A variable's default value is evaluated and assigned to the variable
  each time the block is entered (not just once per function call). So, for
  example, assigning `now()` to a variable of type `timestamp` causes the
  variable to have the time of the current function call, not the time when the
  function was precompiled." [from-docs] Consequence: a `DECLARE` inside a loop
  body's inner `BEGIN` re-evaluates its default every iteration.
- **`%TYPE` / `%ROWTYPE` copy only the base type — NOT `NOT NULL` or the
  column's `DEFAULT`.** Declaring `v users.user_id%TYPE` gives you the type of
  `users.user_id` and nothing else; source-column constraints/defaults do not
  ride along. [from-docs, implicit from examples] The payoff is decoupling: "if
  the data type of the referenced item changes in the future … you might not
  need to change your function definition." [from-docs]
- **Named parameters and `ALIAS FOR $n` are *not* perfectly equivalent** — the
  difference is qualified-name scope. A parameter named in `CREATE FUNCTION`
  (e.g. `subtotal`) can be referenced qualified as `sales_tax.subtotal`; the
  same name introduced via `subtotal ALIAS FOR $1` **cannot** be qualified that
  way. [from-docs] Both ultimately bind to the positional `$1`, `$2`, … slots.
- **`NOT NULL` is enforced at RUN TIME, and forces a non-null default.** "If
  `NOT NULL` is specified, an assignment of a null value results in a run-time
  error. All variables declared as `NOT NULL` must have a nonnull default value
  specified." [from-docs] So `NOT NULL` without a default is a definition error;
  the null-assignment check itself is a runtime trap, not compile-time.
- **`CONSTANT` is a per-block write-lock after initialization.** "prevents the
  variable from being assigned to after initialization, so that its value will
  remain constant for the duration of the block." [from-docs]
- **Variable collation is resolved per call from the arguments, overridable by
  `COLLATE`.** When a function has collatable-type parameters, "a collation is
  identified for each function call depending on the collations assigned to the
  actual arguments … If a collation is successfully identified (i.e., there are
  no conflicts of implicit collations among the arguments) then all the
  collatable parameters are treated as having that collation implicitly." A
  `local_a text COLLATE "en_US"` declaration "overrides the collation that would
  otherwise be given." [from-docs] This is why the *same* PL/pgSQL body can sort
  differently depending on the caller's argument collations.
- **`RECORD` is a placeholder, not a type; a row variable has fixed structure.**
  "Record variables are similar to row-type variables, but they have no
  predefined structure. They take on the actual row structure of the row they
  are assigned … until a record variable is first assigned to, it has no
  substructure, and any attempt to access a field in it will draw a run-time
  error." "Note that `RECORD` is not a true data type, only a placeholder."
  [from-docs] So `tablename%ROWTYPE` is safe to field-access immediately;
  `arow RECORD` is a runtime error until its first `SELECT INTO`/`FOR` assignment.

## Links into corpus

- `[[knowledge/docs-distilled/plpgsql-structure.md]]` — §43.2, the block
  structure whose "each time the block is entered" the DEFAULT timing hangs off.
- `[[knowledge/docs-distilled/plpgsql-expressions.md]]` — §43.4, how the `:=`
  initializer expression is planned/evaluated.
- `[[knowledge/docs-distilled/plpgsql-implementation.md]]` — §43.11, variable
  representation + plan caching in `pl_comp.c`/`pl_exec.c`.
- `[[knowledge/docs-distilled/collation.md]]` — the collation-identification
  rules these per-call bindings follow.
- Skill `plpgsql-internals` (pl_comp.c declaration compilation); `type-cache`
  for how `%TYPE`/`%ROWTYPE` and `RECORD` substructures are resolved.

## Verification note

This chapter is behavioral-contract prose; the load-bearing timing/resolution
claims (DEFAULT per-entry, `%TYPE` strips constraints, runtime `NOT NULL`,
per-call collation, `RECORD` no-substructure) are quoted [from-docs] @ current.
Compiler entry points live in `src/pl/plpgsql/src/pl_comp.c` @ `d774576f6f0`
(not line-cited here — no single load-bearing line, unlike §43.6's subtransaction).
