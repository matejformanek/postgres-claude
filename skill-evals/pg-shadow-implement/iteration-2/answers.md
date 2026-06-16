# Iteration 2 — answers (with_skill vs baseline)

Same 3 prompts as iteration 1, rerun against the edited SKILL.md (Edits
1, 2, 3, 4, 5, 6, 7 applied; see `iteration-2/edits-applied.md`).

## Eval 1 — Outline the shadow-run procedure for a hackers thread URL

### with_skill answer

Procedure follows `pg-shadow-implement` — 7 steps, COVER-only-then-patch
discipline, per-run artifacts under `knowledge/shadow-implementations/<slug>/`.

**Step 1 — Pick / validate the target.** Confirm the thread fits the candidate
criteria in `shadow-implementation-methodology.md` §"Source of features":
`[PATCH]` / `Proposal:` / `PoC:` / `RFC:` prefix; one COVER message; at least
one attached patch; not yet committed; touches a documented subsystem. If it
doesn't fit, **stop and report — don't force**. Derive a slug from the subject.

**Step 2 — Spec extraction (COVER only, NOT the patch).** Read the COVER
message + reviewer replies. **Do NOT fetch or open the attached `.patch`
file yet** — that's Step 4. The skill now states the rationale inline:
*reading the patch before Step 4 contaminates the calibration signal; the
shadow loop measures what our planner suite produces from the COVER alone,
so any patch-derived knowledge poisons the diff*. If you catch yourself
wanting to peek, the answer is no — Steps 3-5 surface the gap explicitly.

The M-finding lineage block at the head of Step 2 makes the M-tags
self-explanatory:
- **M1** = archive-fetch fallback chain (Step 4 hardening).
- **M2** = posting-date / context-awareness pre-step.
- **M3** = pre-emit file:line cite verification.
- **M4** = REJECT as valid plan-stage terminal output.
- **M5** = thread-engagement classification (unengaged / acked / debated /
  contested).
Future runs may add M6+.

Produce `knowledge/shadow-implementations/<slug>/spec.md` with:
- Frontmatter (`slug`, `thread-url`, `first-message-url`, `author`,
  `captured-at`, `captured-anchor`, `posted-at`, `shadow-run-status`).
- `## Context awareness (M2)` — date, author posture, engagement signal
  (catches April-Fools / unserious threads).
- `## What this does` — verbatim COVER claim.
- `## Touched subsystems` — from `knowledge/personas/domain-ownership.md`
  (path now correct in skill).
- `## Predicted reviewer set` — top 5-6 names from
  `knowledge/personas/domain-ownership.md`'s reviewer column.
- `## Author's stated claims` — files / behavior / backpatch / tests.
- `## Open questions raised in thread` — classified per M5.
- `## Phase 0 gates` — `review-checklist` Phase 0 reflex gates.
- `## REJECT-track decision (M4)` — if context/engagement recommends
  REJECT, stop here (Steps 3-5 skipped; thread reply recorded in
  `comparison.md`).

**Step 3 — Shadow implementation.** Run the planner suite as-if-the-user
asked, without opening the patch:
1. `pg-feature-brainstorm` → `planning/shadow-<slug>/brainstorm.md`.
2. `pg-feature-plan` → `knowledge/shadow-implementations/<slug>/plan.md`
   (note: shadow plans live in `knowledge/`, NOT in `planning/`).
3. `pg-implement` → `dev/` branch `shadow-<slug>-ours` per
   `.claude/rules/pg-implement-discipline.md`.
4. Per-phase checks (regress + iso + TAP).
5. Self-review per `pg-patch-review` (5 critics).
**Design-only variant**: if patch is ~50 LOC or purely additive, stop after
plan + Step 5 design-level comparison (skip 3.3-3.5; no `dev/` branch).
Record in `spec.md`'s `shadow-run-status`. money-fx-exchange and
temp-file-compression both ran in design-only mode.

**Step 4 — Ground truth fetch.** ONLY now do we look at the upstream patch.
Fetch via `https://www.postgresql.org/message-id/raw/<message-id>` or the
explicit `.patch` URL. M1 fallback chain: (a) gitweb mirror by message-id,
(b) CommitFest patch-set URL if CF# known, (c) archive attachment with up
to 3 retries, (d) proceed design-level-only and log. Apply to a sibling
branch `shadow-<slug>-upstream`.

**Step 5 — Diff + score.** Produce `comparison.md`. The skill now embeds
the schema inline (frontmatter + Scope match table + Design match bullets
+ File:line accuracy + Missed concerns + Novel concerns + Reviewer-reflex
match + Verdict). Pick exactly one grade. Apply the rubric (A / B / C /
D / F + REJECT-A/B/C). The two tracks are **mutually exclusive** (the
A-F track is for implementation outputs; the REJECT track is for M4
terminal rejections — different shadow-output types). Append
`(design-only)` to any grade when the M1 fallback failed.

**Step 6 — Skill feedback.** Produce `skill-gaps.md` (schema embedded
inline in the skill). Each gap names: which skill/doc would have closed
it, a 1-2 sentence proposed change, and an `M<N>` ordinal continuing the
M1-M5 series from money-fx-exchange (do not reset).

**Step 7 — Aggregate (after N runs).** Once 3-5 shadow runs exist,
produce `knowledge/shadow-implementations/gap-catalog.md` — same shape as
`knowledge/calibration/gap-catalog.md`.

**Output volume per run**: ~600-800 LOC across 5 docs + optional `dev/`
branch. Wall time: 3-4 hours full / 1-2 hours design-only.

**The whole point**: keep the patch unread until Step 4 — anti-pattern #1.

### baseline answer

