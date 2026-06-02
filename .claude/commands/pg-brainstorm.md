---
description: Phase 1 of the PG planner — open-ended exploration of an idea before any heavy planning. Usage: /pg-brainstorm <natural-language idea> [--slug=<short_name>]
---

# pg-brainstorm

Thin wrapper around the `pg-feature-brainstorm` skill. Takes a free-form
description of a PG feature idea and produces
`planning/<slug>/brainstorm.md` — a short sketch that frames the
problem, names 2-3 candidate approaches, and surfaces decisions for
the user.

This is Phase 1 of the three-phase planner:

1. **`/pg-brainstorm`** (this command) — explore the design space.
2. `/pg-plan <slug>` — heavy implementation plan.
3. `/pg-implement <slug>` — execute the plan phase-by-phase.

## Arguments

- `$@` — the natural-language idea (e.g. "add server-side variables to
  PostgreSQL").
- Optional `--slug=<name>` — override the auto-derived slug.

## Pre-flight checks

```bash
IDEA="$*"
SLUG_OVERRIDE=""

# Parse --slug=foo out of the arguments if present
for arg in "$@"; do
  case "$arg" in
    --slug=*) SLUG_OVERRIDE="${arg#--slug=}"; IDEA="${IDEA/$arg/}";;
  esac
done

IDEA="$(echo "$IDEA" | xargs)"

if [ -z "$IDEA" ]; then
  echo "Usage: /pg-brainstorm <natural-language idea> [--slug=<short_name>]"
  echo "Example: /pg-brainstorm add server-side variables to PostgreSQL"
  echo "Example: /pg-brainstorm make EXPLAIN show buffer-pin counts --slug=explain_pins"
  exit 1
fi

# Derive slug if not overridden: first 3-4 significant words, snake_case
if [ -z "$SLUG_OVERRIDE" ]; then
  SLUG=$(echo "$IDEA" | tr 'A-Z' 'a-z' | tr -c 'a-z0-9' '_' | tr -s '_' | \
         sed 's/^_//;s/_$//' | cut -d_ -f1-4)
else
  SLUG="$SLUG_OVERRIDE"
fi

mkdir -p planning/"$SLUG"

if [ -f planning/"$SLUG"/brainstorm.md ]; then
  echo "planning/$SLUG/brainstorm.md already exists."
  echo "Run with a different --slug, or remove the existing file first."
  exit 1
fi

echo "Idea: $IDEA"
echo "Slug: $SLUG"
echo "Will write: planning/$SLUG/brainstorm.md"
```

## Method

1. Load the `pg-feature-brainstorm` skill — that file defines the
   procedure, the document template, and the boundaries with Phase 2.

2. Execute its 8-step method:
   - Set up the planning directory (already done by pre-flight).
   - Load minimal corpus (1-3 subsystem docs).
   - Run the triage pass (CommitFest + git log + corpus grep).
   - Sketch 2-3 candidate approaches.
   - Recommend one.
   - List 3-5 DECISION: questions for the user.
   - Write `planning/<slug>/brainstorm.md` (~150-300 lines).
   - End with a hand-off line pointing at `/pg-plan <slug>`.

3. After writing, summarize for the user: which slug, which approach
   recommended, which DECISION: questions need their answer.

## Boundaries

- Don't load per-file `knowledge/files/...` docs. That's Phase 2.
- Don't enumerate catalog or WAL impact. That's Phase 2.
- Don't propose phase-by-phase implementation. That's Phase 2.
- Don't write more than ~300 lines. Long brainstorm = scope creep.

## Expected output

- `planning/<slug>/brainstorm.md` — the sketch.
- One short message to the user with the slug + recommended approach +
  DECISION questions.

## Troubleshooting

- **"planning/<slug>/brainstorm.md already exists"**: pick a different
  slug with `--slug=`, or `git rm` the existing file if it's stale.
- **The idea is too vague to brainstorm**: ask the user one
  clarifying question inline (what problem are they actually trying to
  solve?), then proceed.
- **The idea is already scoped**: skip Phase 1, go straight to
  `/pg-plan <slug>` with the user's approach as the input.
