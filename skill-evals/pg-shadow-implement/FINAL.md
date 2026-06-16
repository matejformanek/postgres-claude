# pg-shadow-implement — FINAL evaluation summary

Two-iteration skill eval of `.claude/skills/pg-shadow-implement/SKILL.md`
under the single-context heavy methodology (matching the campaign template
established by `replication-overview` and the 21-skill SUMMARY.md).

## Score progression

| Run | with_skill | baseline | delta |
|---|---|---|---|
| Iteration 1 | 29 / 29 = 1.000 | 11 / 29 = 0.379 | +0.621 |
| Iteration 2 | 32 / 32 = 1.000 | 12 / 32 = 0.375 | +0.625 |

Iteration 2 used a **stricter assertion set** (29 → 32 assertions): three
new probes targeted the inline-schema availability, the explicit mutual-
exclusivity language between A-F and REJECT tracks, the calibration-
signal-rationale phrasing in Step 2, and the M-ordinal continuation rule.
The skill still saturates at 100%, which means the iter-1 edits actually
delivered: every harder probe is now answerable from the SKILL.md text.

Baseline stays in the 37-38% range — the +0.62 lift is steady. This is
in line with the campaign mean (~+0.49pp lift) and consistent with skills
that carry highly project-internal procedural detail (the shadow-
implementation loop is unique to pg-claude; baseline can guess shape from
"shadow" but not the M-tags, the 7-step decomposition, the REJECT/A-F
mutual exclusivity, or the per-step artifact paths).

## What changed between iter-1 and iter-2

Six edits from `iteration-1/proposed-edits.md` were applied to SKILL.md
(Edit 7 folded into Edit 3 for compactness):

1. **Edit 1** — `comparison.md` schema embedded inline in Step 5.
2. **Edit 2** — `skill-gaps.md` schema embedded inline in Step 6.
3. **Edit 3** (with Edit 7 folded in) — Scoring rubric paragraph
   stating A-F vs REJECT-A/B/C mutual exclusivity, `(design-only)`
   tag modifier rule, and a "Disambiguating A vs B" trailing note
   ("any single design divergence moves the grade from A to B").
4. **Edit 4** — COVER-only / patch-not-fetched rationale promoted
   into Step 2 prose (`Reading the patch before Step 4 contaminates
   the calibration signal …`).
5. **Edit 5** — M1-M5 lineage block added at Step 2 head, cited to
   `knowledge/shadow-implementations/money-fx-exchange/skill-gaps.md`.
6. **Edit 6** — `domain-ownership.md` → `knowledge/personas/
   domain-ownership.md` (both occurrences).

`git diff --stat -- .claude/skills/pg-shadow-implement/SKILL.md` after
edits: **1 file changed, 107 insertions(+), 14 deletions(-)**.

## Source-value verifications performed

Before applying, the following claims in `proposed-edits.md` were
verified against the worktree filesystem:

- `knowledge/personas/domain-ownership.md` exists; bare
  `domain-ownership.md` does not. [verified-by-code]
- `.claude/commands/pg-shadow.md` and
  `knowledge/shadow-implementations/README.md` exist.
  [verified-by-code]
- money-fx-exchange / temp-file-compression artifacts present.
  [verified-by-code]
- `pg-feature-brainstorm` SKILL.md:46 writes to
  `planning/<slug>/brainstorm.md`, parameterising correctly as
  `planning/shadow-<slug>/brainstorm.md` for shadow runs.
  [verified-by-code, grep 2026-06-16]

All cited paths used in the edits match repo state exactly.

## Honest gotchas

This eval has two structural limitations worth flagging:

1. **The methodology depends on a real hackers thread URL; the eval
   can only simulate one.** Eval 1's prompt uses a hypothetical
   message-id (`https://www.postgresql.org/message-id/CAH2-Wz…fake-
   pgsql-2026-XYZ%40mail.gmail.com`). A real shadow run would
   actually fetch, classify, and reason about the COVER text — the
   eval is only checking whether the agent *procedurally outlines the
   correct steps*, not whether it can drive a fetch-classify-reason
   loop end-to-end. To check the latter, this skill needs a periodic
   live shadow run against a real thread — exactly what the
   methodology calls for, and exactly what the campaign mean-eval
   can't substitute for. money-fx-exchange (Phase E run 1) is the
   only live data point so far; one more run (e.g. temp-file-
   compression completion) would let us double-check the iter-1 edits
   in practice rather than just on paper.

2. **The grade rubric retains residual subjectivity.** Edit 3's
   "Disambiguating A vs B" note tightens the boundary considerably —
   any single design divergence moves A→B — but C-vs-B (where "3+
   design diffs" is the C threshold) still requires counting design
   choices, and the meaning of "design choice" vs "style choice" is
   not crisply defined. The skill compensates by encouraging the
   verdict line to include a one-line rationale, so future readers
   can audit the call. This is consistent with the campaign
   philosophy of "scoring rubrics carry intentional judgement"
   (per SUMMARY.md observation #2: rubrics saturate fast, the useful
   second-iteration signal is qualitative). The risk is two shadow
   runs of the same patch grading B and C respectively — but the
   audit trail in `comparison.md` makes the disagreement legible.

## Verdict

`pg-shadow-implement` is **ready**. The skill provides a strong absolute
lift over baseline (+0.62, in line with the campaign's project-internal-
skill range) and clears 100% of the assertion set at both iterations,
including the iter-2 stricter set that tested for the iter-1 edits.

The most important edit was **Edit 3** (REJECT-track mutual exclusivity
+ A-vs-B disambiguation): two of the three eval prompts depend on
unambiguous rubric interpretation, and before the edit a careful reader
could plausibly grade the same run A or B. After the edit, the answer
is forced.

The skill's structural choice — operationalize the methodology doc as a
runnable procedure, while keeping the methodology doc as the audit-of-
record — is preserved and reinforced (cf. the unchanged
`shadow-implementation-methodology.md` cross-reference at the bottom of
SKILL.md).

Files:
- `/Users/matej/Work/postgres/postgres-claude/.claude/worktrees/ft_meta_skill_creator_round_3/.claude/skills/pg-shadow-implement/SKILL.md`
- `/Users/matej/Work/postgres/postgres-claude/.claude/worktrees/ft_meta_skill_creator_round_3/skill-evals/pg-shadow-implement/iteration-1/`
- `/Users/matej/Work/postgres/postgres-claude/.claude/worktrees/ft_meta_skill_creator_round_3/skill-evals/pg-shadow-implement/iteration-2/`
