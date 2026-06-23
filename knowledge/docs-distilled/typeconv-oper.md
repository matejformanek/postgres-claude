---
source_url: https://www.postgresql.org/docs/current/typeconv-oper.html
fetched_at: 2026-06-22T00:00:00Z
anchor_sha: 031904048aa2
distilled_by: pg-docs-miner (cloud routine)
docs_version: current (PG18)
primary: false
---

# Docs distilled — §10.2: Operator Type Resolution

The operator overload-resolution algorithm (parser, against `pg_operator`;
`parse_oper.c oper_select_candidate`). Structurally the same as function
resolution (§10.3) but with extra `unknown`-handling at the exact-match
step, because operators frequently have one untyped literal operand.

## Step 1 — gather candidates from `pg_operator`

- Unqualified → operators with matching name + arg count in the search
  path; qualified → only that schema. `[from-docs]`
- **1.1:** identical-arg-type duplicates collapse to the **earliest in
  path**; different-arg-type operators compete equally. `[from-docs]`

## Step 2 — exact match (with unknown special-cases)

- An operator accepting **exactly** the input types wins (at most one).
  `[from-docs]`
- **2.1:** for a binary operator with **one** `unknown` operand, assume it
  equals the other operand's type for this check. **Two** `unknown` inputs,
  or a prefix operator with an `unknown` input, **never** match here.
  `[from-docs]`
- **2.2:** one `unknown` + one **domain** operand → check for an operator
  taking the domain's **base type** on both sides; if so, use it. `[from-docs]`

## Step 3 — best match (the tie-break ladder)

Same ladder as functions §10.3 step 4, applied in order; stop when one
remains:

- **3.1:** discard candidates unreachable by **implicit conversion**
  (`unknown` literals assumed convertible to anything). `[from-docs]`
- **3.2:** **domain** inputs treated as their **base type** henceforth.
  `[from-docs]`
- **3.3:** keep the **most exact-type matches**. `[from-docs]`
- **3.4:** keep candidates accepting **preferred types** at the most
  to-be-converted positions. `[from-docs]`
- **3.5:** for `unknown` positions, prefer the **`string`** category if any
  candidate accepts it; else require **all** remaining candidates to share a
  category (or **fail**); then drop non-matching-category and non-preferred
  candidates. `[from-docs]`
- **3.6:** mixed `unknown`/known with all known args one type → assume the
  `unknown`s are that type; **exactly one** surviving candidate wins, else
  **fail**. `[from-docs]`

## Ambiguity failures

- Triggered when 3.5 can't pick a category, or 3.6 leaves ≠1 candidate, or
  multiple candidates survive the whole ladder. Canonical error:

  ```
  ERROR:  operator is not unique: ~ "unknown"
  HINT:  Could not choose a best candidate operator. You might need to add
  explicit type casts.
  ```
  `[from-docs]`

## Links into corpus

- Function analogue (the parallel ladder, with worked examples):
  [docs-distilled/typeconv-func.md](./typeconv-func.md)
- Categories / preferred types: [docs-distilled/typeconv-overview.md](./typeconv-overview.md)
- Relevant skills: `catalog-conventions` (the `pg_operator.dat` +
  `pg_amop`/commutator rows), `parser-and-nodes`.
