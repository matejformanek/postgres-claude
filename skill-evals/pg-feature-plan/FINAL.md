# pg-feature-plan — FINAL evaluation summary

Two-iteration single-context heavy eval of
`.claude/skills/pg-feature-plan/SKILL.md`.

## Score progression

| Run | with_skill | baseline | delta (skill - baseline) |
|---|---|---|---|
| Iteration 1 | 35 / 35 = 1.000 | 9 / 35 = 0.257 | +0.743 |
| Iteration 2 | 35 / 35 = 1.000 | 9 / 35 = 0.257 | +0.743 |

The skill clears the rubric at 100% on both runs; the +0.74 absolute
lift over baseline puts pg-feature-plan in the high cluster alongside
`wal-and-xlog`, `build-and-run`, and `commit-message-style` —
project-internal naming-rich skills where baseline knows the obvious
mechanics (pg_proc.dat + catversion + a regress test) but misses the
scenario layer + REJECT-track + reflex-map + cite discipline.

This is the canonical shape for an iter-2 result on a saturated rubric:
the numeric score doesn't move; the qualitative improvements show in
plan *shape*, not in assertion count. The improvements are:

- Iter-1's MERGE_THEN plan invented ad-hoc "NOT edited (no char-class
  change)" change-type strings. Iter-2 uses the first-class enum
  values introduced by Edit 1: `not edited (sync trap)`, `not edited
  (auto-generated)`, `not edited (build-time validator)`.
- Iter-1's REJECT plan cited the M2 / M5 sections and the
  review-checklist Phase 0 rubric by name, but had no template for
  Verdict-block contents. Iter-2's plan emits the spec-shaped Verdict
  block (grade + 5 reasons + lead reviewer + alternative + hand-off),
  with §2-§14 explicitly absent.
- Iter-1's "Likely reviewers" line was a generic two-name pick. Iter-2
  uses the reflex map: each name carries the reflex tag (Tom Lane =
  type-system / dump-determinism; Andres = hot-path; Noah = security).

## What changed between iter-1 and iter-2

Five edits applied (Edits 1+4+5 merged into one). Diff:

```
.claude/skills/pg-feature-plan/SKILL.md | 75 +++++++++++++++++++++++++++++++--
 1 file changed, 71 insertions(+), 4 deletions(-)
```

1. **Edit 1+4+5 (merged)** — §3 required-section description rewritten:
   change-type enum expanded with three "not edited" first-class
   values; example row showing `source/<path>:<line>` cite shape;
   "Pin contract reminder" paragraph naming the §8a coverage gate and
   the ADD-only rule explicitly.

2. **Edit 2** — new `## REJECT-track output shape` section between
   M5 Thread-engagement and the standard `## Output`. Spec-shapes the
   Verdict block: numbered reasons, predicted reviewer with reflex,
   alternative shape, hand-off to review-checklist Phase 0. Includes
   inline summary of the REJECT-A/B/C grade rubric (copied verbatim
   from `.claude/skills/review-checklist/SKILL.md` Phase 0).

3. **Edit 3** — §12 "Likely reviewers" expanded to a 7-anchor reflex
   map (Tom Lane / Andres / Noah / Michael / Peter E. / Amit-Masahiko /
   David-Richard / Melanie-Peter G.), each tagged with the subsystem
   reflex they apply.

4. **Edit 6** — Added "Dropping a scenario-checklist row from §3
   without explicit user approval" to the "Forbidden in Phase 2"
   list. Redundant by design with the new §3 reminder; the failure
   mode is high-value enough to forbid twice.

## Source-value verifications performed

Before applying edits:

- `source/src/backend/utils/adt/lockfuncs.c:624` —
  `pg_advisory_lock(int8)` comment present.
- `knowledge/personas/` directory has all 11 persona files named in
  Edit 3 (tom-lane.md, andres-freund.md, noah-misch.md,
  michael-paquier.md, peter-eisentraut.md, amit-kapila.md,
  masahiko-sawada.md, david-rowley.md, richard-guo.md,
  melanie-plageman.md, peter-geoghegan.md).
- REJECT-A/B/C grade table at
  `.claude/skills/review-checklist/SKILL.md:83-87` matches Edit 2's
  inline copy.
- `add-new-builtin-function.md` scenario has 11 checklist rows;
  `add-new-sql-keyword.md` has 16 (6 NOT-edited).
- `add-new-builtin-function` scenario's `last_verified_commit:
  e18b0cb7344` is recent relative to HEAD `b5e2649db64`.

All values used in the edits match source exactly.

## Verdict

`pg-feature-plan` is **ready**. The skill carries the highest density
of project-internal contract surface of any skill in the campaign:
Step 0 scenario pin, §3 pin-contract reminder (new), §8a coverage gate,
M2 context-awareness probe, M5 engagement classification, REJECT-track
output shape (new), §9 hand-off line distinction (`/pg-implement` vs
review-checklist Phase 0), and §12 reflex-map (new). Baseline cannot
reproduce any of these surfaces from general PG knowledge — the +0.74
absolute lift is the structural floor for project-internal planner
skills, and rubric saturation means the next signal will come from
real-use runs of `/pg-plan <feature>`.

Files:
- `.claude/skills/pg-feature-plan/SKILL.md` (edited; 71 insertions, 4 deletions)
- `skill-evals/pg-feature-plan/iteration-1/` (5 files)
- `skill-evals/pg-feature-plan/iteration-2/` (4 files)
