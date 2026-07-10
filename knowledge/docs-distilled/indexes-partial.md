---
source_url: https://www.postgresql.org/docs/current/indexes-partial.html
fetched_at: 2026-07-10
anchor_sha: c1702cb51363
chapter: "11.8 Partial Indexes"
maps_to_skills: [executor-and-planner, planner-cost-model]
---

# 11.8 Partial Indexes

Distilled from §11.8. The internals hook is **predicate implication**: a
partial index is only usable when the planner can *prove* the query's `WHERE`
mathematically implies the index predicate — the theorem prover in
`predtest.c`, invoked from `indxpath.c`.

## Non-obvious claims

- **A partial index indexes only rows satisfying its predicate.** Entries
  exist "only for those table rows that satisfy the predicate." [from-docs §11.8]
- **Three use cases:** (1) exclude common values so the index stays small
  (a query for a value that is >few-% of the table won't use an index
  anyway); (2) enforce a **partial unique** constraint on a subset
  (`CREATE UNIQUE INDEX … WHERE success`) without constraining the rest;
  (3) steer planner choices. [from-docs §11.8]
- **Usability = provable implication, at plan time.** "A partial index can be
  used in a query only if the system can recognize that the `WHERE` condition
  of the query mathematically implies the predicate of the index." Matching
  happens at *planning* time, not run time. [from-docs §11.8]
  — code path: `predicate_implied_by(index->indpred, all_clauses, false)`
  called from the index-path builder.
  [verified-by-code `source/src/backend/optimizer/path/indxpath.c:1134` @c1702cb51363;
  prover entry `source/src/backend/optimizer/util/predtest.c:154`]
- **The prover is deliberately weak.** No general theorem prover: it handles
  simple inequality implication (`x < 1` implies `x < 2`); otherwise the
  predicate must *exactly match part of* the query's `WHERE`. Equivalent
  expressions written differently are NOT recognized. [from-docs §11.8]
- **Parameterized clauses never match a partial index.** A prepared query
  `x < ?` can't imply `x < 2` for all parameter values, so partial indexes
  are unusable for it — a real gotcha with prepared statements. [from-docs §11.8]
- **Predicate columns need not be indexed columns**, and arbitrary predicates
  are allowed "so long as only columns of the table being indexed are
  involved." [from-docs §11.8]
- **Anti-pattern: partial indexes as poor-man's partitioning.** Many
  non-overlapping partial indexes force the planner to "laboriously test each
  one" (it doesn't understand their relationship). Use real partitioning
  (§5.12) instead. [from-docs §11.8]
- **Partial predicate need not be rechecked at runtime** when it's guaranteed
  by the index — this is what lets a partial index feed an index-only scan on
  a column that only appears in the predicate (see §11.9). [from-docs §11.8]
  [[knowledge/docs-distilled/indexes-index-only-scans.md]]

## Links into corpus

- The predicate-implication theorem prover:
  [[knowledge/files/src/backend/optimizer/util/predtest.c.md]].
- Where index paths test the predicate:
  [[knowledge/subsystems/optimizer.md]],
  [[knowledge/files/src/backend/optimizer/util/clauses.c.md]].
- Partial *unique* index enforcement ↔ nbtree uniqueness:
  [[knowledge/docs-distilled/index-unique-checks.md]],
  [[knowledge/subsystems/access-nbtree.md]].
- Real partitioning as the scale answer:
  [[knowledge/subsystems/partitioning.md]].
- Interaction with index-only scans:
  [[knowledge/docs-distilled/indexes-index-only-scans.md]].

## Citations

- Behavioral claims: source-URL §11.8.
- Prover invocation: `source/src/backend/optimizer/path/indxpath.c:1134`
  (`predicate_implied_by(index->indpred, all_clauses, false)`); prover entry
  `source/src/backend/optimizer/util/predtest.c:154`
  (`predicate_implied_by(List *predicate_list, List *clause_list, …)`).
  [verified-by-code @c1702cb51363]
