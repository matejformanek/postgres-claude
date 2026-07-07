# Persona: Michael Paquier

- **Last verified:** 2026-06-12
- **Source pin:** e18b0cb7344
- **Method:** `git log` mining of `source/` (commit bodies parsed for trailers, subjects scanned for prefix patterns, paths bucketed by subsystem) + cross-cut against `committer-map.md`, `contributor-map.md`, `domain-ownership.md`. No mailing-list archives.

## Role + email(s)

- Role: committer (active 24mo), core team member.
- Primary email: `michael@paquier.xyz` — single identity in the 24mo window.
- Lifetime committer rank: **#5** (2,476 lifetime commits — see `committer-map.md`).
- Identity rollups: name accent variant "Michaël Paquier" folded to "Michael Paquier" per `contributor-map.md` display picker.

## Activity profile (last 24mo: 2024-06-11 .. 2026-06-11)

| Trailer | Count |
|---|---:|
| Commits authored (`%an` as committer) | 723 (**most prolific committer in 24mo**) |
| Commits w/ `Discussion:` URL | 709 (98%) |
| Commits w/ `Backpatch-through:` | 183 (25%) |
| Reviewed-by trailer appearances (any commit) | 235 |
| Reported-by | 14 |
| Author trailer appearances | 70 |
| Co-authored-by | 33 |
| Other (Suggested + Tested + Diagnosed) | 36 |
| **Total trailer appearances** | **355** |

Self-authorship on his pushed commits: 66 explicit `Author: Michael Paquier`, 194 with no Author trailer (mostly small fixes), **463 with someone else as Author**. So roughly **64% of what he pushes is committing other people's patches** — the inverse of Tom Lane. He is heavily a committer-of-others.

Cross-verified against `contributor-map.md`: row "Michael Paquier | 70 | 235 | 14 | 36 | 355" matches.

## Domain ownership

From `domain-ownership.md` per-subsystem leadership (24mo):

- `src/backend/utils/` — **top committer** (168 commits, narrowly ahead of Peter Eisentraut 164 and Tom Lane 137).
- `src/test/regress/` and `src/test/modules/` — **top committer** (249 / 261 file-touches). He is the closest thing to a "test infrastructure maintainer." Authored `injection_points` and the `Add a test module for Bitmapset` series.
- `src/backend/access/` — top committer (101 commits, ahead of Peter Geoghegan 87 and Melanie Plageman 83).
- `src/backend/statistics/` — top committer (28 commits, ahead of Jeff Davis 18). The pg_dependencies/pg_ndistinct/pg_restore_extended_stats infrastructure is his.
- `src/bin/psql/` — heavy (67 file-touches; `psql:` prefix commits are common).
- `doc/src/sgml/` — top-4 (118 commits, behind only Bruce Momjian).

**Read:** Michael is the project's broadest committer-of-record. His 723 24mo commits span virtually every backend subsystem. The pattern is *commit pickup*: he watches the CommitFest, picks up smaller-scoped fixes from many authors, applies them, runs tests, pushes. This makes him the highest-throughput committer but it ALSO means he is a primary integration choke-point for new contributors.

## Style + patterns

### Commit message style

Subject prefix histogram (top 10):

| Prefix | Count |
|---|---:|
| `Fix ...` | 157 |
| `Add ...` | 104 |
| `doc:` | 37 |
| `Improve ...` | 33 |
| `Remove ...` | 32 |
| `psql:` | 27 |
| `injection_points:` | 20 |
| `Use ...` | 19 |
| `pg_stat_statements:` | 16 |
| `Move ...` | 15 |

- Heavy use of **module/tool-tag colon prefix** (`doc:`, `psql:`, `pg_stat_statements:`, `injection_points:`, `meson:`, `pg_dump:`). This is more disciplined than Tom Lane's mostly-bare-imperative style. If your patch touches `src/bin/psql/`, expect the landed subject to start with `psql: `.
- Average subject length: 53.6 chars.
- Imperative + period at end (project norm).

### Body conventions

`%B` mean ≈ 17 lines / commit, **median = 15 lines**. Substantial but not as long as Tom Lane's (median 17). Bodies typically include:

1. One-paragraph context (what is the patch about).
2. Trailer block always present: at minimum `Discussion:` (98% rate), often `Reviewed-by:` + `Author:`.
3. Frequently a back-patch range and rationale.

Compared with Tom Lane: Michael's bodies are more **operational** ("here's what this does and why we want it") and less **narrative** ("here's the symptom, here's the root cause, here's the API design"). This matches his role as committer-of-others: he doesn't always need to re-explain root cause if the original Author wrote the body.

### Discussion: URL discipline

**98% of his commits cite a `Discussion:` URL** (709/723) — the highest discipline of any active committer in this Phase B set. The 14 without are mechanical (catalog version bump scripts, tzdata, copyright). If you submit a patch to him without a thread URL, expect immediate pushback.

### Backpatch behavior

**25% backpatch rate** (183/723) — highest absolute count of any committer in the 24mo window and one of the highest ratios. He is a primary stable-branch maintainer. Expect him to ask "should this be backpatched?" on every correctness fix.

