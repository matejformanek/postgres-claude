---
source_url: https://www.postgresql.org/docs/current/xoper-optimization.html
fetched_at: 2026-06-11T00:00:00Z
anchor_sha: e18b0cb7344cb4bd28468f6c0aeeb9b9241d30aa
distilled_by: pg-docs-miner (cloud routine)
docs_version: current (PG18)
primary: true
---

# Docs distilled — §38.15: Operator Optimization Information

The `CREATE OPERATOR` clauses that feed the planner: `COMMUTATOR`, `NEGATOR`,
`RESTRICT`, `JOIN`, `HASHES`, `MERGES`. **These are correctness-critical, not
hints** — a wrong clause yields wrong results, not just slow plans. Pairs with the
`catalog-conventions` skill (pg_operator.dat) and `executor-and-planner`.

## COMMUTATOR [from-docs]

- A is the commutator of B iff `(x A y) == (y B x)` for all `x,y`; the relation is
  mutual (B is also A's commutator). `<`/`>` are mutual commutators; `=` and `+`
  are self-commutators. Operand types cross over: A's left type = B's right type.
- **Why it's critical**: the planner must "flip" `tab1.x = tab2.y` to
  `tab2.y = tab1.x` to put an indexed column on the left for index scans / join
  clauses. PG **will not assume** the flip is valid without an explicit
  `COMMUTATOR`. [from-docs]
  [verified-by-code, source/src/include/catalog/pg_operator.h — `oprcom`; via
  knowledge/idioms/catalog-conventions.md]

## NEGATOR [from-docs]

- A is the negator of B iff `(x A y) == NOT (x B y)` for all inputs; mutual.
  `<`/`>=` are a negator pair for most types. **An operator can never be its own
  negator.** Same operand types as the operator defined.
- **Payoff**: lets the planner simplify `NOT (x = y)` → `x <> y`, which surfaces
  more than expected because `NOT` gets injected by other rewrites. [from-docs]
  [verified-by-code, source/src/include/catalog/pg_operator.h — `oprnegate`]

## RESTRICT — restriction selectivity estimator [from-docs]

- Names a **function** (not an operator) estimating the row fraction satisfying
  `column OP constant`. Binary, boolean-returning operators only.
- Standard estimators: `=`→`eqsel`, `<>`→`neqsel`, `<`→`scalarltsel`,
  `<=`→`scalarlesel`, `>`→`scalargtsel`, `>=`→`scalargesel`.
- General-purpose: `matchingsel` (works for almost any binary op with standard
  MCV/histogram stats; default ≈ 2× `eqsel`), `generic_restriction_selectivity`
  (custom default). Geometric: `areasel`/`positionsel`/`contsel`
  (`src/backend/utils/adt/geo_selfuncs.c`). You may reuse `eqsel`/`neqsel` for
  very-high/low-selectivity non-equality ops (e.g. approximate-equality). [from-docs]
  [verified-by-code, source/src/backend/utils/adt/selfuncs.c — `eqsel` et al.;
  via knowledge/subsystems/optimizer.md]

## JOIN — join selectivity estimator [from-docs]

- Names a function estimating the fraction satisfying `t1.c1 OP t2.c2`; drives
  join-order choice. Binary boolean ops only.
- Standard: `=`→`eqjoinsel`, `<>`→`neqjoinsel`, `<`→`scalarltjoinsel`,
  `<=`→`scalarlejoinsel`, `>`→`scalargtjoinsel`, `>=`→`scalargejoinsel`, generic
  `matchingjoinsel`; geometric `areajoinsel`/`positionjoinsel`/`contjoinsel`.
  [from-docs]

## HASHES — hash-join eligibility [from-docs]

- Declares the operator may drive a **hash join**. The underlying assumption: the
  operator can return true **only** for pairs that hash to the same code — values
  in different buckets are never compared, implicitly treated as non-matching.
- Consistency rules (enforced at *use*, not creation):
  1. Must represent **equality** for a type or type-pair.
  2. Must appear in a **hash index operator family** (so a per-type hash function
     is reachable).
  3. Must have a **commutator in the same family** (itself if operand types match,
     else a related equality operator).
  4. Underlying function must be **immutable or stable** — volatile → never
     hash-joined.
  5. If the function is **strict** it must also be **complete**: return true/false,
     never null, for any two non-null inputs — else hash-optimized `IN` can return
     false where the standard says null, or error. [from-docs]
- Gotchas: structs with pad bits can't just `hash_any` the whole struct; IEEE
  ±0.0 compare equal but differ in bits, so the hash function must map both to the
  same code. [from-docs]
  [verified-by-code, source/src/include/catalog/pg_operator.h — `oprcanhash`]

## MERGES — merge-join eligibility [from-docs]

- Declares the operator may drive a **merge join** (sort both sides, scan in
  parallel). Both types must be **totally orderable**, and the operator must
  succeed only for values at the "same place" in sort order.
- Consistency rules (enforced at use):
  1. Must behave like **equality** (may cross compatible types, e.g.
     `smallint = integer`).
  2. Needs sorting operators bringing both types into a compatible sequence.
  3. Must be the **equality member of a `btree` operator family** (acts as a
     planner hint).
  4. Must have a **commutator in the same family**, else planner errors.
  5. Underlying function **immutable or stable** — volatile → never merge-joined.
  [from-docs]
  [verified-by-code, source/src/include/catalog/pg_operator.h — `oprcanmerge`]

## Links into corpus

- [[knowledge/idioms/catalog-conventions.md]] — the `pg_operator.dat` columns
  (`oprcom`/`oprnegate`/`oprrest`/`oprjoin`/`oprcanhash`/`oprcanmerge`) these
  clauses populate.
- [[knowledge/docs-distilled/xindex.md]] — operator families/classes the HASHES/
  MERGES rules reference.
- [[knowledge/subsystems/optimizer.md]] — where the selectivity estimators and
  hash/merge-join paths consume this metadata.
- [[knowledge/docs-distilled/planner-stats.md]] — how the RESTRICT/JOIN estimators
  use statistics.

## Gaps / follow-ups

- The basic `CREATE OPERATOR` mechanics (function-first, leftarg/rightarg,
  overloading) are on the sibling `xoper.html` page (not separately distilled —
  thin, and fully subsumed here). The estimator internals live in
  `selfuncs.c`; `knowledge/subsystems/optimizer.md` is the deeper reference.
