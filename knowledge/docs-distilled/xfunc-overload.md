---
source_url: https://www.postgresql.org/docs/current/xfunc-overload.html
chapter: "38.6 Function Overloading (xfunc-overload)"
fetched_at: 2026-06-17
anchor_sha: e5f94c4808fe88c170840ac3a24cdfa423b404fc
---

# Function overloading — xfunc-overload

Functions are keyed by name **plus input-argument types**; the corner cases are
where overload resolution becomes ambiguous, plus the C-linker constraint that
trips up overloaded `LANGUAGE C` functions.

## Non-obvious claims

- **Same name, different input types = legal overload.** A function's identity
  is its name + input-argument type list (the *calling signature*); output
  params don't count. [from-docs xfunc-overload]
- **Near-numeric overloads are an ambiguity trap.** With `test(int, real)` and
  `test(smallint, double precision)`, a call like `test(1, 1.5)` has no
  obviously-correct match — resolution follows the Chapter 10 rules, but
  leaning on subtle implicit-cast precedence is fragile. [from-docs]
- **Don't name a single-composite-arg function the same as a field of that
  composite.** `attribute(table)` is treated as equivalent to `table.attribute`;
  on ambiguity the **attribute always wins**. Schema-qualifying
  (`schema.func(table)`) overrides, but avoiding the collision is better.
  [from-docs]
- **Variadic vs non-variadic can both exist but conflict on single-arg
  calls.** With `foo(numeric)` and `foo(VARIADIC numeric[])`, a call `foo(10.1)`
  is resolved by: the function earlier in the `search_path` wins; if both are in
  the same schema, the **non-variadic one is preferred**. [from-docs]
- **C-language overloads need distinct C symbol names.** Every function in an
  overloaded family must have a C link name different from every other (internal
  or dynamically-loaded) function — violating this is non-portable. Use the `AS`
  clause to decouple the SQL name from the C symbol (`test_1arg`, `test_2arg`).
  This is the overloading-specific corollary of the
  [[knowledge/docs-distilled/xfunc-c.md]] symbol rules. [from-docs]

## Links into corpus

- The full overload-resolution algorithm (the "Chapter 10 rules" this page
  defers to): [[knowledge/docs-distilled/extend-type-system.md]] covers the
  polymorphic-type half; the precedence/best-match logic lives in
  `source/src/backend/parser/parse_func.c` (`func_select_candidate`).
- The C-symbol-name constraint in context:
  [[knowledge/docs-distilled/xfunc-c.md]].
- SQL-function overloading specifics:
  [[knowledge/docs-distilled/xfunc-sql.md]] (OUT params excluded from the
  signature).

## Caveats / verification

- All claims `[from-docs xfunc-overload]`. Candidate selection /
  ambiguous-call resolution is in
  `source/src/backend/parser/parse_func.c` at anchor
  `e5f94c4808fe88c170840ac3a24cdfa423b404fc`.