### Test-first instinct

The high incidence of `injection_points:` (20), `test_bitmapset:` (multiple), and `Split regression tests` subjects indicates Michael **adds tests proactively, often as separate commits before or alongside the feature**. Three of his top-10 churn commits in the last 12mo are test-only or test-infrastructure changes. Patches he reviews with thin test coverage will typically be returned with a request for more.

### Revert/fixup pattern

Michael does push revert commits when needed (rare but visible). His self-fix follow-up pattern is to push small `Improve ...` or `Fix ...` follow-ons rather than rewrite history. Examples: `test_bitmapset: Expand more the test coverage` (Sep 2025) followed by `test_bitmapset: Simplify code of the module` (Oct 2025) — same module, iterative.


## Scenarios I'd review
<!-- persona-scenarios:auto -->

*Derived from Domain-ownership paths overlapping each scenario's §Files section. If this persona claims a directory and a scenario mentions any file under it, they're a likely reviewer.*
*Refresh via `scripts/build-persona-scenario-matrix.py`.*

| Scenario | Via path(s) |
|---|---|
| [`add-new-aggregate-function`](../scenarios/add-new-aggregate-function.md) | `src/backend/utils`, `src/test/regress` |
| [`add-new-bgworker`](../scenarios/add-new-bgworker.md) | `src/test/modules`, `src/backend/utils` |
| [`add-new-buffer-strategy`](../scenarios/add-new-buffer-strategy.md) | `src/backend/utils`, `src/backend/access` (+1) |
| [`add-new-builtin-function`](../scenarios/add-new-builtin-function.md) | `src/backend/utils`, `src/test/regress` |
| [`add-new-cast`](../scenarios/add-new-cast.md) | `src/test/regress` |
| [`add-new-cost-model-knob`](../scenarios/add-new-cost-model-knob.md) | `src/backend/utils`, `src/backend/access` (+1) |
| [`add-new-data-type`](../scenarios/add-new-data-type.md) | `src/backend/utils`, `src/test/regress` |
| [`add-new-error-code`](../scenarios/add-new-error-code.md) | `src/backend/utils` |
| [`add-new-expression-eval-step`](../scenarios/add-new-expression-eval-step.md) | `src/backend/utils`, `src/test/regress` |
| [`add-new-guc`](../scenarios/add-new-guc.md) | `src/test/modules`, `src/backend/utils` (+1) |
| [`add-new-hook`](../scenarios/add-new-hook.md) | `src/test/modules` |
| [`add-new-index-am`](../scenarios/add-new-index-am.md) | `src/bin/psql`, `src/backend/utils` (+2) |
| [`add-new-lwlock-tranche`](../scenarios/add-new-lwlock-tranche.md) | `src/test/modules`, `src/backend/utils` (+1) |
| [`add-new-node-type`](../scenarios/add-new-node-type.md) | `src/backend/utils` |
| [`add-new-operator`](../scenarios/add-new-operator.md) | `src/backend/utils` |
| [`add-new-operator-class`](../scenarios/add-new-operator-class.md) | `src/backend/access`, `src/test/regress` |
| [`add-new-pg-stat-view`](../scenarios/add-new-pg-stat-view.md) | `src/backend/utils`, `src/test/regress` |
| [`add-new-plan-node`](../scenarios/add-new-plan-node.md) | `src/backend/utils` |
| [`add-new-protocol-message`](../scenarios/add-new-protocol-message.md) | `src/test/modules`, `src/backend/access` |
| [`add-new-shared-memory-region`](../scenarios/add-new-shared-memory-region.md) | `src/test/modules`, `src/backend/utils` |
| [`add-new-sql-keyword`](../scenarios/add-new-sql-keyword.md) | `src/bin/psql`, `src/backend/utils` (+1) |
| [`add-new-system-catalog-column`](../scenarios/add-new-system-catalog-column.md) | `src/backend/utils`, `src/backend/access` (+2) |
| [`add-new-system-view`](../scenarios/add-new-system-view.md) | `src/backend/utils`, `src/test/regress` |
| [`add-new-table-am`](../scenarios/add-new-table-am.md) | `src/backend/access`, `src/test/regress` |
| [`add-new-test-module`](../scenarios/add-new-test-module.md) | `src/test/modules` |
| [`add-new-utility-statement`](../scenarios/add-new-utility-statement.md) | `src/bin/psql` |
| [`add-new-wal-record`](../scenarios/add-new-wal-record.md) | `src/test/modules`, `src/backend/access` |
| [`add-startup-hook`](../scenarios/add-startup-hook.md) | `src/test/modules`, `src/backend/utils` |
| [`bump-catversion`](../scenarios/bump-catversion.md) | `src/backend/access` |
| [`integrate-with-plpgsql`](../scenarios/integrate-with-plpgsql.md) | `src/test/regress` |
| [`remove-from-catalog`](../scenarios/remove-from-catalog.md) | `src/test/regress` |

<!-- /persona-scenarios:auto -->


## Subsystems I know
<!-- persona-subsystems:auto -->

