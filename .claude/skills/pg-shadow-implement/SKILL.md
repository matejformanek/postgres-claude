---
name: pg-shadow-implement
description: Shadow-implement a pgsql-hackers thread to calibrate the pg-claude planner suite — read the COVER + discussion only (NOT the attached patch), produce a spec, run pg-feature-brainstorm / pg-feature-plan / pg-implement as-if the user asked for the feature, then fetch the upstream patch, diff against ours, score the gap, and emit comparison.md + skill-gaps.md. This is the "Phase E" calibration loop. Use when the user invokes `/pg-shadow <thread-url>`, says "shadow-implement that thread", "run Phase E against <thread>", "run a shadow against this hackers thread", or names a pgsql-hackers thread + asks how our planner would handle it. Do NOT trigger for real upstream patches we plan to send (use `pg-feature-plan` + `pg-implement` directly), for already-committed threads (re-implementing landed code is meaningless), or for non-PG calibration.
when_to_load: Run a Phase E shadow-implementation against a pgsql-hackers thread; produce calibration data for the planner suite; aggregate to the implementation-gap catalog after 3-5 runs.
companion_skills:
  - pg-feature-brainstorm
  - pg-feature-plan
  - pg-implement
  - pg-patch-review
  - review-checklist
  - memory-keeping
  - meta-commit-style
---

# pg-shadow-implement — Phase E shadow-implementation runner

This skill operationalizes
`knowledge/calibration/shadow-implementation-methodology.md` as a
runnable procedure. Each run produces calibration data about the
planner suite's implementation accuracy, NOT a patch we plan to send
upstream.

The pairing:
- **Phase C** calibrated review (`pg-patch-review` / `review-checklist`).
- **Phase E** (this skill) calibrates implementation
  (`pg-feature-plan` / `pg-implement`).

## When to use vs not

| Situation | Use |
|---|---|
| Active pgsql-hackers thread with COVER + attached patch + clear scope | **this skill** |
| Already-committed patch (we'd be re-implementing) | neither — useless |
| Thread we plan to send patches against | `pg-feature-plan` directly (no shadow) |
| Multi-thread series where the COVER doesn't fully specify scope | neither — too much guessing |
| Touched subsystem isn't documented in our corpus | neither — guessing not calibrating |

## Inputs

- **Thread URL** (required) — a `https://www.postgresql.org/message-id/...`
  link to the thread's COVER message, or the `flat` view URL.
- **Slug** (optional) — short kebab-case name for the run directory
  (auto-derived from the thread subject if omitted).

## Output

Per run, under `knowledge/shadow-implementations/<slug>/`:

- `spec.md` (~50-200 LOC) — COVER extraction, context probe,
  engagement classification.
- `plan.md` (~200 LOC) — produced by `pg-feature-plan`.
- `notes.md` (~100 LOC) — produced by `pg-implement` if the run
  reaches Step 3 implementation.
- `comparison.md` (~150 LOC) — diff vs upstream patch.
- `skill-gaps.md` (~50 LOC) — methodology / skill improvements
  surfaced.

Plus (when implementation is attempted): a `dev/` branch
`shadow-<slug>-ours` with our patch, and `shadow-<slug>-upstream`
with theirs.

After every 3-5 runs:
`knowledge/shadow-implementations/gap-catalog.md` — the
implementation-side counterpart to Phase C's gap-catalog.

## Method — seven steps

### Step 1 — Pick / validate the target

1. Confirm the thread matches the candidate criteria from
   `shadow-implementation-methodology.md` §"Source of features":
   subject prefix (`[PATCH]`, `Proposal:`, `PoC:`, `RFC:`, etc.);
   one COVER; at least one attached patch; not yet committed.
2. If the thread doesn't fit (already merged, no patch, multi-thread
   series with unclear scope), **stop and report** — don't force.

### Step 2 — Spec extraction (COVER only, NOT the patch)

Read the COVER message + any reviewer replies in the thread. **Do
NOT read or fetch the attached `.patch` file yet** — that's Step 4.
Reading the patch before Step 4 contaminates the calibration signal:
the shadow loop measures what our planner suite produces from the
COVER alone, so any patch-derived knowledge poisons the diff. If you
catch yourself wanting to peek, the answer is no — Steps 3-5 will
surface the gap explicitly.

