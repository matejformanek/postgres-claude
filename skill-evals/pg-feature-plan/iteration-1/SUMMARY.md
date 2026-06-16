# Iteration 1 — summary

Single-context heavy eval pass against `.claude/skills/pg-feature-plan/SKILL.md`.

## Score

| Condition | Score | Rate |
|---|---|---|
| with_skill | 35 / 35 | 1.000 |
| baseline   | 9 / 35  | 0.257 |
| **Lift**   |         | **+0.743** |

Rubric saturates on with_skill (typical for skills with a clear structural
spine). The +0.74 absolute lift is at the high end of the campaign
distribution — comparable to wal-and-xlog, build-and-run, and
commit-message-style.

## Eval coverage

1. **Builtin function plan** — exercises Step 0 scenario-match against
   add-new-builtin-function, §3 pin contract, §4 catalog impact, §12
   commit-style routing.
2. **MERGE_THEN keyword plan** — exercises the scenario-coverage gate on
   a 16-row scenario where 6 rows are "NOT edited". The high-value
   scenario integration probe.
3. **REJECT-track plan for April-1 money_fx_exchange()** — exercises M2
   Context-awareness + M5 Engagement classification + §9 REJECT hand-off.

## Baseline shape

Baseline missed: scenario names (project-internal pin contract); 6 of 16
NOT-edited keyword rows; REJECT-A/B/C grade convention; reflex-map for
predicted reviewers; M2/M5 taxonomy names; /pg-implement vs /implement;
hand-off to review-checklist Phase 0 for REJECT; specific source/<path>:<line>
cites.

## Edits proposed (see proposed-edits.md)

Six edits aimed at hardening the structural contract:

1. Echo Step 0 pin contract into §3 required-section description.
2. Specify REJECT-track output shape inline (Verdict block contents).
3. Reflex-map hint in §12 Likely reviewers (5 named anchors).
4. Cross-link §3 → §8a coverage gate explicitly.
5. Show source/<path>:<line> cite-shape by exemplar in §3.
6. Add silent-scenario-drop to Forbidden in Phase 2 list.

Edits 1, 4, 6 are the high-value cluster (scenario-drop prevention).
Edits 2, 3 sharpen the REJECT track. Edit 5 is cosmetic.
