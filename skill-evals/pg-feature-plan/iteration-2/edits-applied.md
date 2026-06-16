# Edits applied — iteration 2

Six edits proposed in `iteration-1/proposed-edits.md`. Five applied, one
folded into another. `git diff --stat` against `iteration-1` shows:

```
.claude/skills/pg-feature-plan/SKILL.md | 75 +++++++++++++++++++++++++++++++--
 1 file changed, 71 insertions(+), 4 deletions(-)
```

## Edit 1 — Pin-contract reminder in §3 — APPLIED + MERGED with Edit 4 + Edit 5

Combined into one Edit at the §3 required-section description. The new
§3 text:

- Expanded `Change type:` enum to recognize `not edited (sync trap)` /
  `not edited (auto-generated)` / `not edited (build-time validator)`
  as first-class row shapes (so a planner doesn't have to invent
  conventions for the NOT-edited rows of a scenario like
  add-new-sql-keyword).
- Added an example row showing `source/<path>:<line>` cite shape
  (Edit 5 — exemplar in the description).
- Added the "Pin contract reminder" paragraph naming the §8a coverage
  gate (Edit 4) and explicitly stating the ADD-only / never-DROP rule.

## Edit 2 — REJECT-track output shape — APPLIED

Inserted as a new top-level section `## REJECT-track output shape (when
verdict is REJECT)` between the M5 Thread-engagement classification
section and the `## Output` section. Contains:

- Numbered list of 5 required Verdict-block contents.
- Explicit statement that §2-§14 do NOT appear in REJECT-track output
  (only §1 + Context block).
- REJECT-A/B/C grade table copied verbatim (after verification) from
  `.claude/skills/review-checklist/SKILL.md:83-87`.

## Edit 3 — Reflex map in §12 Likely reviewers — APPLIED

Expanded the `Likely reviewers?` bullet from one line to a 7-anchor
reflex map. Anchors verified against `knowledge/personas/` directory
contents (tom-lane.md, andres-freund.md, noah-misch.md, michael-paquier.md,
peter-eisentraut.md, amit-kapila.md, masahiko-sawada.md, david-rowley.md,
richard-guo.md, melanie-plageman.md, peter-geoghegan.md all confirmed
present).

## Edit 4 — Cross-link §3 → §8a — APPLIED (merged into Edit 1)

Folded into the "Pin contract reminder" paragraph at §3. Names §8a by
section number, explains it as the plan-finalization gate.

## Edit 5 — `source/<path>:<line>` cite exemplar in §3 — APPLIED (merged into Edit 1)

Folded into the §3 description as an example row inside the
"One-sentence summary" bullet. Uses lockfuncs.c:624 as the exemplar
(verified by code: `pg_advisory_lock(int8)` comment is at
source/src/backend/utils/adt/lockfuncs.c:624).

## Edit 6 — Silent-drop in Forbidden in Phase 2 — APPLIED

Added a fourth forbidden-bullet to the "Forbidden in Phase 2" list
explicitly naming the silent-scenario-drop failure mode. Echoes the
ADD-only rule that Step 0 + the new §3 reminder paragraph already
state — redundant by design, since the failure mode is the highest-
value one to prevent.

## Source-value verifications performed

Before applying, the following claims were verified against source:

- `source/src/backend/utils/adt/lockfuncs.c:624` — `pg_advisory_lock(int8)`
  comment present (verified by grep).
- `knowledge/personas/` directory has 26 persona files including all
  7 anchors named in Edit 3 (verified by `ls`).
- REJECT-A/B/C grade rubric at
  `.claude/skills/review-checklist/SKILL.md:83-87` matches the table
  copied into Edit 2 (verified by Read).
- `add-new-builtin-function` scenario at `knowledge/scenarios/` has
  `last_verified_commit: e18b0cb7344` (still current per worktree HEAD).
- `add-new-sql-keyword` scenario has 16 checklist rows, 6 marked
  NOT edited or "NOT edited — RUN" (verified by Read).

All values used in the edits match source exactly.
