# Phase E — shadow-implementation calibration

The implementation-side counterpart to Phase C's patch-review
calibration. **Phase C asked: "what would real PG reviewers say
about a patch?"** Phase E asks: **"what would our skills + corpus
produce when handed a feature proposal — and how does that compare
to what the actual implementer did?"**

## Why this exists

Phase C calibrated the review pipeline (`pg-patch-review` +
`review-checklist`) — produces good output. It does NOT calibrate
the implementation pipeline (`pg-feature-brainstorm` +
`pg-feature-plan` + `pg-implement`). Those skills + the rule file
`pg-implement-discipline.md` are the canonical development workflow
but have not been measured against ground truth.

The shadow-implementation loop is the measurement. By picking active
pgsql-hackers threads where someone is implementing a feature, we
can:

1. Read the **thread + COVER** (not the patch) to extract the
   spec/intent.
2. Use the `pg-feature-plan` + `pg-implement` pipeline to produce
   our own plan + implementation.
3. **Fetch the actual patch they posted**, diff against ours.
4. Score the gap (scope match, design match, file:line accuracy,
   missed concerns, novel concerns we caught they didn't).
5. Feed the gap into the next skill-creator pass.

This is a paper exercise (no upstream sends, no actual PG patches
of our own). The output is **calibration data** about our skills'
implementation accuracy.

## How this differs from Phase C

| Dimension | Phase C | Phase E |
|---|---|---|
| Question | Will our review catch what theirs would? | Will our implementation match theirs? |
| Input | Our staged patch | Their pgsql-hackers thread (COVER only) |
| Ground truth | Predicted personas + reflexes | Their actual posted patch |
| Skills calibrated | `pg-patch-review`, `review-checklist` | `pg-feature-plan`, `pg-implement` |
| Output | Reviewer-reflex gap catalog (11 items) | Implementation-gap catalog (TBD) |
| Cadence | One-time at session of record | Ongoing — re-run as new threads land |

## Source of features

Pgsql-hackers threads matching:

- Subject prefix `[PATCH]`, `Proposal:`, `PoC:`, `RFC:`,
  `[GSoC YYYY]`, `Re: Implement <X>`
- Touches one of the documented subsystems (so the corpus has
  relevant content)
- Has a clear scope (one feature, one cover letter — not a
  multi-thread series)
- Has an attached patch (so ground truth exists)
- Is NOT yet committed (we're predicting their final shape, not
  re-implementing landed code)

From Phase B's archive-mining (April-May 2026 sample), candidate
threads exist in:

| Thread | Author | Subsystem | Reason it's a good candidate |
|---|---|---|---|
| "Sequence Access Methods, round two" | Andrei Lepikhov | access | Clear scope (sequence AM); active series |
| "Implement waiting for wal lsn replay: reloaded" | Xuneng Zhou | access-transam / replication | New mechanism; one cover letter |
| "Bound memory usage during manual slot sync retries" | Xuneng Zhou | replication | Bounded scope |
| "Track last-used timestamp for index usage" | Raghav Mittal | access (index) | Pure-archive author (Phase B Finding B); good test of corpus coverage |
| "Eliminating SPI / SQL from some RI triggers - take 3" | Amit Langote | commands | Multi-take series; we'd want take-3 specifically |
| "POC: enable logical decoding when wal_level = 'replica' without a server restart" | Masahiko Sawada | replication | Substantive — touches WAL + decoding state machine |
| "Proposal: Adding compression of temporary files" | Filip Janus | storage | Pure-archive author; new mechanism |
| "Add fx exchange support to money type" | Joel Jacobson | utils-adt | Self-contained; small scope |

(Candidates re-mined when this skill runs — these are from a
Phase B sample, not a steady source.)

## Per-feature recipe

### Step 1 — Pick a target

1. Browse pgsql-hackers archive at
   `https://www.postgresql.org/list/pgsql-hackers/`. Filter for
   subjects matching the patterns above.
2. Confirm:
   - One COVER letter exists with clear scope.
   - At least one patch attached.
   - **DO NOT read the patch yet.** Read only the COVER + the
     thread discussion.
3. Capture:
   - Thread URL
   - Author + CC list
   - Subject + scope (one paragraph)
   - The "What this does" claim from the COVER
   - The "Files affected" claim (if stated)
   - Any reviewer questions that surfaced before our shadow run

### Step 2 — Spec extraction

Read the COVER + thread (NOT the patch). Produce a
`knowledge/shadow-implementations/<slug>/spec.md`:

```
---
slug: <feature-slug>
thread-url: <archive-url>
author: <name>
captured-at: <YYYY-MM-DD>
captured-anchor: <SHA>
---

# Spec extracted from pgsql-hackers thread

## What this does
<1 paragraph from COVER>

## Touched subsystem(s)
<from our domain-ownership.md lookup>

## Predicted reviewer set (per Phase B + Phase C)
<from domain-ownership.md + relevant personas>

## Author's stated claims
- Files affected: <claim>
- Behavior delta: <claim>
- Backpatch: <claim>
- Test coverage: <claim>

## Open questions from thread (already raised by their reviewers)
- <reviewer-Q1>
- <reviewer-Q2>
...

## Phase 0 gates that apply (per review-checklist Phase 0)
- security@? <yes/no/exemption>
- test-omission? <stated/pre-empted>
- install-script? <applicable/not>
```

### Step 3 — Shadow implementation

Run the planner suite **as if the user just asked for this feature**:

1. `pg-feature-brainstorm` against the spec — produce idea-shaping notes.
2. `pg-feature-plan` against the brainstorm output — produce the
   detailed plan with file:line cites.
3. `pg-implement` against the plan — produce the patch in `dev/`
   per the `pg-implement-discipline.md` rule (one branch, one plan,
   per-phase commits).
4. Run the per-phase checks (regress + iso + TAP scoped to the area).
5. Self-review per `pg-patch-review` (5 critics including Critic E).

Output: branch in `dev/` with our shadow implementation, plus
`knowledge/shadow-implementations/<slug>/plan.md`,
`knowledge/shadow-implementations/<slug>/notes.md`.

**DO NOT** look at the upstream patch until step 3 is complete.

### Step 4 — Ground truth fetch

After our implementation is done:

1. Fetch the actual patch from the thread (latest version):
   `https://www.postgresql.org/message-id/raw/<message-id>` or via
   GitHub-mirror tooling.
2. Apply to a sibling branch in `dev/` (e.g. `shadow-<slug>-upstream`).
3. Get its commit message + scope + file:line surface.

### Step 5 — Diff + score

Produce `knowledge/shadow-implementations/<slug>/comparison.md`:

```
# Shadow vs upstream — comparison

## Scope match
| Dimension | Ours | Theirs | Match? |
|---|---|---|---|
| Files touched | <list> | <list> | ✓/✗ |
| LOC | N | M | ✓/✗ (within 20%) |
| New symbols | <list> | <list> | overlap % |
| Behavior delta | <our claim> | <their claim> | semantic equiv? |

## Design match
- Did we partition the work the same way? <Y/N>
- Did we pick the same data structures / signatures? <Y/N>
- Did we honor the same invariants (per knowledge/subsystems/<x>.md INV-*)? <Y/N>
- Did we route through the same hook / extension surface? <Y/N>

## File:line accuracy
- For each file:line cite in our plan: does the cite still hold in
  the upstream patch's worldview? <hit %>

## Missed concerns (theirs caught, ours didn't)
- ...

## Novel concerns (ours flagged, theirs didn't)
- ...

## Reviewer-reflex match
- Did our pg-patch-review Critic E predict the same reviewer
  reflexes the actual thread surfaced? <list both, diff>

## Verdict
- Implementation quality: A / B / C / D / F
- Top 3 gaps in skills/corpus that this run surfaced
```

### Step 6 — Skill feedback

For each gap surfaced in step 5's comparison, file a brief
`knowledge/shadow-implementations/<slug>/skill-gaps.md` listing
the specific skill or knowledge doc that would have closed the gap
if richer. This becomes the input to the next skill-creator pass.

### Step 7 — Aggregate (after N runs)

Once we have 3-5 shadow runs, produce
`knowledge/shadow-implementations/gap-catalog.md` — the
implementation-side counterpart to Phase C's
`knowledge/calibration/gap-catalog.md`. Same shape: 5-15 actionable
items each with hit rate across runs and skill driver.

## Scoring rubric

| Grade | Meaning | Threshold |
|---|---|---|
| **A** | Patch-equivalent within minor style | ≥ 90% file-line overlap, no missed invariants, no novel-concern divergence |
| **B** | Functionally equivalent, design diverges | ≥ 70% overlap, no missed invariants, 1-2 design choices diverge |
| **C** | Same scope, materially different design | 40-70% overlap, no missed invariants, 3+ design diffs |
| **D** | Different scope OR missed invariant | <40% overlap or invariant broken |
| **F** | Wrong direction | wouldn't pass review-checklist |

A grade of C or worse names specific skill/corpus weaknesses for
the gap catalog. A grade of A or B validates the backbone.

## When NOT to invoke this loop

- Threads that are already committed (we'd be re-implementing landed
  code — meaningless).
- Threads with no actual patch attached (no ground truth).
- Multi-thread series where the COVER doesn't fully specify the
  scope (we'd be guessing).
- Threads whose touched subsystem isn't documented in our corpus
  (we'd be guessing rather than calibrating).

## Output volume

Each shadow run produces:

- `knowledge/shadow-implementations/<slug>/spec.md` (~50 lines)
- `knowledge/shadow-implementations/<slug>/plan.md` (~200 lines —
  produced by `pg-feature-plan`)
- `knowledge/shadow-implementations/<slug>/notes.md` (~100 lines —
  per-phase implementation notes per `pg-implement`)
- `dev/` branch with the patch (volume varies)
- `knowledge/shadow-implementations/<slug>/comparison.md` (~150 lines)
- `knowledge/shadow-implementations/<slug>/skill-gaps.md` (~50 lines)

Per-run wall time: ~3-4 hours.

After 3-5 runs: aggregate gap-catalog (~150 lines).

## Cadence

- Skill-creator pass (your plugin) lands first.
- First shadow run: pick a small / medium target (e.g. Joel
  Jacobson's "Add fx exchange support to money type" or Filip
  Janus's "Adding compression of temporary files").
- Cadence: 1 shadow run per week initially. After 3-5 runs,
  aggregate and assess.
- Once the implementation-gap catalog stabilises, the loop
  graduates to "fire when a major thread lands" rather than
  weekly.

## Where to write the new skill

`.claude/skills/pg-shadow-implement/SKILL.md` — wraps the per-feature
recipe above. The slash command `/pg-shadow <thread-url>` invokes
it.

This skill is part of the next skill-creator pass (per
`progress/skill-creator-brief.md` Tier 3). Until then, the recipe
in this doc IS the methodology.

## Cross-references

- `progress/backbone-audit-2026-06-12.md` — Phase E motivation
- `progress/skill-creator-brief.md` — input to the plugin pass that
  precedes the first shadow run
- `knowledge/calibration/gap-catalog.md` — Phase C analog
- `.claude/skills/pg-feature-brainstorm/SKILL.md`,
  `.claude/skills/pg-feature-plan/SKILL.md`,
  `.claude/skills/pg-implement/SKILL.md` — the planner suite under test
- `.claude/rules/pg-implement-discipline.md` — the rule the suite obeys
- `knowledge/personas/archive-participants.md` — Phase B #5; source of
  candidate-thread authors
