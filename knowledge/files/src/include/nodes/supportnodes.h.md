# src/include/nodes/supportnodes.h

**Source pin:** `4b0bf0788b066a4ca1d4f959566678e44ec93422`
**Lines:** 448 [verified-by-code]

## Role

API for "planner support functions" (despite the name, some calls are
from executor too). A support function is a C-language SQL routine
with signature `supportfn(internal) returns internal` declared via
`pg_proc.prosupport`. When the planner / executor processes a call to
the *target* function it consults this support function passing one of
the request Nodes below; the support function can simplify the call,
provide a selectivity estimate, generate index conditions, etc.

## Public API (request kinds)

- `SupportRequestSimplify` (`:66-72`) — plan-time const-folding-style
  rewrite of a `FuncExpr`.
- `SupportRequestSimplifyAggref` (`:91-97`) — similar for `Aggref`
  (e.g. COUNT(1) → COUNT(*) swap).
- `SupportRequestInlineInFrom` (`:118-125`) — inline a FROM-clause
  function call as a Query subtree.
- `SupportRequestSelectivity` (`:146-162`) — return a Selectivity in
  [0,1] for boolean-returning function call. Unifies restriction
  and join estimation.
- `SupportRequestCost` (`:186-198`) — startup + per-tuple Cost
  estimate for the target function.
- `SupportRequestRows` (`:213-224`) — output rowcount for an SRF.
- `SupportRequestIndexCondition` (`:278-295`) — generate index-able
  conditions from a non-indexable function call; produces a
  `List *` of indexable expression nodes; can be marked lossy.
- `SupportRequestWFuncMonotonic` (`:345-355`) — declares a window
  function is monotonic; enables run condition pushdown.
- `SupportRequestOptimizeWindowClause` (`:388-399`) — let the
  support function adjust `WindowClause.frameOptions` (e.g.
  RANGE → ROWS) when safe.
- `SupportRequestModifyInPlace` (`:439-446`) — PL/pgSQL `x := f(x,...)`
  can pass a R/W expanded pointer if the support function approves.

## Invariants

- INV-SUPPORT-NULL-RESULT: "NULL pointer result (PG_RETURN_POINTER(NULL),
  not PG_RETURN_NULL()) indicates that the support function cannot do
  anything useful for the given request" (`:17-21` [from-comment]).
- INV-SUPPORT-FORWARD-COMPAT: support functions MUST return NULL (not
  error) for unrecognized request types — required for future
  request-type additions without breaking existing extensions
  (`:21-24` [from-comment]).
- INV-SIMPLIFY-NO-MUTATE: must NOT modify `*fcall` directly (`:62-65`
  [from-comment]); can reuse `fcall->args` parts in returned tree.
- INV-INLINEINFROM-PARSE-PASSED: returned Query must already have
  been through parse-analysis + rewrite (`:114-116` [from-comment]).
- INV-INDEX-COND-PSEUDO-CONSTANT: returned indexable expressions
  must have the index column on left, "pseudo-constant" on right
  (no volatile functions, no Vars of the target table)
  (`:244-256` [from-comment]).
- INV-WFUNC-MONOTONIC-PARTITION: monotonicity claim applies per
  partition only, not across the result (`:331-333` [from-comment]).
- INV-MODIFY-IN-PLACE: `f` must (1) leave object untouched on
  failure, (2) cope with self-reference in other args
  (`:413-425` [from-comment]).

## Trust boundary / Phase D surface

- **A15 echo — selectivity-leak surface.** `SupportRequestSelectivity`
  can return arbitrary [0,1]; combined with EXPLAIN ANALYZE row
  estimates, attacker can probe pg_statistic-like info through a
  side channel similar to MCV-leak. A custom support function for
  a victim's expression index could leak per-bucket selectivity
  to a non-owner.
- **A15 echo — cost-leak surface.** `SupportRequestCost` likewise
  observable via EXPLAIN. Distinct from selectivity but same
  privilege pattern.
- **Index-condition extraction (A7 echo).** A buggy
  `SupportRequestIndexCondition` that generates an index-condition
  not semantically equivalent to the original function call can
  return wrong rows OR — in the LEAKPROOF case — leak data behind
  RLS through `enable_partition_pruning` / index scans.
- **Inline-in-from rewrite (A7 echo).** `SupportRequestInlineInFrom`
  inlines a Query — RLS and ACL checks for the inlined relations
  must have already been performed in the returned tree. A
  custom support function inlining a Query that omits RLS quals
  produces an RLS bypass.
- **Window-func optimize.** Frame-option rewriting must be
  semantically equivalent; an incorrect optimization can change
  query results.
- **Modify-in-place expanded-object dance.** Bugs lead to
  PL/pgSQL variables being modified mid-statement-failure —
  observable as transactional integrity hole.

## Notable internals

- The big request-node-tag dispatch lives in each extension's
  support function: typical pattern is `if (IsA(req,
  SupportRequestSelectivity)) ...`. Forward-compat via NULL
  return.
- `prosupport` lookup happens during planner constfold and during
  cost/selectivity calls; cache invalidation tied to pg_proc
  invalidation.

## Cross-references

- `optimizer/planner.h` — `eval_const_expressions_mutator` invokes
  Simplify request.
- `optimizer/restrictinfo.h`, `optimizer/cost.h` — Selectivity /
  Cost call sites.
- `optimizer/indxpath.h` — IndexCondition consumer.
- `parser/parse_func.h` — `find_inheritance_children`-related
  inlining wiring? (actually `inline_set_returning_function`).
- `executor/nodeWindowAgg.c` — WFuncMonotonic & OptimizeWindowClause
  consumers.
- `pl/plpgsql/src/pl_exec.c` — ModifyInPlace consumer.

## Issues / drift

- `[ISSUE-TRUST: A15 echo — custom support functions for selectivity / cost can be EXPLAIN-observed by non-owners; per-estimator MCV-leak pattern (medium)] — source/src/include/nodes/supportnodes.h:146-198`
- `[ISSUE-TRUST: A7 echo — InlineInFrom can drop RLS quals if implementer is not careful; "must have been passed through rewrite" is a comment not an assertion (high)] — source/src/include/nodes/supportnodes.h:114-116`
- `[ISSUE-DOC: forward-compat NULL-on-unknown contract restated 6+ times — would benefit from a single header-level summary table of request kinds (low)] — source/src/include/nodes/supportnodes.h:21-24`
- `[ISSUE-CODE: SupportRequestIndexCondition.lossy default-true is fail-safe but easy to mis-set; mis-flagged "exact" claim can cause wrong rows (medium)] — source/src/include/nodes/supportnodes.h:263-265`