**M-finding lineage.** The `M1` … `M5` tags throughout Step 2-5 come
from the money-fx-exchange shadow run (Phase E run 1), recorded in
`knowledge/shadow-implementations/money-fx-exchange/skill-gaps.md`.
They are durable methodology findings:

- **M1** — archive-fetch fallback chain (Step 4).
- **M2** — posting-date / context-awareness pre-step.
- **M3** — pre-emit file:line cite verification (consumed by
  `pg-feature-plan`).
- **M4** — REJECT as valid plan-stage terminal output.
- **M5** — thread-engagement classification (`unengaged` / `acked`
  / `debated` / `contested`).

Future shadow runs may add M6+ to this lineage.

Produce `knowledge/shadow-implementations/<slug>/spec.md` with:

- Frontmatter: `slug`, `thread-url`, `first-message-url`, `author`,
  `captured-at`, `captured-anchor`, `posted-at`,
  `shadow-run-status` (see status enum below).
- **`## Context awareness (M2)`** — per `pg-feature-plan`'s
  Context-awareness pre-step (PR #168 adds this). Date, author
  posture, engagement signal.
- **`## What this does`** — verbatim COVER claim.
- **`## Touched subsystems`** — from
  `knowledge/personas/domain-ownership.md` lookup + inferred from the
  COVER.
- **`## Predicted reviewer set`** — top 5-6 names per
  `knowledge/personas/domain-ownership.md`'s reviewer column for the
  touched subsystem.
- **`## Author's stated claims`** — files / behavior / backpatch /
  tests.
- **`## Open questions raised in thread`** — verbatim reviewer
  asks, classified per the **M5 engagement classification**:
  `unengaged` / `acked` / `debated` / `contested`.
- **`## Phase 0 gates`** — apply `review-checklist` Phase 0
  reflex gates to the COVER.
- **`## REJECT-track decision (M4)`** — if context-awareness or
  engagement classification recommends REJECT, name the grade
  (`REJECT-A` / `REJECT-B`) and stop. The deliverable becomes a
  thread reply per `review-checklist` Phase 0 REJECT track,
  recorded in `comparison.md` instead of a patch.

`shadow-run-status` enum for the frontmatter:

- `SPEC EXTRACTED` — Step 2 done, Step 3 not yet started.
- `PLAN PRODUCED` — Step 3 done.
- `IMPLEMENTATION IN PROGRESS` — Step 3 implementation underway.
- `IMPLEMENTATION DONE` — `dev/` branch landed.
- `COMPARISON DONE` — Step 5 emitted `comparison.md`.
- `GAPS LOGGED` — Step 6 emitted `skill-gaps.md`.
- `REJECT-A` / `REJECT-B` — REJECT verdict; Steps 3-5 skipped.
- `BLOCKED` — methodology M1 archive 503, or external
  dependency missing.

### Step 3 — Shadow implementation

Run the planner suite **as if the user just asked for this feature**:

1. `pg-feature-brainstorm` against the spec → idea-shaping notes
   (`planning/shadow-<slug>/brainstorm.md`).
2. `pg-feature-plan` against the brainstorm → detailed plan
   (`knowledge/shadow-implementations/<slug>/plan.md`, NOT
   `planning/...` — shadow runs live in `knowledge/`).
3. `pg-implement` against the plan → patch on a `dev/` branch
   `shadow-<slug>-ours`, per
   `.claude/rules/pg-implement-discipline.md`.
4. Per-phase checks (regress + iso + TAP scoped to area).
5. Self-review per `pg-patch-review` (5 critics including
   Critic E).

**DO NOT** look at the upstream patch until Step 3 is complete.

**Lighter-weight variant for design-only runs:** if the patch is
small (~50 LOC) or scope is purely additive, stopping after Step 3
plan + Step 4 fetch + Step 5 design-level comparison is acceptable.
Skip Step 3.3-3.5 (no `dev/` branch). Record the choice in
`spec.md`'s `shadow-run-status` field. The first two Phase E runs
(money-fx-exchange, temp-file-compression) ran in design-only mode.

### Step 4 — Ground truth fetch

After our implementation is done:

1. Fetch the latest patch version from the thread:
   `https://www.postgresql.org/message-id/raw/<message-id>` for
   the message text, or the explicit `.patch` attachment URL.
2. **M1 fallback chain** if the fetch fails with 503 / network
   error:
   - Try gitweb mirror via message-id.
   - Try CommitFest patch-set URL if CF# is known.
   - Try archive attachment URL with up to 3 retries.
   - If all fail: proceed with design-level-only comparison and
     log the unavailability in `comparison.md`.
3. Apply to a sibling `dev/` branch `shadow-<slug>-upstream`.
4. Record its commit message + scope + file:line surface.

### Step 5 — Diff + score

Produce `comparison.md`. The skeleton (matches the template in
`shadow-implementation-methodology.md`):

```
---
slug: <slug>
comparison-status: <FULL | DESIGN-LEVEL ONLY (M1 fallback)>
verdict: <grade> (<one-line reason>)
---

## Scope match
| Dimension | Ours | Theirs | Match? |
|---|---|---|---|
| Files touched | <list> | <list> | ✓/✗ |
| LOC | N | M | ✓/✗ within 20% |
| New symbols | <list> | <list> | overlap % |
| Behavior delta | <our claim> | <their claim> | semantic equiv? |

## Design match
- Same partitioning? <Y/N>
- Same data structures / signatures? <Y/N>
- Same invariants honored (INV-* in knowledge/subsystems/)? <Y/N>
- Same hook / extension surface? <Y/N>

## File:line accuracy
- For each file:line cite in our plan: still holds vs upstream? <hit %>

## Missed concerns (theirs raised, ours didn't)
## Novel concerns (ours raised, theirs didn't)
## Reviewer-reflex match
- pg-patch-review Critic E predictions vs actual thread reflexes: diff
## Verdict
- Grade: A / B / C / D / F or REJECT-A / REJECT-B / REJECT-C
- Top 3 skill / corpus gaps surfaced
```

**Scoring rubric.** Pick exactly one grade. The A-F track applies
when Step 3 produced an implementation; the REJECT-A/B/C track
applies when Step 2 terminated at the M4 REJECT decision and the
deliverable was a thread reply, not a patch. The two tracks are
**mutually exclusive** (different shadow-output types). Append
`(design-only)` to any grade when the M1 fallback chain failed and
Step 5 ran without an upstream patch body — e.g. `B (design-only)`,
`REJECT-A (design-only)`.

| Grade | Meaning | Threshold |
|---|---|---|
| **A** | Patch-equivalent within minor style | ≥ 90% file-line overlap, no missed invariants, no novel-concern divergence |
| **B** | Functionally equivalent, design diverges | ≥ 70% overlap, no missed invariants, 1-2 design choices diverge |
| **C** | Same scope, materially different design | 40-70% overlap, no missed invariants, 3+ design diffs |
| **D** | Different scope OR missed invariant | <40% overlap or invariant broken |
| **F** | Wrong direction | wouldn't pass `review-checklist` |
| **REJECT-A** | (M4 track) Identified all critical design problems + proposed correct alternative — equivalent to A on a serious patch |
| **REJECT-B** | (M4 track) Identified most critical problems but missed one major concern |
| **REJECT-C** | (M4 track) Rejected for wrong reasons OR rejected a sound proposal — escalate to user |

**Disambiguating A vs B**: "1-2 design choices diverge" is the
B-threshold. Any single design divergence — even one that doesn't
break an invariant — moves the grade from A to B. A is reserved for
runs where the only differences are style or minor variable naming.

### Step 6 — Skill feedback

For each gap surfaced in `comparison.md`, produce `skill-gaps.md`.
Skeleton (matches money-fx-exchange/skill-gaps.md):

```
---
slug: <slug>
purpose: Gaps surfaced by this shadow run — input to next skill-creator pass
---

# Skill gaps surfaced by <slug> shadow run

## Gap M<N> — <one-line title>
**Where**: <skill or knowledge doc path>
**Symptom**: <what went wrong / would have gone better>
**Fix**: <1-2 sentence proposed edit>
**Owner skill**: <pg-feature-plan | pg-implement | review-checklist | ...>

(repeat per gap; M-ordinals are unique across the whole run lineage,
not per gap-class — extend the M1-M5 series from money-fx-exchange)

## What this run did NOT surface
<corpus / persona / scenario gaps that did NOT appear — useful negative
signal that things are calibrated>

## Recommendation for next skill-creator pass
<bulleted list keyed to skill-creator-brief.md tiers>
```

Each gap entry must name:

- Which skill or knowledge doc would have closed the gap if richer.
- A 1-2 sentence proposed change.
- An `M<N>` ordinal (continues the M1-M5 series from
  money-fx-exchange — do not reset).

### Step 7 — Aggregate (after N runs)

Once 3-5 shadow runs exist, produce
`knowledge/shadow-implementations/gap-catalog.md` — same shape as
`knowledge/calibration/gap-catalog.md` (5-15 actionable items
each with hit-rate across runs + skill driver).

## Anti-patterns (don't do these)

- **Don't read the patch before Step 4.** That's the whole point —
  reading the patch first removes the calibration signal.
- **Don't skip the M2 context-awareness probe.** It's what
  surfaces the April-1 / unserious-thread case (money-fx run 1
  caught a joke proposal).
- **Don't classify `unengaged` engagement as `acked`.** Reply
  count alone is misleading; deadpan replies don't validate
  community endorsement.
- **Don't produce a Step 5 grade without Step 4 fetch.** If M1
  fallback chain fails, the verdict is design-level-only —
  record this in `comparison.md` and tag the grade with
  `(design-only)`.
- **Don't move shadow output into `planning/`.** Shadow runs are
  durable corpus, not WIP planning artifacts. The
  `planning/shadow-<slug>/brainstorm.md` from Step 3 is the only
  exception (the brainstorm skill's hardcoded path).

## Boundaries vs other skills

- **`pg-feature-brainstorm`** — invoked at Step 3.1; produces
  `planning/shadow-<slug>/brainstorm.md`.
- **`pg-feature-plan`** — invoked at Step 3.2; consumes
  the M2/M3/M5-enhanced version from PR #168.
- **`pg-implement`** — invoked at Step 3.3 if the run is
  full-implementation, not design-only.
- **`pg-patch-review`** — invoked at Step 3.5 in `--self` mode
  for the shadow's own self-review; also at Step 5 to predict
  reviewer reflexes.
- **`review-checklist`** — Phase 0 gates applied at Step 2;
  REJECT track applied at the M4 decision point.
- **`memory-keeping`** — session log of the shadow run goes
  through this skill at run end.
- **`meta-commit-style`** — every artifact commits to the meta
  repo via this style.

## Output volume + cadence

Per run: ~600-800 LOC across 5 docs + (optional) a `dev/` branch.
Per-run wall time: 3-4 hours for full implementation; ~1-2 hours
for design-only.

Cadence:
- 1 run per week initially.
- After 3-5 runs: aggregate gap-catalog.
- Once the catalog stabilises: fire when a major thread lands
  (not weekly).

## Cross-references

- `knowledge/calibration/shadow-implementation-methodology.md` — the
  canonical recipe this skill operationalizes. Where they disagree,
  the methodology doc wins (it's the audit-of-record).
- `knowledge/shadow-implementations/README.md` — index of runs.
- `knowledge/shadow-implementations/money-fx-exchange/` — Phase E
  run 1 (REJECT-A; surfaced M1-M5).
- `knowledge/shadow-implementations/temp-file-compression/` — Phase E
  run 2 (spec done; plan/comparison deferred to next session).
- `knowledge/calibration/gap-catalog.md` — Phase C analog the
  aggregate catalog mirrors.
- `.claude/skills/pg-feature-brainstorm/SKILL.md`,
  `.claude/skills/pg-feature-plan/SKILL.md`,
  `.claude/skills/pg-implement/SKILL.md` — the planner suite under
  test.
- `.claude/skills/pg-patch-review/SKILL.md` — Critic E supplies the
  reviewer-reflex predictions Step 5 cross-checks.
- `.claude/skills/review-checklist/SKILL.md` — Phase 0 gates + M4
  REJECT track this skill consumes.
- `.claude/rules/pg-implement-discipline.md` — the rule the planner
  suite obeys; this skill exercises that obedience.
- `.claude/commands/pg-shadow.md` — slash-command wrapper.
- `knowledge/personas/archive-participants.md` — source of candidate
  thread authors.
