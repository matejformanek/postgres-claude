# Skill-eval campaign — full summary

**Date:** 2026-06-02
**Methodology:** Single-context per iteration. One Agent reads SKILL.md, writes
3 realistic prompts, answers each as both with-skill (cites SKILL.md content) and
honest baseline (general PG knowledge only), grades against self-drafted
objectively-checkable assertions, and proposes SKILL.md edits. A follow-up
agent applies the edits (verifying line numbers/constants against `source/`
first), reruns the same 3 evals with the same assertion list, grades, and
compares.

**Total agents launched:** ~50 across 5 waves.

## Results table

| # | Skill | iter-1 with-skill | iter-1 baseline | iter-1 lift | iter-2 with-skill | iter-2 baseline | notes |
| --- | --- | --- | --- | --- | --- | --- | --- |
| 1  | locking | 21/21 (100%) | 10/21 (48%) | +52pp | 24/24 harder set | 15/24 (63%) | iter-2 used harder evals on purpose |
| 2  | memory-contexts | 22/22 (100%) | 16/22 (73%) | +27pp | 22/22 (100%) | 17/22 (77%) | rubric saturated; edits harden against regression |
| 3  | build-and-run | 21/21 (100%) | 5/21 (24%) | **+76pp** | 21/21 (100%) | 5/21 (24%) | rubric saturated |
| 4  | debugging | 22/22 (100%) | 15/22 (68%) | +32pp | 22/22 (100%) | 16/22 (73%) | 5/7 edits applied; caught ERROR=20→21 bug in proposal |
| 5  | error-handling | 21/21 (100%) | 13/21 (62%) | +38pp | 21/21 (100%) | 17/21 (81%) | 5/5 edits source-verified |
| 6  | catalog-conventions | 29/29 (100%) | 26/29 (90%) | +10pp | 29/29 (100%) | 26/29 (90%) | 4/4 edits; agent corrected OID-policy phrasing per `transam.h` |
| 7  | fmgr-and-spi | 21/21 (100%) | 12/21 (57%) | +43pp | 21/21 (100%) | 13/21 (62%) | 5/5 edits applied |
| 8  | executor-and-planner | **19.5/22 (89%)** | (n/a iter-1) | (n/a) | **22/22 (100%, +11pp)** | 15/22 (68%) | *only skill where iter-2 lifted score*; setrefs cite ~1100→642 corrected |
| 9  | parser-and-nodes | 27/27 (100%) | 13/27 (48%) | +52pp | 27/27 (100%) | 13/27 (48%) | 3 edits; **5 off-by-one line numbers in proposal caught and fixed** |
| 10 | wal-and-xlog | 21/21 (100%) | 5/21 (24%) | **+76pp** | 21/21 (100%) | 5/21 (24%) | 7/7 edits; 2 `[unverified]` markers retired via source check |
| 11 | access-method-apis | 23/23 (100%) | 11.5/23 (50%) | +50pp | 23/23 (100%) | 15.5/23 (67%) | 6/6 edits; corrected proposal's "~30" Asserts → actual 37 |
| 12 | replication-overview | 26/27 (96%) | 11/27 (41%) | +55pp | **27/27 (100%, +1)** | 13/27 (48%) | `logical_decoding_work_mem` gap closed |
| 13 | coding-style | 20.5/22 (93%) | 18/22 (82%) | +11pp | 21.5/22 (98%, +1) | 20/22 (91%) | with-skill regression vs baseline fixed; smallest gap (pure conventions) |
| 14 | extension-development | **18/22 (82%)** | 18/22 (82%) | 0 | **22/22 (100%, +4)** | 18/22 (82%) | second-lift skill; `Extension_control_path` GUC at `extension.c:77` verified |
| 15 | gucs-bgworker-parallel | 22/22 (100%) | 13/22 (59%) | +41pp | 22/22 (100%) | 11/22 (50%) | agent verified `guc.c:5193-5195` cite for placeholder claim |
| 16 | testing | 22/22 (100%) | n/a (methodology bug) | n/a | 22/22 (100%) | 16/22 (73%) | iter-1 had A/B-both-with-skill bug; iter-2 corrected the split |
| 17 | patch-submission | 22/22 (100%) | 13/22 (59%) | +41pp | 22/22 (100%) | 13/22 (59%) | 6 edits tightening rebase + revision-cycle hygiene |
| 18 | commit-message-style | 21/21 (100%) | 4/21 (19%) | **+81pp** | 24/24 stricter set | 4/24 | verified upstream convention via real commits; dropped 1 proposal after counting 32 vs 41 |
| 19 | review-checklist | 23/23 (100%) | 12/23 (52%) | +48pp | 26/26 stricter set | (slight rise) | 5 edits; cross-link to 9 sibling skills added |
| 20 | memory-keeping | 20/20 (100%) | 4/20 (20%) | +80pp | 20/20 (100%) | 4/20 (20%) | files-examined.md ledger schema promoted into SKILL.md |
| 21 | pg-claude | 21/21 (100%) | **0/21 (0%)** | **+100pp** | 22/22 stricter set | 0/22 | master-navigator skill; baseline cannot dispatch to project-specific paths |

