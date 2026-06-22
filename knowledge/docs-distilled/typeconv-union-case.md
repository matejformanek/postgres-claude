---
source_url: https://www.postgresql.org/docs/current/typeconv-union-case.html
fetched_at: 2026-06-22T00:00:00Z
anchor_sha: 031904048aa2
distilled_by: pg-docs-miner (cloud routine)
docs_version: current (PG18)
primary: false
---

# Docs distilled — §10.5: UNION, CASE, and Related Constructs

The "select a common type across N branches" algorithm
(`select_common_type` in `parse_coerce.c`). Applies wherever several
expressions must collapse to one output type.

## Where it applies

`UNION` / `INTERSECT` / `EXCEPT`, `CASE`, `ARRAY`, `VALUES`, `GREATEST`,
`LEAST`. Note: `INTERSECT`/`EXCEPT` resolve **pairwise**; the others
consider **all inputs at once**. `[from-docs]`

## The numbered algorithm

1. **All inputs same non-`unknown` type** → resolve as that type. `[from-docs]`
2. **Domain input** → treat as its **base type** for all later steps.
   `[from-docs]`
3. **All inputs `unknown`** → resolve as **`text`** (preferred type of the
   string category). Otherwise `unknown` inputs are **ignored** for the
   remaining rules. `[from-docs]`
4. **Non-unknown inputs not all in the same type category** → **fail**.
   `[from-docs]`
5. **Left-to-right candidate walk:** start with the first non-unknown type as
   candidate; for each subsequent type, if the candidate can be **implicitly
   converted to it but not vice-versa**, the other type becomes the new
   candidate. **If a preferred type is ever selected, stop early.** `[from-docs]`
6. **Convert all inputs to the final candidate**; **fail** if any input has
   no implicit conversion to it. `[from-docs]`

## Non-obvious consequences

- The **left-to-right asymmetry** in step 5 means branch *order* can matter
  when neither direction is clearly more general — but the "stop on a
  preferred type" rule usually settles it deterministically. `[inferred]`
- `unknown` literals never *drive* the choice (step 3 sidelines them); they
  ride along and get coerced in step 6. A `CASE` with all-NULL/all-literal
  branches lands on `text`. `[inferred from steps 3+6]`
- Category mismatch (step 4) is a **hard fail** with no implicit-cast
  rescue — e.g. `UNION` of a `numeric` and a `boolean` branch errors rather
  than coercing. `[from-docs]`

## Links into corpus

- The category/preferred-type concepts these steps lean on:
  [docs-distilled/typeconv-overview.md](./typeconv-overview.md)
- Sibling resolution algorithms:
  [docs-distilled/typeconv-func.md](./typeconv-func.md),
  [docs-distilled/typeconv-oper.md](./typeconv-oper.md)
- Relevant skills: `parser-and-nodes` (this runs in parse-analysis,
  producing `CoerceViaIO`/`RelabelType`/`FuncExpr` coercion nodes),
  `executor-and-planner`.
