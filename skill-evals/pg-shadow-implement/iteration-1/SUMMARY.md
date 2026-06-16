# Iteration 1 — Summary

**Skill**: `pg-shadow-implement`
**Date**: 2026-06-16
**Method**: single-context, no subagents

## Prompts evaluated

1. Trigger/routing probe — outline the shadow procedure for a hackers thread URL.
2. Grade rubric probe — score a 90%-match, one-MVCC-design-diff, no-invariant run.
3. Anti-trigger probe — pg-shadow vs pg-feature-plan + pg-implement for real
   upstream-send-ready work.

## Scores

| Cohort | Passed / Total | Pass rate |
|---|---|---|
| with_skill | 29 / 29 | 1.000 |
| baseline   | 11 / 29 | 0.379 |

Skill delta: **+62.1pp** (18 additional assertions out of 29).

## What the skill clearly helped with

- 7-step structure (pick → spec → shadow → fetch → diff → gaps → aggregate)
  baseline got the rough shape but lost on step count, output dir
  (`knowledge/shadow-implementations/<slug>/`), and per-step artifact names.
- M-tag lineage (M1 fallback, M2 context, M3 cite verify, M4 REJECT-as-output,
  M5 engagement classification) — baseline didn't know these tags exist.
- Grade rubric specifics: ≥70% / 1-2 diffs = B; REJECT-A/B/C as a separate
  track for run that terminated at M4; `(design-only)` modifier.
- Anti-trigger list — baseline reasoned correctly from skill name alone but
  couldn't cite the frontmatter rule.
- Design-only variant (skip 3.3-3.5, no `dev/` branch) — baseline missed
  entirely.

## Where baseline kept up

- General shape of "calibration via shadow implementation" (skill name is
  self-explanatory).
- Patch-fetch-not-first discipline (clear from "shadow" framing).
- Same overall verdict on Eval 3 (don't use this for real work).
- Grade B on Eval 2 (right answer, but on intuition not rubric).
- Step 5 alternative skill chain naming (general PG-workflow knowledge).

## Edits proposed (see proposed-edits.md)

7 candidates. The strongest are:

1. **HIGH**: Inline `comparison.md` schema in Step 5.
2. **HIGH**: Inline `skill-gaps.md` schema in Step 6.
3. **MED**: Tighten REJECT-track mutual-exclusivity language with A-F track.
4. **MED**: Promote the COVER-only / patch-not-fetched rationale into Step 2 prose.
5. **MED**: Add M1-M5 lineage paragraph at Step 2 head.
6. **LOW**: Fix `domain-ownership.md` → `knowledge/personas/domain-ownership.md`.
7. **LOW**: Add `(design-only)` tag modifier row to rubric.

## Source-verification done

- `knowledge/personas/domain-ownership.md`, `.claude/commands/pg-shadow.md`,
  `knowledge/shadow-implementations/README.md`, money-fx-exchange artifacts,
  temp-file-compression spec.md — all verified to exist.
- The `planning/shadow-<slug>/brainstorm.md` path matches
  `pg-feature-brainstorm` SKILL.md:46.

## Decision

Skill is strong. Apply Edits 1-3 (defensive against rubric subjectivity),
Edit 4 (calibration-rationale emphasis), Edit 5 (M-tag lineage), Edit 6
(path-hygiene). Edit 7 is optional — fold into Edit 3 if compact.
