---
description: Phase 3 of the PG planner — execute a planning/<slug>/plan.md phase-by-phase with plan-linked commits, per-phase tests, and a running notes log. Enforces .claude/rules/pg-implement-discipline.md. Usage: /pg-implement <slug> [--phase=<N>]
---

# pg-implement

Thin wrapper around the `pg-implement` skill. Takes a planning slug
and walks the plan's phases one at a time, with strict discipline (the
rules in `.claude/rules/pg-implement-discipline.md` apply).

This is **the PG-specific implementer**, distinct from the generic
`/implement` skill. The PG version enforces:

- Plan-linked commits (every commit has a `Plan:` trailer)
- File:line citation discipline
- One phase at a time, with phase-end check before commit
- Per-phase notes log in `planning/<slug>/notes.md`
- Upstream PG commit-message style for `dev/` commits

This is Phase 3 of the three-phase planner:

1. `/pg-brainstorm` — explore.
2. `/pg-plan` — heavy plan.
3. **`/pg-implement`** (this command) — execute.

## Arguments

- `$1` — the slug under `planning/<slug>/`.
- Optional `--phase=<N>` — start at phase N (default: 1 if `notes.md`
  empty, else next pending phase).

## Pre-flight checks

```bash
SLUG=""
START_PHASE=""

for arg in "$@"; do
  case "$arg" in
    --phase=*) START_PHASE="${arg#--phase=}";;
    *) SLUG="$arg";;
  esac
done

if [ -z "$SLUG" ]; then
  echo "Usage: /pg-implement <slug> [--phase=<N>]"
  echo "Available planning slugs with a plan.md:"
  for d in planning/*/; do
    if [ -f "$d/plan.md" ]; then
      echo "  $(basename "$d")"
    fi
  done
  exit 1
fi

PLAN=planning/"$SLUG"/plan.md

if [ ! -f "$PLAN" ]; then
  echo "$PLAN does not exist."
  echo "Run /pg-plan $SLUG first."
  exit 1
fi

NOTES=planning/"$SLUG"/notes.md

if [ -f "$NOTES" ] && [ -z "$START_PHASE" ]; then
  echo "Existing notes: $NOTES"
  echo "Phase history (last 5):"
  grep -E '^## Phase' "$NOTES" | tail -5 | sed 's/^/  /'
  echo "Resuming from next pending phase (pass --phase=N to override)."
fi

if ! git -C dev rev-parse --is-inside-work-tree >/dev/null 2>&1; then
  echo "dev/ is not a git tree. Run /setup-pg first."
  exit 1
fi

DEV_BRANCH=$(git -C dev rev-parse --abbrev-ref HEAD)
EXPECTED_BRANCH="feature_${SLUG}"

if [ "$DEV_BRANCH" != "$EXPECTED_BRANCH" ]; then
  echo "WARNING: dev/ is on branch $DEV_BRANCH, expected $EXPECTED_BRANCH."
  echo "Either checkout $EXPECTED_BRANCH or create it:"
  echo "  (cd dev && git checkout -b $EXPECTED_BRANCH master)"
fi

echo "Slug: $SLUG"
echo "Plan: $PLAN"
echo "Dev branch: $DEV_BRANCH (expected: $EXPECTED_BRANCH)"
```

## Method

1. Read both authoritative files:
   - `.claude/skills/pg-implement/SKILL.md` (the procedure)
   - `.claude/rules/pg-implement-discipline.md` (the binding rules)

2. Read the plan end-to-end. Note especially §3 (Files that change),
   §8 (Phased implementation), §13 (Known risks), §14 (Phase-zero
   validation if present).

3. Read existing `notes.md` if present to know where to resume.

4. Execute the skill's per-phase loop:
   - Pre-phase: spot-check 3-5 file:line cites; load relevant
     subsystem + per-file corpus; confirm dev cluster state.
   - Edit: make the phase's 5-10 edits, recording each in `notes.md`.
   - Phase-end check: run the test scope per the plan's phase spec.
   - Per-phase commit: stage + commit with the plan-linked message
     format (upstream PG style — NOT meta style).
   - Phase-end log: append the structured section to `notes.md`.
   - Confirm with user + ask whether to continue or pause.

5. After the last phase: end-of-implementation gate (full test suite,
   commit chain verification, optionally hand to `patch-submission`).

6. End-of-session: invoke `memory-keeping` to update
   `progress/STATE.md` with the slug + status.

## Boundaries

- **One phase at a time.** Strict (R3 in rules).
- **Don't auto-continue to the next phase** without confirming with
  the user — phases are natural pause points.
- **Don't commit in `postgres-claude/`** during implementation —
  notes.md updates are uncommitted until the end (or until the user
  asks). Code commits go in `dev/` only.
- **Don't expand scope** — if a phase reveals work not in the plan,
  escalate per R7 in the rules.

## Expected output

Per phase:
- New commit on `dev/feature_<slug>` with the plan-linked message
  format.
- Updated `planning/<slug>/notes.md` with a new "## Phase N" section.
- One summary message to the user with: phase status, test result,
  commit SHA, and a question about whether to continue.

At end of implementation:
- N commits on `dev/feature_<slug>` for N phases.
- Complete `planning/<slug>/notes.md` with all phases logged.
- Updated `progress/STATE.md` via `memory-keeping`.
- Optionally: hand-off to `patch-submission`.

## Troubleshooting

- **"$PLAN does not exist"**: run `/pg-plan <slug>` first.
- **"dev/ is on branch X, expected feature_<slug>"**: either
  checkout the existing branch, or (more often) create it from a
  clean master + a known anchor commit.
- **Phase-end check fails for reasons not in §13**: don't push through
  — escalate per the rules (R4 + R7). Either fix in this phase, or
  update the plan + re-run /pg-plan to capture the new risk.
- **File:line citation drift > 10%**: the plan is stale.
  STOP — re-run `/pg-plan <slug>` against current master to refresh
  before continuing (R2).
- **Build breakage mid-phase**: use the dev-loop:
  `cd dev/build-debug && ninja install 2>&1 | tail -20` to see errors;
  fix; rebuild. Don't commit broken state.

## Cross-references

- `.claude/skills/pg-implement/SKILL.md` — the procedure.
- `.claude/rules/pg-implement-discipline.md` — the binding rules.
- `.claude/skills/commit-message-style/SKILL.md` — upstream PG style
  used for every per-phase commit.
- `.claude/skills/pg-feature-plan/SKILL.md` — the plan template this
  command reads.
- `.claude/skills/review-checklist/SKILL.md` — invoked at end-of-impl
  if going upstream.
- `.claude/skills/memory-keeping/SKILL.md` — invoked at end-of-session.