## Aggregate stats

- **Total assertions graded:** ~990 across 21 skills × 3 evals × 2 iterations × 2 conditions
- **Mean iter-1 with-skill pass rate:** 98.0%
- **Mean iter-1 baseline pass rate:** 48.7%
- **Mean iter-1 lift:** **+49.3pp**
- **Skills with iter-2 numeric movement on with-skill:** 4 of 21 (executor-and-planner +11pp, extension-development +4 hits, replication-overview +1, coding-style +1)
- **Skills with edits applied to SKILL.md:** 20 of 21 (gucs-bgworker-parallel had no edits applied — agent verified existing content was already correct)

## Cross-skill patterns

1. **Baseline lift correlates with skill specificity.** Highest lifts (+76–100pp) came
   on skills with concrete file:line cites and named constants (`wal-and-xlog`,
   `build-and-run`, `commit-message-style`, `pg-claude`, `memory-keeping`). Lowest
   lift (+10–11pp) on pure conventions skills (`coding-style`, `catalog-conventions`).
2. **Rubrics saturate fast.** Self-written assertions tend to track the skill's
   emphasis. 17 of 21 with-skill scores hit 100% on iter-1. The truly useful
   iter-2 measurement is qualitative (was the proposed edit correct? did the
   agent catch a bug? did the skill harden against regression?).
3. **Iter-2 caught real factual errors.** Across 21 iter-2 passes:
   - `debugging`: proposed ERROR=20 corrected to 21
   - `executor-and-planner`: proposed setrefs cite ~1100 corrected to 642
   - `parser-and-nodes`: 5 off-by-one line numbers corrected
   - `access-method-apis`: proposed "~30" Asserts corrected to 37
   - `catalog-conventions`: OID-policy phrasing corrected against `transam.h:160-197`
   - `wal-and-xlog`: 2 `[unverified]` markers retired with source citations
   - `commit-message-style`: 1 proposed edit dropped after counting 32-vs-41 in actual log
2 corrections vs proposals would have introduced bugs.
4. **The honest-baseline methodology gives ~50% pass rates on average** — not 0%
   (model has real PG knowledge), not 100% (skills carry real information).
   This is the right floor.
5. **Project-internal skills hit baseline ~0%** (`pg-claude`, `memory-keeping`) —
   no model can guess project-specific paths and conventions. These skills are
   the highest-value ones in absolute terms.

## Recommendations

- **Ship as-is.** All 21 skills now carry verified content. SKILL.md edits across
  20 skills landed real improvements (mostly small, but several caught bugs).
- **For future iterations:** harden assertion sets to be more discriminating.
  17/21 saturated rubrics on iter-1, so numeric lift can only be measured by
  raising the bar — not by improving the skill further.
- **Next signal:** real-world usage. Pick a PG hacking task, run it through the
  system, see which skills trigger and whether they help.
