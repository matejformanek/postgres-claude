# Persona: Richard Guo

- Last verified: 2026-06-12
- Source pin: e18b0cb7344
- Method: git log mining of source/ + cross-cut against committer-map.md,
  contributor-map.md, domain-ownership.md.

## Role + email(s)

- Committer since 2024-06 (first commit-as-committer
  `e3a0304eba28` 2024-06-10, "Fix comment about cross-checking
  varnullingrels"). [verified-by-code]
- Author email in trailers: `Richard Guo <guofenglinux@gmail.com>`.
  [verified-by-code]
- Listed in committer-map.md and the task brief with the
  `rguo@postgresql.org` committer alias. [from-committer-map]

## Activity profile (last 24mo)

| Vector                                                   | Count |
|----------------------------------------------------------|-------|
| Commits as committer (24mo)                              | 111   |
| Commits as committer, all time                           | 112   |
| Commits authored by him via `Author:` trailer is implied — he commits his own work, so author == committer for ~85% of his commits | — |
| `Reviewed-by: Richard Guo` in other committers' commits (24mo) | 30 |
| First commit (as committer): 2024-06-10                  |       |
| Pre-2024-06 commits as committer                         | 0     |

Counts via `rtk proxy git -C source/ log --since='24 months ago'
--author='Richard Guo'` and `--committer='Richard Guo'`. The 111 figure
matches committer-map.md.

### Subsystem footprint (file touches, 24mo, top areas)

| Path                            | Touches |
|---------------------------------|--------:|
| src/test/regress                | 175     |
| src/backend/optimizer           | 155     |
| src/include/optimizer           | 30      |
| src/backend/utils               | 17      |
| src/include/nodes               | 16      |
| src/tools/pgindent              | 9       |
| src/backend/parser              | 7       |
| src/backend/executor            | 7       |
| src/backend/rewrite             | 6       |
| contrib/postgres_fdw/expected   | 6       |

Source: `git log --since='24 months ago' --author='Richard Guo'
--name-only --pretty=format:` then bucket by top-3 path components.
[verified-by-code]

## Domain ownership

- **Optimizer / planner internals.** Within
  `src/backend/optimizer/` and `src/include/optimizer/` he authored
  85 commits in 24mo vs Tom Lane's 40 in the same window — a
  **~2.1× lead** on the optimizer tree's mainline. [verified-by-code]
  This corroborates the "Tom is eclipsed by Richard in last 24mo"
  claim in domain-ownership.md.
- Sub-areas where his commits cluster (from commit subjects, 24mo):
  - **Self-join elimination** (`remove_self_join_rel()`,
    `remove_rel_from_query()` cleanups; 5+ commits).
  - **Eager aggregation** push-down (`eager_aggregation_possible_for_relation`,
    semi/antijoin safety, volatile-function handling; 5+ commits in
    2026).
  - **PlaceHolderVar / `varnullingrels` plumbing** (strip-PHV from
    index operands, partition-pruning operands, statistics lookup; 5+
    commits).
  - **`var_is_nonnullable()` / `expr_is_nonnullable()` family** —
    pushing NULL-aware optimizations into more expression types
    (`COALESCE`, `ROW IS NULL`, `IS DISTINCT FROM`, `BooleanTest`).
  - **Outer-join / semi-join / anti-join plan shapes** — "Right Semi
    Join" support, NOT-IN→anti-join conversion, LEFT→ANTI reduction
    under NOT NULL.
- Outside `optimizer/`: light touches to `nodes/` (parsenodes /
  plannodes plumbing for new planner features), `parser/`,
  `executor/` — virtually all in service of an optimizer change.

## Style + patterns

- **Title style:** terse, imperative, planner-specific. "Fix X in Y",
  "Teach planner to Z", "Optimize W using V". No "WIP", no ticket
  numbers. [verified-by-code, sample of 40 subjects]
- **Body style:** consistently long bodies (multi-paragraph) that
  explain the *invariant* being preserved or violated. Example:
  ffeda04259bb (eager aggregation for semi/antijoin) — 4 paragraphs
  walking through *why* `nulling_relids` was insufficient as a guard
  and what the new check enforces. [verified-by-code]
- **Heavy use of `Reported-by:` trailers** — he routinely credits the
  bug reporter (often `Alexander Lakhin`, who fuzz-tests the
  planner). [verified-by-code]
- **Frequent self-review then self-commit** of his own patches; for
  optimizer micro-fixes he sometimes commits with only a
  `Reviewed-by: Tender Wang` line. The high `Author == Committer`
  ratio is unusual — most other committers more often push other
  people's work.
- **Backpatch discipline:** the commits in the visible 24mo window
  are predominantly master-only feature work; the older fixes carry
  `Backpatch-through:` lines when relevant (e.g. 8b6c89e377b5
  "Fix integer overflow in nodeWindowAgg.c"). [from-comment]


## Scenarios I'd review
<!-- persona-scenarios:auto -->

*Derived from Domain-ownership paths overlapping each scenario's §Files section. If this persona claims a directory and a scenario mentions any file under it, they're a likely reviewer.*
*Refresh via `scripts/build-persona-scenario-matrix.py`.*

| Scenario | Via path(s) |
|---|---|
| [`add-new-aggregate-function`](../scenarios/add-new-aggregate-function.md) | `src/backend/optimizer` |
| [`add-new-cost-model-knob`](../scenarios/add-new-cost-model-knob.md) | `src/backend/optimizer`, `src/include/optimizer` |
| [`add-new-hook`](../scenarios/add-new-hook.md) | `src/backend/optimizer`, `src/include/optimizer` |
| [`add-new-operator`](../scenarios/add-new-operator.md) | `src/backend/optimizer` |
| [`add-new-plan-node`](../scenarios/add-new-plan-node.md) | `src/backend/optimizer`, `src/include/optimizer` |

<!-- /persona-scenarios:auto -->


## Subsystems I know
<!-- persona-subsystems:auto -->

*Derived from Domain-ownership paths overlapping each subsystem's `## Files owned` block.*
*Refresh via `scripts/build-persona-scenario-matrix.py`.*

- [`optimizer`](../subsystems/optimizer.md)

<!-- /persona-subsystems:auto -->

## Common reviewer/collaborator partners

From `Reviewed-by:` trailers inside his own commits (24mo):

| Reviewer            | Count |
|---------------------|------:|
| Tender Wang         | 17    |
| Tom Lane            | 11    |
| David Rowley        | 8     |
| wenhui qiu          | 7     |
| Matheus Alcantara   | 6     |
| Andrei Lepikhov     | 6     |
| Robert Haas         | 5     |
| Jian He             | 3     |
| Dean Rasheed        | 3     |

Going the other direction — who pushes patches that *he* reviewed
(`Reviewed-by: Richard Guo` 24mo, n=30): Tom Lane (4), Robert Haas
(4), Peter Eisentraut (4), David Rowley (2), then a long tail
(Plageman, Naylor, Davis, Fujii, Korotkov each 1). His review work
concentrates on Tom Lane's planner patches plus Robert Haas's
executor / parallelism work.

## What to expect on a patch he would review

- Will land on **optimizer correctness over micro-perf**. He'll ask
  whether the path is *valid* under outer-join NULL semantics before
  whether it's *fast*.
- Strong attention to **`varnullingrels`, PHV, EquivalenceClass, and
  RelOptInfo invariants** — if you touch any of these, expect a
  pointed question about what the new code does in the
  semi/anti/outer-join case.
- Likes **small targeted regression tests** alongside the fix.
  Look at `src/test/regress/expected/join.out`, `aggregates.out`,
  `subselect.out` for the test conventions he extends.
- Will probably credit a `Reported-by:` if your patch has any bug-
  report origin and you forgot the trailer.
- For genuinely large planner changes he tends to defer to Tom Lane
  ("Reviewed-by: Tom Lane" appears on 11 of his own commits). He'll
  review the patch, but expect a second pass from Tom for anything
  that touches join ordering or path generation deep enough to shift
  costs.

## Landmark commits (last 12mo)

- **`cf74558feb8f`** (2026-02-12) — "Reduce LEFT JOIN to ANTI JOIN
  using NOT NULL constraints." A new transformation that exploits
  catalog NOT NULL info to convert outer joins. Substantial new
  planner machinery. [verified-by-code]
- **`383eb21ebffe`** (2026-03-12) — "Convert NOT IN sublinks to
  anti-joins when safe." Long-standing optimizer wish; safety
  depends on NOT NULL of inner-side cols. [verified-by-code]
- **`f41ab51573a4`** (2026-02-10) — "Teach planner to transform
  `x IS [NOT] DISTINCT FROM NULL` to a NullTest." Plus paired
  commits 0aaf0de7fed8 and 0a379612540c optimizing `BooleanTest`
  and `IS DISTINCT FROM` with non-nullable inputs. The
  `expr_is_nonnullable()` family theme. [verified-by-code]
- **`ffeda04259bb`** (2026-06-03) — "Fix eager aggregation for
  semi/antijoin inner rels." Live demonstration of his style: a
  precise correctness fix to his own earlier eager-aggregation
  series, with a 4-paragraph explanation of why
  `nulling_relids` was the wrong guard. [verified-by-code]
- **`3a08a2a8b4fd`** + **`bd94845e8c90`** (2026-04-06) — paired
  fixes to eager aggregation (volatile functions; collation in
  grouping keys). Shows him maintaining the feature he introduced
  rather than handing it off. [verified-by-code]

## Notes / hedges

- **Rising star pattern, confirmed.** As a committer he has 0
  pre-2024-06 commits and 111 in the 24mo since — i.e. he was made
  a committer mid-window and has hit the ground running. The task
  brief's "since 2024-06" framing is exact. domain-ownership.md
  flags him as the emerging dominant force in the optimizer; the
  85-vs-40 file-touch count in `src/backend/optimizer/` vs Tom Lane
  over the same 24mo confirms this. [verified-by-code]
- **He continues to author most of what he commits.** Unlike Tom
  Lane (who pushes many other people's patches as committer),
  Richard's commits are overwhelmingly his own authored work plus a
  handful of reviewed-by trailers. This means his throughput is a
  more direct signal of *his* design activity than a senior
  committer's commit count would be.
- **Sustained 2026 cadence** — he is still landing multi-commit
  series in Q2 2026 (eager-aggregation fixups, HAVING-to-WHERE
  pushdown, etc.). No sign of slowdown. [verified-by-code]
- The 30 `Reviewed-by: Richard Guo` count is *lower* than peers
  like Tom Lane or David Rowley in the same window — Richard's
  contribution profile is heavier on authoring than on reviewing.
  Whether this shifts as he settles into the committer role is
  worth tracking. [inferred]
- His commits stay narrowly in the optimizer; he does not (yet)
  touch storage, replication, or access methods. Treat him as a
  **deep specialist** for planner / optimizer review routing.
