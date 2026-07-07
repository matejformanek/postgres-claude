# Persona: Robert Haas

- Last verified: 2026-06-12
- Source pin: e18b0cb7344
- Method: `git log` mining of `source/` (committer-filtered, 24 months) + cross-cut against `knowledge/personas/committer-map.md`, `contributor-map.md`, `domain-ownership.md`.

## Role + email(s)

- Committer email: `rhaas@postgresql.org`
- Long-time top-tier committer (lifetime rank #4-5 depending on how Eisentraut's two emails are merged). Owner of parallel query, replication progress, partitioning historically, and pg_basebackup / incremental backup tooling more recently.
- In the 24mo window, his lane is **optimizer extensibility + a new contrib module pair (`pg_plan_advice` + `pg_stash_advice`) + incremental backup tooling**. The pg_plan_advice work is the dominant feature thread.
- Affiliation: EDB (long-time).

## Activity profile (last 24mo) — trailer counts

| Metric | Count | Source |
|---|---:|---|
| Commits as committer (24mo) | 117 | `committer-map.md`; verified |
| Commits with Reviewed-by trailer | 66 (56%) | `committer-map.md` |
| Self Reviewed-by | 2 | `git log ... | grep -ci '^Reviewed-by: Robert Haas'` |
| Reviewed-by trailers earned on others' commits (24mo, per `contributor-map.md`) | 92 | `contributor-map.md` |
| Author trailers on his own commits | 8 explicit `Author:` + 5 `Co-authored-by:` | git log query |

The self-Reviewed-by count (2 out of 117) is the **opposite shape** from Amit Kapila (91/185). Haas does not self-credit. Instead, he credits external reviewers heavily.

**Subsystem footprint (24mo, his commits only — top dirs):**

| Path | Touched files-count |
|---|---:|
| `src/test/regress/` | 90 |
| `src/backend/optimizer/` | 73 |
| `src/backend/commands/` | 34 |
| `doc/src/sgml/` | 29 |
| `src/bin/pg_combinebackup/` | 23 |
| `src/include/nodes/` | 20 |
| `src/bin/pg_verifybackup/` | 19 |
| `src/bin/pg_basebackup/` | 19 |
| `src/include/optimizer/` | 18 |
| `contrib/pg_plan_advice/sql/` | 16 |

The optimizer + contrib (`pg_plan_advice` + `pg_stash_advice`) concentration is striking. Backup tooling (`pg_combinebackup`, `pg_verifybackup`, `pg_basebackup`) is a secondary lane covering ~60 file touches across his incremental-backup follow-up work.

## Domain ownership

- **`contrib/pg_plan_advice/` contrib module (PG 19-devel).** Sole owner, brand-new. Landed `5883ff30b02` ("Add pg_plan_advice contrib module"). The module exposes an extension API for influencing/disabling plan choices via persisted advice. ~25+ follow-up commits include `b1901e2895e` (DO_NOT_SCAN is simple tag), `5dcb15e89af` (refactor to invent `pgpa_planner_info`), `26255a32073` (Add `alternative_plan_name` field to PlannerInfo), `6455e55b0da` (DO_NOT_SCAN(relation_identifier)), `01b02c0ecad` (avoid GEQO crash), `0f93ebb3112` (subquery-pruned bug fix), `4321dcad475` (unique-semijoin bug fix). Very large feature thread.
- **`contrib/pg_stash_advice/` contrib module (PG 19-devel).** Sole owner. Landed `e8ec19aa321` ("Add pg_stash_advice contrib module"). Companion to pg_plan_advice — persists stashed advice to disk. Follow-ups: `c10edb102ad` (persist to disk), `878839bafe2` (reject overlong stash names).
- **Optimizer extensibility hooks.** `91f33a2ae92` ("Replace `get_relation_info_hook` with `build_simple_rel_hook`"), `0fbfd37cefb` ("Allow extensions to mark an individual index as disabled"), `0442f1c9eff` ("Add a `guc_check_handler` to the EXPLAIN extension mechanism"). The infra that makes pg_plan_advice possible — he adds the hook, then uses it.
- **`auto_explain` extension touch-ups.** `e972dff6c30` ("auto_explain: Add new GUC, `auto_explain.log_extension_options`"). Adjacent to the EXPLAIN-extension work.
- **`pg_overexplain`** contrib module enhancements (per `committer-map.md` row): `8d5ceb1` "pg_overexplain: additional EXPLAIN options".
- **Incremental backup tooling (`pg_combinebackup`, `pg_verifybackup`).** Continuing maintenance of the incremental backup feature he originally landed pre-window. Sample: `ffc226ab64d` ("Prevent restore of incremental backup from bloating VM fork").
- **Append/partition-wise planner micro-improvements.** `7358abcc607` ("Store information about Append node consolidation in the final plan"), `6e466e1e839` ("Fix `add_partial_path` interaction with `disabled_nodes`"), `8300d3ad4aa` ("Consider startup cost as a figure of merit for partial paths"), `e2ee95233ca` (partitionwise aggregate fix). Continuing his historical partition/parallel lane.
- **Memoize + nested loop interactions.** `dc47beacaa0` ("`get_memoize_path`: Don't exit quickly when `PGS_NESTLOOP_PLAIN` is unset"), `47c110f77e7` (respect disabled_nodes in `fix_alternative_subplan`).

## Style + patterns

- **Compact, surgical commit subjects.** "pg_plan_advice: Fix another unique-semijoin bug." "pg_plan_advice: pgindent." "doc: Fix a couple of mistakes in pgplanadvice.sgml." Subjects are mostly scoped (`pg_plan_advice:` prefix is used consistently), suggesting fast iteration on a single feature.
- **Many small follow-up commits per feature.** Like Korotkov, but at higher tempo. pg_plan_advice landed in `5883ff30b02` and has had 25+ follow-up commits in <6 months: bug fixes, refactors, pgindent runs, doc tweaks. He does not amend — each is its own SHA.
- **`Reviewed-by:` external, not self.** Top reviewers on his work: **Tom Lane (19), Lukas Fittl (14), Alexandra Wang (10), Andrei Lepikhov (9), Jakub Wartak (7)**. Heavy reliance on Lukas Fittl + Alexandra Wang specifically for pg_plan_advice review (they are both EDB / planning-related).
- **`Author:` trailer used sparingly.** Most pg_plan_advice commits are written by him (no `Author:` trailer; convention is that the committer is the author when no trailer is present). When he commits someone else's patch (rare in this window), the `Author:` trailer is explicit.
- **Self-Reviewed-by usage is anomalously LOW** — 2 out of 117. He does not credit himself even when he was the primary author. Contrast Kapila (91/185 ~50%), Korotkov (44/141 ~31%), Melanie (8/121 ~7%). Haas is at the bottom — he treats the trailer as strictly for external review.
- **Test additions in `src/test/regress/` are heavy.** 90 file touches in regress is one of the highest among feature committers (only Korotkov is comparable). Plus a new `test_plan_advice` module (`12444183e40`, `e0e4c132ef2`).
- **Bounds-checking discipline.** `c98ad086ad9` ("Bounds-check access to `TupleDescAttr` with an Assert") — small defensive commit characteristic of his style.


## Scenarios I'd review
<!-- persona-scenarios:auto -->

*Derived from Domain-ownership paths overlapping each scenario's §Files section. If this persona claims a directory and a scenario mentions any file under it, they're a likely reviewer.*
*Refresh via `scripts/build-persona-scenario-matrix.py`.*

_(none — persona has no owned paths that overlap any scenario's files)_

<!-- /persona-scenarios:auto -->


## Subsystems I know
<!-- persona-subsystems:auto -->

*Derived from Domain-ownership paths overlapping each subsystem's `## Files owned` block.*
*Refresh via `scripts/build-persona-scenario-matrix.py`.*

- [`contrib-pg_plan_advice`](../subsystems/contrib-pg_plan_advice.md)

<!-- /persona-subsystems:auto -->

## Common reviewer / collaborator partners

Top reviewers credited on his 117 24mo commits:

| Reviewer | R-by count |
|---|---:|
| Tom Lane | 19 |
| Lukas Fittl | 14 |
| Alexandra Wang | 10 |
| Andrei Lepikhov | 9 |
| Jakub Wartak | 7 |
| Jacob Champion | 5 |
| Haibo Yan | 5 |
| Greg Burd | 5 |
| Sami Imseih | 4 |
| Richard Guo | 4 |
| Matheus Alcantara | 4 |
| Amit Langote | 4 |

Top authors of patches he commits (mostly self-authored):

| Author | Count |
|---|---:|
| Robert Haas (self) | 8 explicit + 5 co-authored (many more implicit when no trailer) |
| Ilia Evdokimov | 3 |
| Tom Lane | 2 (co-authored) |
| Lukas Fittl | 2 (co-authored) |
| Jelte Fennema-Nio | 2 |
| Jakub Wartak | 2 |
| Ashutosh Bapat | 2 |

**Pattern: Haas runs a small EDB-affiliated review loop (Lukas Fittl, Alexandra Wang) for his pg_plan_advice work, with Tom Lane as the gravity-well senior reviewer.** Andrei Lepikhov + Richard Guo + Amit Langote provide the optimizer cross-cut. This is a **looser, optimizer-internals cluster** rather than a tight subteam — more reminiscent of Korotkov's reviewer pool than Kapila's.

Cross-cut to `contributor-map.md`: he earned 92 Reviewed-by appearances on others' commits in the 24mo window, with top pairings Nathan Bossart (20), Robert Haas self (15). He reviews broadly across optimizer + commands, not just his own lane.

## What to expect on a patch he would review

1. **Optimizer-internals review will be detailed.** Cost-model correctness, path-list invariants, partition-wise interactions — he asks the deep questions. His own commits show evidence of catching subtle bugs (e.g. `4321dcad475` "Fix another unique-semijoin bug").
2. **Extension-API stability is a concern.** With pg_plan_advice + pg_stash_advice in flight, he's actively shaping `build_simple_rel_hook`, `guc_check_handler`, `alternative_plan_name`. A patch that proposes a new optimizer hook in his vicinity will get scrutinized for ABI compatibility and forward design.
3. **Tom Lane will probably also weigh in.** 19 Reviewed-by from Tom Lane on Haas's commits in 24mo is consistent — Tom is the de facto senior reviewer of Haas's optimizer work, and the same is likely true the other direction.
4. **Tests in `src/test/regress/` are expected.** 90 file touches indicates he expects regress coverage for any optimizer behavior change. A patch landing without regress additions will be sent back.
5. **He works at high tempo on follow-ups.** Expect rapid back-and-forth (multiple commits/day during active feature work). Don't be surprised if a patch you submit gets a refactor request that lands within a day as a precursor commit.

## Landmark commits (last 12mo)

1. **`5883ff30b02` — Add pg_plan_advice contrib module** (early 2026). New extension allowing extensions to influence/disable planner choices via persisted advice. Foundational commit for a 25+-commit feature arc.
2. **`e8ec19aa321` — Add pg_stash_advice contrib module** (2026-04). Companion module that lets stashed advice persist across sessions / be loaded from disk.
3. **`8d5ceb1` — pg_overexplain: additional EXPLAIN options** (from committer-map). Continued evolution of the pg_overexplain extension. Demonstrates his ongoing investment in EXPLAIN extensibility.
4. **`91f33a2ae92` — Replace `get_relation_info_hook` with `build_simple_rel_hook`.** Optimizer hook API change that makes pg_plan_advice's intervention point cleaner. A breaking ABI change in an extension hook (extension authors must update); shipped with rationale in commit body.
5. **`0fbfd37cefb` — Allow extensions to mark an individual index as disabled.** Enables the DO_NOT_SCAN advice from pg_plan_advice. Pre-feature plumbing pattern.

## Notes / hedges

- The pg_plan_advice / pg_stash_advice work is brand-new (PG 19-devel) and may evolve significantly before release. The 25+ small follow-up commits in the 24mo window are characteristic of active flux. Treat his current "lane" as **provisional** — his historical lanes (parallel query, partitioning, incremental backup) are not represented strongly in 24mo data.
- EDB affiliation is `[from-comment]` (publicly well-known).
- The Lukas Fittl + Alexandra Wang co-reviewer pattern is likely an EDB internal loop; `[inferred]` — no explicit affiliation in trailers.
- The self-Reviewed-by count of 2 (vs Kapila's 91) is the most distinctive style finding. It is *not* that he reviews less of his own work; it is that he does not credit himself in the trailer. Cultural difference between committers.
- The 92 Reviewed-by trailers on others' work confirm he is doing substantial community review beyond his own feature commits — but not as heavily as Michael Paquier, Tom Lane, or Peter Eisentraut.