*Derived from Domain-ownership paths overlapping each subsystem's `## Files owned` block.*
*Refresh via `scripts/build-persona-scenario-matrix.py`.*

- [`access-heap`](../subsystems/access-heap.md)
- [`access-nbtree`](../subsystems/access-nbtree.md)
- [`access-transam`](../subsystems/access-transam.md)
- [`utils-cache`](../subsystems/utils-cache.md)
- [`utils-mmgr`](../subsystems/utils-mmgr.md)

<!-- /persona-subsystems:auto -->

## Common reviewer/collaborator partners

Top reviewers credited on commits Michael pushed (24mo):

| Reviewer | Count |
|---|---:|
| Michael Paquier (self) | 99 |
| Chao Li | 39 |
| Bertrand Drouvot | 37 |
| Tom Lane | 17 |
| Nazir Bilal Yavuz | 14 |
| Sami Imseih | 13 |
| Daniel Gustafsson | 12 |
| Ashutosh Bapat | 11 |
| Peter Eisentraut | 11 |
| Andrey Borodin | 11 |

Self-credit rate: 99/723 = 14% — moderate. He uses `Reviewed-by: Michael Paquier` when he did substantive review beyond pushing.

**Cross-reviewing pattern:** Michael's biggest paired reviewer is **Bertrand Drouvot** (37 reviews on Michael's commits). Inversely, `contributor-map.md` shows "Michael Paquier" as a top-2 reviewer on commits by both Nathan Bossart (35 reviews) and Peter Eisentraut. He is the most cross-cutting reviewer in PG's current committer pool.

**Chao Li (39 reviews)** is the rising 2025+ heavy reviewer (see `contributor-map.md` notes). He reviews Michael's work the most of any non-Michael reviewer — significant for Phase D since many MP-committed patches will pass through Chao's review.

## What to expect on a patch he would review

1. **He will commit it, not just review it.** Confidence: very high. Michael is committer-of-record on 64% of patches he touches — i.e. he is the most likely committer for a generic small-to-medium-scoped patch that doesn't have a natural subsystem owner. If your patch lands in his queue, expect a quick turnaround (he commits at a rate of ~30/month).

2. **He will demand a `Discussion:` URL.** Confidence: very high — 98% of his commits cite one. A patch without a hackers thread will be returned.

3. **He will probably re-tag your subject.** Confidence: medium-high. If your patch touches `psql`, `pg_stat_statements`, `pg_upgrade`, etc., expect the landed subject to start with `<module>:`. Submit with this prefix to avoid the rewrite.

4. **He will check test coverage.** Confidence: medium-high — `injection_points:` and `test_bitmapset:` infrastructure work shows he cares about test scaffolding. Patches changing behavior without an updated regression test will be flagged.

5. **He will ask about backpatching.** Confidence: high (25% rate). On correctness fixes, expect a "back to which branch?" question.

6. **He will keep the trailer block clean.** He maintains comma-separated `Reviewed-by:` lines and adds explicit `Co-authored-by:` when warranted. Submit your patch with proposed trailers if you can.

## Landmark commits (last 12mo)

- `ba97bf9cb7b` (Mar 2026): Add support for "exprs" in pg_restore_extended_stats(). — Top-churn 12mo commit (3,189 lines); extends statistics restore infrastructure.
- `1b105f9472b` (Dec 2025): Use palloc_object() and palloc_array() in backend code. — Project-wide cleanup using the new safer allocation macros.
- `00c3d87a5ca` (Sep 2025): Add a test module for Bitmapset. — New test infrastructure that subsequently caught real bugs (cited from other commits).
- `b45242fd30f` (Jul 2025): Move code for the bytea data type from varlena.c to new bytea.c. — Long-overdue refactor splitting a giant utility file.
- `e1405aa5e3a`, `44eba8f06e5` (Nov 2025): Add input function for data type pg_dependencies / pg_ndistinct. — Statistics-import infrastructure.

## Notes / hedges

- **Author=other 463 vs self 66** is the most informative single number for Michael's persona — it cleanly distinguishes him from Tom Lane (208 self vs 128 other) and shows the project's two distinct top-committer archetypes: Tom = own-work author, Michael = patch-pickup committer.
- **The "Michael commits Bertrand Drouvot's work" axis** is one of the busiest author-committer pairs in the project (101 of Bertrand's 107 24mo Author credits go through Michael per `contributor-map.md`'s "Top crediting committers" column for Bertrand). Bertrand is functionally Michael's most frequent patch source.
- **Cross-references:**
  - `tom-lane.md` — the opposite archetype (high self-author).
  - `nathan-bossart.md` — cross-reviews Michael often (Nathan credits Michael 35× as reviewer).
  - Contributor-map's "Chao Li" entry (340 R-by appearances since 2025-08) is a Phase B follow-up persona candidate; he reviews Michael heavily.
- **Subject-prefix discipline (`psql:`, `pg_stat_statements:`, etc.)** is more rigid for Michael than for Tom Lane. Phase C review-skill calibration should weight this when the proposed landing committer is likely Michael.
