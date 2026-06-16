---
description: Pull a scenario playbook from knowledge/scenarios/ and emit a starter plan from its file checklist — skip the brainstorm phase when the change-class is already known. Usage: /pg-scenario <slug>
---

# pg-scenario

Skip Phase 1 (brainstorm) for a change-class that already has a
known playbook. Reads `knowledge/scenarios/<slug>.md` directly and
seeds a `planning/<slug>/plan.md` starter from its file checklist.

Use when:

- The user already knows the change-class ("I'm adding a new GUC, no
  brainstorm needed").
- The user explicitly names a scenario slug.
- A `pg-feature-brainstorm` previously named the scenario and the
  user is moving to Phase 2.

Don't use when:

- The change-class is genuinely exploratory (use `/pg-brainstorm`).
- The user names a scenario slug that doesn't exist
  (use `knowledge/scenarios/_index.md` to suggest a real one or
  flag a gap).
- The feature spans 3+ scenarios in unusual combinations
  (composite — go through brainstorm first to scope).

## Argument

`$1` — the scenario slug (must match a file in
`knowledge/scenarios/<slug>.md`). Examples:

- `/pg-scenario add-new-data-type`
- `/pg-scenario add-new-sql-keyword`
- `/pg-scenario add-startup-hook`

If `$1` is empty, list the available scenarios from
`knowledge/scenarios/_index.md` and exit.

## Pre-flight checks

```bash
SLUG="$1"

if [ -z "$SLUG" ]; then
  echo "Usage: /pg-scenario <slug>"
  echo ""
  echo "Available scenarios (one per line):"
  ls knowledge/scenarios/ | grep -v '^_' | grep -v 'README' | sed 's/\.md$//' | sed 's/^/  /'
  echo ""
  echo "See knowledge/scenarios/_index.md for the decision tree."
  exit 1
fi

if [ ! -f "knowledge/scenarios/$SLUG.md" ]; then
  echo "knowledge/scenarios/$SLUG.md does not exist."
  echo ""
  echo "Did you mean one of:"
  ls knowledge/scenarios/ | grep -v '^_' | grep "$(echo "$SLUG" | cut -d- -f1)" | sed 's/\.md$//' | sed 's/^/  /'
  echo ""
  echo "If this change-class has no scenario yet, the planner will"
  echo "flag a gap. Run /pg-brainstorm <idea> to start there."
  exit 1
fi

if [ -f "planning/$SLUG/plan.md" ]; then
  echo "planning/$SLUG/plan.md already exists."
  echo "Either revise it in place, remove it first, or use a different slug."
  exit 1
fi

mkdir -p planning/"$SLUG"
echo "Scenario: $SLUG (knowledge/scenarios/$SLUG.md)"
echo "Will write: planning/$SLUG/plan.md (starter from scenario checklist)"
```

## Method

1. **Read the scenario.** Open `knowledge/scenarios/<slug>.md`. Note:
   - The frontmatter `when_to_use`, `companion_skills`,
     `related_scenarios`, `canonical_commit`, `last_verified_commit`.
   - The full file checklist (§ "File checklist").
   - The suggested phases (§ "Phases").
   - The pitfalls (§ "Pitfalls").

2. **Anchor-drift check.** Compare the scenario's
   `last_verified_commit:` to the current `source/` HEAD
   (`git -C source rev-parse HEAD`). If they differ:
   - Run a fresh grep pass to confirm every file in the checklist
     still exists at its cited path.
   - Note in the plan's §1 intro that the scenario was drift-checked
     against the current anchor.
   - DO NOT bump `last_verified_commit:` in the scenario unless you
     ran the full check.

3. **Load the `pg-feature-plan` skill.** Per its Step 0, the scenario's
   file checklist IS the starting authoritative §3 table.

4. **Skip Step 1-3 of the regular method.** No brainstorm to read; no
   need to inventory the change sites from scratch (the scenario
   already did it).

5. **Run Steps 4-9 of `pg-feature-plan`:**
   - Decide catalog + WAL + lock + memory (§4-§7).
   - Phase the work (§8) — use the scenario's "Phases" section as the
     starting point, refine based on the specific feature.
   - Test surface (§9) — the scenario names the verification
     invocations; refine for this specific feature.
   - Risk surface (§13) — mandatory. Include any scenario pitfalls
     that bite this specific feature.
   - **Cite verification** — every file:line in the plan must be
     greppable against current source.
   - End with hand-off line: `Run /pg-implement <slug> to start phase 1.`

6. **Plan structure deviation from `pg-feature-plan`:** The plan's
   §1 intro names the scenario explicitly. Format:

   ```markdown
   ## What this plan is

   Starter plan generated via `/pg-scenario <slug>` — bypassed Phase 1
   (brainstorm) because the change-class has a known playbook in
   `knowledge/scenarios/<slug>.md`. The scenario's file checklist is
   the authoritative §3 table.

   Anchor: `<short-sha>` (matches scenario's `last_verified_commit:` ✓
   OR drift detected — re-verified against current master).
   ```

## Expected output

- `planning/<slug>/plan.md` — full plan structured per
  `.claude/skills/pg-feature-plan/SKILL.md`, with §3 pinned to the
  scenario's checklist.
- One short message: which scenario was pinned, how many phases,
  any drift warnings, recommended next action (typically
  `/pg-implement <slug>`).

## Boundaries

- This command does NOT write or modify scenarios. To edit a
  scenario, edit `knowledge/scenarios/<slug>.md` directly and bump
  `last_verified_commit:` after re-verifying the checklist.
- This command does NOT replace `/pg-brainstorm` for composite or
  exploratory features — when in doubt, brainstorm first.
- The user reviews + approves the plan before `/pg-implement` runs.
  Don't auto-invoke `/pg-implement`.

## Troubleshooting

- **Scenario doesn't exist**: either the slug is wrong (consult
  `_index.md`) or the change-class is a genuine gap. For a gap, run
  `/pg-brainstorm` first and note the gap in
  `progress/scenarios-coverage.md` under "Gaps surfaced by planner
  runs".
- **Anchor drift, checklist row no longer applies**: edit the
  scenario before writing the plan — don't quietly drop the row from
  the plan and continue.
- **The feature spans multiple scenarios**: list all matching slugs
  inline in this command's invocation (this command takes ONE slug,
  but you can chain: write the plan with the union of two scenarios'
  checklists, and call out the composite in §1). Or fall back to
  `/pg-brainstorm` for proper scoping.

## Cross-references

- `.claude/skills/pg-feature-plan/SKILL.md` — the underlying skill;
  Step 0 is what makes the scenario load-bearing.
- `.claude/skills/pg-feature-brainstorm/SKILL.md` — Phase 1
  alternative; use when the design space is still open.
- `knowledge/scenarios/README.md` — the layer doc.
- `knowledge/scenarios/_index.md` — decision tree to pick a slug.
- `progress/scenarios-coverage.md` — coverage ledger for the
  scenarios layer.
