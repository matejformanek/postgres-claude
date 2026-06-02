# Skill-eval campaign — interim status

**Goal:** Full 2-iteration skill-creator eval (test cases → with-skill/baseline
runs → grading → SKILL.md edits → rerun → diff) on each of the 21 skills.

**Methodology:** Single-context per-iteration. One Agent reads SKILL.md,
writes 3 realistic eval prompts, answers each as both with-skill and
honest baseline, grades against assertions, and proposes SKILL.md edits.
A second Agent applies edits + reruns evals + writes FINAL.md.

**Session paused:** hit API session limit mid-campaign (reset 2026-06-02
~03:10 Prague). 12 skills fully evaluated. 4 mid-iteration (iter-2 edits
were applied but not verified or graded). 5 not started.

## Status by skill

| Skill | iter-1 | iter-2 | FINAL.md | with-skill iter-1 | iter-1 baseline | iter-2 with-skill | notes |
| --- | --- | --- | --- | --- | --- | --- | --- |
| locking | ✓ | ✓ | ✓ | 21/21 | 10/21 | 24/24 (harder set) | strongest baseline lift +52pp; iter-2 used harder evals |
| memory-contexts | ✓ | ✓ | ✓ | 22/22 | 16/22 | 22/22 | edits applied; rubric saturated |
| build-and-run | ✓ | ✓ | ✓ | 21/21 | 5/21 | 21/21 | +76pp baseline lift; rubric saturated |
| debugging | ✓ | ✓ | ✓ | 22/22 | 15/22 | 22/22 | 5/7 edits applied; agent caught ERROR=21 (proposal said 20) |
| error-handling | ✓ | ✓ | ✓ | 21/21 | 13/21 | 21/21 | 5/5 edits applied, source-verified |
| catalog-conventions | ✓ | ✓ | ✓ | 29/29 | 26/29 | 29/29 | 4/4 edits applied; agent corrected OID-policy phrasing |
| fmgr-and-spi | ✓ | ✓ | ✓ | 21/21 | 12/21 | 21/21 | 5/5 edits applied |
| executor-and-planner | ✓ | ✓ | ✓ | **19.5/22** | (n/a) | **22/22 (+11.4pp)** | only skill where iter-2 moved score; setrefs cite numbers corrected before applying |
| parser-and-nodes | ✓ | ✓ | ✓ | 27/27 | 13/27 | 27/27 | 3 edits applied; 5 off-by-one line numbers caught and fixed |
| wal-and-xlog | ✓ | ✓ | ✓ | 21/21 | 5/21 | 21/21 | +76pp lift; 7/7 edits; 2 [unverified] retired |
| access-method-apis | ✓ | ✓ | ✓ | 23/23 | 11.5/23 | 23/23 | 6/6 edits; corrected proposal's "~30" Asserts to actual 37 |
| replication-overview | ✓ | ✓ | ✓ | 26/27 | 11/27 | **27/27 (+1)** | logical_decoding_work_mem gap closed |
| **coding-style** | ✓ | partial | ✗ | 20.5/22 | 18/22 | (interrupted) | iter-2 SKILL.md edits applied but not verified or graded |
| **extension-development** | ✓ | partial | ✗ | 18/22 | 18/22 | (interrupted) | iter-2 SKILL.md edits applied but not verified or graded |
| **gucs-bgworker-parallel** | ✓ | partial | ✗ | 22/22 | 13/22 | (interrupted) | iter-2 SKILL.md edits applied; agent verified guc.c:5195 before stalling |
| **testing** | ✓ | partial | ✗ | 22/22 + 21/22 (no baseline split — methodology bug) | n/a | (interrupted) | iter-2 has edits-applied.md + eval dirs but no grading.json |
| patch-submission | ✗ | ✗ | ✗ | — | — | — | not started |
| commit-message-style | ✗ | ✗ | ✗ | — | — | — | not started |
| review-checklist | ✗ | ✗ | ✗ | — | — | — | not started |
| memory-keeping | ✗ | ✗ | ✗ | — | — | — | not started |
| pg-claude | ✗ | ✗ | ✗ | — | — | — | not started |

## Headline numbers (12 fully evaluated)

- Mean iter-1 with-skill pass rate: **99.0%**
- Mean iter-1 baseline pass rate: **52.5%**
- Mean lift: **+46.5pp**
- Mean iter-2 with-skill pass rate: **99.4%**
- Only one skill (executor-and-planner) moved on iter-2 from a non-ceiling
  start; the rest had already saturated their rubrics on iter-1, so
  iter-2's value was qualitative (source-verified hardening, cite
  precision, gap closure for known weaknesses).

## Cross-skill patterns observed

1. **Baseline lift correlates with skill specificity.** Skills with
   concrete file:line cites and named constants (wal-and-xlog,
   build-and-run, access-method-apis) showed the biggest baseline gaps.
   Pure conventions (coding-style) showed smallest gap (~11pp).
2. **Rubrics saturate fast.** Self-written assertions tend to track the
   skill's own emphasis, so with-skill near-100% is largely a measurement
   artifact. Iter-2 wouldn't move the score even when content genuinely
   improved.
3. **Iter-2 caught factual errors.** 4 of 12 iter-2 passes corrected
   wrong line numbers or constant values in the iter-1 proposals
   (ERROR=20→21; ~30 Asserts→37; setrefs ~1100→642; 5 off-by-ones
   in parser-and-nodes).
4. **The "single-context" methodology bias is real but smaller than
   feared.** Honest baselines consistently scored ~50% — not 0% (the
   model has real PG knowledge) and not 100% (the with-skill cites and
   exact constants do carry information).

## Resumption plan (post-reset)

1. For coding-style, extension-development, gucs-bgworker-parallel,
   testing: verify the in-place SKILL.md edits via git diff, then
   re-run iter-2 evals + write FINAL.md.
2. For patch-submission, commit-message-style, review-checklist,
   memory-keeping, pg-claude: full iter-1 + iter-2 passes.
3. Final aggregation in skill-evals/SUMMARY.md.
4. Commit + push.

Skill artifacts on disk: `skill-evals/<name>/iteration-{1,2}/` + FINAL.md.
SKILL.md edits already applied in `.claude/skills/<name>/SKILL.md`.
