---
description: Phase E shadow-implementation run for the pg-claude calibration loop. Usage: /pg-shadow <thread-url> [--slug=<short_name>] [--design-only]
---

# pg-shadow

Thin wrapper around the `pg-shadow-implement` skill. Takes a
pgsql-hackers thread URL, runs the planner suite against the COVER
(NOT the patch), fetches the actual patch only after our plan /
implementation is complete, scores the gap, and produces calibration
data under `knowledge/shadow-implementations/<slug>/`.

## Arguments

- `$1` — thread URL (required).
  - Either the COVER message URL:
    `https://www.postgresql.org/message-id/<msg-id>`
  - Or the flat-view URL:
    `https://www.postgresql.org/message-id/flat/<msg-id>`
- `--slug=<name>` — override the auto-derived slug.
- `--design-only` — skip Step 3.3-3.5 (no `dev/` branch); produce
  spec + plan + design-level comparison only. Default for runs 1-3
  of Phase E.

## Pre-flight checks

```bash
THREAD_URL=""
SLUG_OVERRIDE=""
DESIGN_ONLY=0

for arg in "$@"; do
  case "$arg" in
    --slug=*) SLUG_OVERRIDE="${arg#--slug=}";;
    --design-only) DESIGN_ONLY=1;;
    https://www.postgresql.org/*|https://postgr.es/*) THREAD_URL="$arg";;
    *)
      echo "Unrecognized arg: $arg"
      echo "Usage: /pg-shadow <thread-url> [--slug=<name>] [--design-only]"
      exit 1
      ;;
  esac
done

if [ -z "$THREAD_URL" ]; then
  echo "Usage: /pg-shadow <thread-url> [--slug=<name>] [--design-only]"
  echo "Example: /pg-shadow https://www.postgresql.org/message-id/CA..."
  echo "         /pg-shadow https://postgr.es/m/<id> --slug=my_feature --design-only"
  exit 1
fi

# Derive slug from URL message-id last segment if not overridden
if [ -z "$SLUG_OVERRIDE" ]; then
  SLUG=$(echo "$THREAD_URL" | sed 's|.*/||' | cut -c1-30 \
         | tr 'A-Z' 'a-z' | tr -c 'a-z0-9' '_' | tr -s '_' \
         | sed 's/^_//;s/_$//')
else
  SLUG="$SLUG_OVERRIDE"
fi

mkdir -p "knowledge/shadow-implementations/$SLUG"

if [ -f "knowledge/shadow-implementations/$SLUG/spec.md" ]; then
  echo "knowledge/shadow-implementations/$SLUG/spec.md already exists."
  echo "Pick a different --slug, or remove the dir to redo this run."
  exit 1
fi

echo "Thread URL:  $THREAD_URL"
echo "Slug:        $SLUG"
echo "Design-only: $DESIGN_ONLY"
echo "Will write:  knowledge/shadow-implementations/$SLUG/{spec,plan,comparison,skill-gaps}.md"
```

## Method

1. Load the `pg-shadow-implement` skill — that file defines the
   procedure, the seven steps, the scoring rubric, and the boundaries
   with the planner suite.

2. Execute its method:
   - **Step 1** — validate the thread fits the candidate criteria.
   - **Step 2** — extract spec from COVER + thread (NOT the patch).
   - **Step 3** — run planner suite against the spec. Stop after
     Step 3.2 (plan produced) if `--design-only`.
   - **Step 4** — fetch the upstream patch (M1 fallback chain on
     503).
   - **Step 5** — diff + score, produce `comparison.md`.
   - **Step 6** — produce `skill-gaps.md`.
   - (Step 7 aggregate happens manually after N runs, not per-run.)

3. After the run, summarize for the user: slug, grade
   (A/B/C/D/F or REJECT-A/B/C), top 3 skill gaps surfaced.

## Boundaries

- Don't read the patch before Step 4. That removes the calibration
  signal.
- Don't move shadow output into `patches/<slug>/` (that's the upstream
  send queue — Phase D, not Phase E).
- Don't apply REJECT-C grade without escalating to the user first.

## Expected output

- `knowledge/shadow-implementations/<slug>/spec.md`
- `knowledge/shadow-implementations/<slug>/plan.md`
- `knowledge/shadow-implementations/<slug>/comparison.md`
- `knowledge/shadow-implementations/<slug>/skill-gaps.md`
- (Optional, non-design-only) `dev/shadow-<slug>-ours` +
  `dev/shadow-<slug>-upstream` branches.
- One short message to the user with slug + grade + top gaps.

## Troubleshooting

- **"already exists"**: pick a different `--slug`, or `rm -rf` the
  existing dir if it's stale.
- **M1 archive 503** on patch fetch: per the methodology doc, fall
  back through gitweb mirror → CommitFest patch-set URL → 3-retry
  archive. If all fail, produce design-level-only comparison.md.
- **Thread doesn't fit candidate criteria**: stop, tell the user
  why. Don't force a shadow run against a multi-thread series or
  an already-committed patch.
- **Spec extraction reveals a REJECT-track candidate** (April-1,
  contested, foreclosed INV): mark `shadow-run-status: REJECT-A`
  (or B) in spec.md frontmatter, skip Steps 3-5, write
  comparison.md as a thread-reply draft per `review-checklist`
  Phase 0 REJECT track.

## Phase E status check

`knowledge/shadow-implementations/README.md` is the index of runs.
Current state at this command's introduction:

- Run 1 (money-fx-exchange): REJECT-A, surfaced M1-M5.
- Run 2 (temp-file-compression): spec extracted, plan + comparison
  deferred to next session.
- Run 3+: as scheduled.

After 3-5 runs, the aggregate gap-catalog is the natural next
deliverable.
