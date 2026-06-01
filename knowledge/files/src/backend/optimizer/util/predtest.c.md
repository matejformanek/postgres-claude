# predtest.c — predicate-implication prover

- **Source:** 2364 lines · **Last verified commit:** `ef6a95c7c64`
- **Depth:** read

## Purpose

Decide whether one expression implies (or refutes) another. Used by:
partial-index matching, constraint exclusion, partition pruning at
plan-time, OR-clause simplification. False negatives are tolerable
("we may fail to prove a valid implication"); false positives are not.
[from-comment:135-145]

## Public entries

- `bool predicate_implied_by(predicate_list, clause_list, weak)` (153) —
  does `(AND of predicate_list)` follow from `(AND of clause_list)`?
- `bool predicate_refuted_by(predicate_list, clause_list, weak)` (223) —
  symmetric refutation prover.

## Mandatory preconditions

1. **AND/OR-flat inputs.** Nested AND under AND etc. just causes
   missed proofs, no incorrect ones. [from-comment:138-143]
2. **Immutable functions only.** "We dare not make deductions based on
   non-immutable functions, because they might change answers between
   plan time and execution time." Checked locally if not externally
   guaranteed (e.g. CheckPredicate on index predicates). [from-comment:144-151]

## Weak vs strong proof

`weak=true` means the prover may use SQL three-valued logic shortcuts
that consider NULL acceptable; `weak=false` requires the stricter "must
be TRUE" semantics. Partial indexes use weak; some uses (RLS) require
strong.

## Tags
`[verified-by-code]` ×2, `[from-comment]` ×4
