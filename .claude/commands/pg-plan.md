---
description: Phase 2 of the PG planner — heavy, citation-rich implementation plan for a PG feature whose design space has been narrowed (typically by /pg-brainstorm). Usage: /pg-plan <slug>
---

# pg-plan

Thin wrapper around the `pg-feature-plan` skill. Takes a planning slug
(from `/pg-brainstorm`) and produces `planning/<slug>/plan.md` — a
plan-mode plan with file:line cites ready to hand to `/pg-implement`.

This is Phase 2 of the three-phase planner:

1. `/pg-brainstorm` — explore the design space.
2. **`/pg-plan`** (this command) — heavy implementation plan.
3. `/pg-implement <slug>` — execute the plan phase-by-phase.

## Argument

`$1` — the slug under `planning/<slug>/`. Examples:

- `/pg-plan server_side_vars`
- `/pg-plan explain_pins`

## Pre-flight checks

```bash
SLUG="$1"

if [ -z "$SLUG" ]; then
  echo "Usage: /pg-plan <slug>"
  echo "Available planning slugs:"
  ls planning/ 2>/dev/null | sed 's/^/  /'
  exit 1
fi

if [ ! -d planning/"$SLUG" ]; then
  echo "planning/$SLUG/ does not exist."
  echo "Run /pg-brainstorm first to create it, or check the slug name."
  exit 1
fi

BRAINSTORM=planning/"$SLUG"/brainstorm.md

if [ -f "$BRAINSTORM" ]; then
  echo "Reading existing brainstorm: $BRAINSTORM"
else
  echo "WARNING: no brainstorm.md in planning/$SLUG/."
  echo "Phase 1 was skipped — the plan must capture design-space"
  echo "exploration that brainstorm would normally do."
fi

if [ -f planning/"$SLUG"/plan.md ]; then
  echo "planning/$SLUG/plan.md already exists."
  echo "Either revise it in place, remove it first, or use a different slug."
  exit 1
fi

echo "Slug: $SLUG"
echo "Will write: planning/$SLUG/plan.md"
```

## Method

1. Load the `pg-feature-plan` skill — that file defines the document
   template (14 required sections), the discipline rules, and the
   boundaries with Phase 1.

2. If `brainstorm.md` exists, read it end-to-end. The picked approach
   + answered DECISION questions are your constraints. If the brainstorm
   left DECISION questions unanswered, ask the user inline before
   continuing.

3. If no brainstorm, accept the user's free-form description of the
   picked approach. Note in §1 of the plan that Phase 1 was skipped.

4. Execute the skill's 9-step method:
   - Re-read brainstorm + decisions.
   - Load corpus deeply (subsystem docs + per-file docs + actual
     source if needed).
   - Inventory the change sites via targeted greps.
   - Decide catalog + WAL + lock + memory BEFORE phasing.
   - Phase the work (3-6 phases).
   - Test surface in §9 references the phase-end checks in §8.
   - Risk surface (§13) is mandatory.
   - Validate by spot-checking 3-5 file:line citations.
   - End with hand-off line pointing at `/pg-implement <slug>`.

5. After writing, summarize for the user: which approach, how many
   phases, which §13 risks are highest severity, and the recommended
   next action (typically `/pg-implement <slug>`).

## Boundaries

- The plan must be implementable as-is. "We'll figure it out during
  implementation" for any of §3-§10 is forbidden — decide here or move
  to §13 as a tracked open question.
- File:line cites without verification are forbidden — every cite
  must be greppable against current source.
- Don't auto-invoke `/pg-implement`. The user reviews + approves the
  plan first.

## Expected output

- `planning/<slug>/plan.md` — the heavy plan, structured per the
  `pg-feature-plan` skill's 14 required sections.
- One short message to the user summarizing the plan + highest-risk
  items + the next step.

## Troubleshooting

- **"planning/<slug>/ does not exist"**: run `/pg-brainstorm` first,
  or create the directory + a stub `brainstorm.md` manually if Phase 1
  is genuinely not needed.
- **Plan drift > 10% during writing**: the corpus is stale at the
  anchor commit. Either: (a) update the affected per-file docs first
  (run `pg-corpus-maintainer` cloud routine or do it interactively),
  or (b) re-anchor the plan against current master via `git log` and
  accept the drift inline as §13 risks.
- **Plan is becoming a 3000-line monster**: split the feature. Take
  the smallest deliverable that can land as one CF entry, plan that,
  and treat the rest as follow-ups.