A pgsql-hackers shadow run sounds like: read the thread, design what we'd
do, then look at the actual patch and compare. Roughly:
1. Fetch the thread's COVER message — what's the proposed feature?
2. Outline the design we'd produce (subsystems touched, signatures, tests).
3. Either sketch a patch or fully implement on a branch.
4. Pull the actual upstream patch and diff against ours.
5. Write up what matched, what we missed, where we picked a different
   approach.
6. Note any gaps to feed back into the planning skills.

Per-run artifacts: probably a spec extracted from the COVER, a plan, a
diff report, and a notes/gaps file. Keep them in a per-feature directory.
Probably the discipline of NOT reading the patch first is important —
otherwise the diff is contaminated. But I don't remember exact filenames,
the exact step count, or whether there's a formal REJECT track or a slug-
naming convention.

---

## Eval 2 — Grade a shadow run that lands 90% with one MVCC-design diff

### with_skill answer

**Grade: B.** Reasoning from the rubric in `SKILL.md` Step 5.

The skill now includes the **disambiguating note**: "1-2 design choices
diverge is the B-threshold. Any single design divergence — even one that
doesn't break an invariant — moves the grade from A to B. A is reserved
for runs where the only differences are style or minor variable naming."
That maps this case directly to B without rubric-reading judgment.

| Grade | Threshold | This run? |
|---|---|---|
| **A** | ≥ 90% overlap, no missed invariants, **no novel-concern divergence** (i.e. only style differs) | No — one real design pick differs |
| **B** | ≥ 70% overlap, no missed invariants, 1-2 design diffs | **Exactly this** |
| **C** | 40-70% overlap or 3+ design diffs | No |
| **D** | <40% overlap or invariant broken | No |
| **F** | Wouldn't pass `review-checklist` | No |

**Sub-track applicability**: REJECT-A / REJECT-B / REJECT-C do **not**
apply. The skill is now explicit that the A-F track and REJECT track are
mutually exclusive (different shadow-output types — patch vs thread reply).
This run produced a patch (Step 3 reached implementation), so it scores on
the A-F axis. The `(design-only)` tag also does not apply — that's the M1
fallback marker for unfetchable upstream patches, and the question states
we ran the comparison normally.

**Verdict**: B. Record in `comparison.md` §"Verdict". The MVCC design diff
goes in §"Novel concerns" (if our pick has merit) or §"Missed concerns"
(if theirs is clearly better). The single divergence graduates to
`skill-gaps.md` with the next M-ordinal (M6+) continuing the lineage,
naming the owner skill (likely `pg-feature-plan` for the MVCC visibility-
check idiom). The Critic E reviewer-reflex match is recorded as a
separate field in `comparison.md` §"Reviewer-reflex match" — it reinforces
backbone calibration but doesn't shift the implementation grade.

### baseline answer

Sounds like a strong run — 90% match, no missed invariants, one design
diff. I'd grade around an A-minus or B+. If A requires exact match, then
90% with a diff bumps to B. If A allows "minor style differences" then a
single design pick might still be A. I don't know the exact threshold
language. REJECT-A / REJECT-B sound like sub-grades for design-rejection
cases — they don't apply here because this run produced an implementation,
not a rejection. I'd guess: B, noting the MVCC diff as a design
divergence worth flagging.

---

## Eval 3 — Anti-trigger: pg-shadow vs pg-feature-plan + pg-implement for real upstream work

### with_skill answer

**Do NOT invoke `pg-shadow-implement` here.** The frontmatter is explicit:
"Do NOT trigger for real upstream patches we plan to send (use
`pg-feature-plan` + `pg-implement` directly), for already-committed
threads (re-implementing landed code is meaningless), or for non-PG
calibration."

**What pg-shadow IS for**: calibration. The skill is a **measurement
tool**. Phase E measures how close our planner suite comes to a real
implementer's posted patch. The skill now includes the rationale inline
at Step 2: *the shadow loop measures what our planner suite produces from
the COVER alone, so any patch-derived knowledge poisons the diff*.
The COVER-only / patch-fetch-only-after discipline is what makes the
measurement honest.

For real upstream-send-ready work, you want the **opposite**: read
everything (including any prior patch versions), use all context, iterate
against reviewer feedback, produce something that lands cleanly on
`master`. The workflows have inverted goals.

**What to use instead**:
- `pg-feature-brainstorm` to shape the idea.
- `pg-feature-plan` against the brainstorm + full thread context (no
  read-order discipline) → `planning/<slug>/plan.md`.
- `pg-implement` against the plan, per
  `.claude/rules/pg-implement-discipline.md` (one plan, one branch,
  per-phase commits with `Plan:` trailer).
- `pg-patch-review --self` for self-review before sending.
- `review-checklist` + `patch-submission` for final send.

**Other anti-trigger cases** the skill explicitly skips:
- Already-committed threads (re-implementing landed code is meaningless).
- Multi-thread series where COVER doesn't fully specify scope (too much
  guessing — calibration signal lost).
- Touched subsystem isn't documented in our corpus (we'd be measuring our
  absence-of-knowledge, not our skills).
- Non-PG calibration.

In short: pg-shadow is a measurement tool, not a development tool.

### baseline answer

Skipping pg-shadow makes sense here. From the name, "shadow" implies
producing a parallel/alternate version to compare against — useful for
calibrating skills but not for shipping a patch. For real upstream work
you'd just want pg-feature-plan and pg-implement directly. pg-shadow
probably has some discipline like "don't peek at the upstream patch until
later" that would actively hurt real implementation work. Skip pg-shadow,
go straight to feature-brainstorm → feature-plan → implement →
patch-review → patch-submission.
