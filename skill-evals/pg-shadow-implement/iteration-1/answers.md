# Iteration 1 — answers (with_skill vs baseline)

## Eval 1 — Outline the shadow-run procedure for a hackers thread URL

### with_skill answer

Procedure follows `pg-shadow-implement` — 7 steps, COVER-only-then-patch
discipline, per-run artifacts under `knowledge/shadow-implementations/<slug>/`.

**Step 1 — Pick / validate the target.** Confirm the thread fits the candidate
criteria in `shadow-implementation-methodology.md` §"Source of features":
`[PATCH]` / `Proposal:` / `PoC:` / `RFC:` prefix; one COVER message; at least
one attached patch; not yet committed; touches a documented subsystem in our
corpus. If it doesn't fit, **stop and report — don't force**. Derive a slug
from the subject.

**Step 2 — Spec extraction (COVER only, NOT the patch).** Read the COVER
message + reviewer replies in the thread. **Do NOT fetch or open the attached
`.patch` file yet** — that's Step 4. Produce
`knowledge/shadow-implementations/<slug>/spec.md` with:
- Frontmatter (`slug`, `thread-url`, `first-message-url`, `author`,
  `captured-at`, `captured-anchor`, `posted-at`, `shadow-run-status`).
- `## Context awareness (M2)` — date, author posture, engagement signal
  (this is what catches April-Fools / unserious threads).
- `## What this does` — verbatim COVER claim.
- `## Touched subsystems` — from `domain-ownership.md`.
- `## Predicted reviewer set` — top 5-6 names from `domain-ownership.md`.
- `## Author's stated claims` — files / behavior / backpatch / tests.
- `## Open questions raised in thread` — classified per M5: `unengaged /
  acked / debated / contested`.
- `## Phase 0 gates` — `review-checklist` Phase 0 reflex gates.
- `## REJECT-track decision (M4)` — if context/engagement classification
  recommends REJECT, stop here (Steps 3-5 skipped, deliverable becomes a
  thread reply recorded in `comparison.md`).

**Step 3 — Shadow implementation.** Run the planner suite **as if the user
just asked for this feature**, without ever opening the patch:
1. `pg-feature-brainstorm` against the spec → `planning/shadow-<slug>/brainstorm.md`.
2. `pg-feature-plan` against the brainstorm →
   `knowledge/shadow-implementations/<slug>/plan.md` (note: shadow plans live
   in `knowledge/`, NOT in `planning/`).
3. `pg-implement` against the plan → patch on a `dev/` branch
   `shadow-<slug>-ours`, per `.claude/rules/pg-implement-discipline.md`
   (one plan, one branch, per-phase commits with `Plan:` trailer).
4. Per-phase checks (regress + iso + TAP scoped to area).
5. Self-review per `pg-patch-review` (5 critics including Critic E).
**Design-only variant**: if the patch is ~50 LOC or purely additive, stop
after the plan + Step 5 design-level comparison (skip 3.3-3.5; no `dev/`
branch). Record the choice in `spec.md`'s `shadow-run-status`. The
money-fx-exchange and temp-file-compression runs both ran in design-only mode.

**Step 4 — Ground truth fetch.** ONLY now do we look at the upstream patch.
Fetch via `https://www.postgresql.org/message-id/raw/<message-id>` or the
explicit `.patch` attachment URL. **M1 fallback chain** if the fetch fails
with 503 / network error: (a) gitweb mirror via message-id, (b) CommitFest
patch-set URL if CF# is known, (c) archive attachment with up to 3 retries,
(d) proceed with design-level-only comparison and log unavailability. Apply
the upstream patch to a sibling branch `shadow-<slug>-upstream`.

**Step 5 — Diff + score.** Produce
`knowledge/shadow-implementations/<slug>/comparison.md` per the methodology
template: Scope match / Design match / File:line accuracy / Missed concerns
(theirs caught, ours didn't) / Novel concerns (ours flagged, theirs didn't) /
Reviewer-reflex match (cross-check vs `pg-patch-review` Critic E
predictions) / Verdict. Apply the **scoring rubric** (A / B / C / D / F
+ REJECT-A / REJECT-B / REJECT-C tracks). REJECT-A means we identified all
critical design problems and proposed correct alternative — equivalent to A
on a serious patch.

**Step 6 — Skill feedback.** Produce `skill-gaps.md` listing each gap
surfaced in the comparison, tagged with the owner skill or knowledge doc
that would have closed the gap, with `M<N>` ordinals for cross-run
reference.

**Step 7 — Aggregate (after N runs).** Once 3-5 shadow runs exist, produce
`knowledge/shadow-implementations/gap-catalog.md` — same shape as
`knowledge/calibration/gap-catalog.md` (5-15 actionable items each with hit
rate across runs + skill driver).

**Output volume per run**: ~600-800 LOC across 5 docs (`spec.md`, `plan.md`,
`notes.md`, `comparison.md`, `skill-gaps.md`) + optional `dev/` branch.
Wall time: 3-4 hours full implementation; 1-2 hours design-only.

**The whole point**: keep the patch unread until Step 4. Reading it first
removes the calibration signal (anti-pattern #1 in the skill).

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

Per-run artifacts: probably a spec extracted from the COVER, a plan, a diff
report, and a notes/gaps file. Keep them in a per-feature directory.
Probably the discipline of NOT reading the patch first is important —
otherwise the diff is contaminated. But I don't remember exact filenames,
the exact step count, or whether there's a formal REJECT track or a slug-
naming convention. I'd guess `comparison.md` and something like `gaps.md`
based on the question framing.

---

## Eval 2 — Grade a shadow run that lands 90% with one MVCC-design diff

### with_skill answer

**Grade: B.** Reasoning from the rubric in `SKILL.md` §"Step 5 — Diff + score":

| Grade | Threshold | This run? |
|---|---|---|
| **A** | ≥ 90% file-line overlap, no missed invariants, **no novel-concern divergence** | Almost — overlap = 90%, no invariant broken, but one design diff |
| **B** | ≥ 70% overlap, no missed invariants, **1-2 design choices diverge** | **Yes — exactly this case** |
| **C** | 40-70% overlap, no missed invariants, 3+ design diffs | No, overlap too high |
| **D** | <40% overlap OR invariant broken | No |
| **F** | Wouldn't pass `review-checklist` | No |

The xmax-equals-self vs xmin-committed pick is **one design choice
divergence**. Both are MVCC-correct (no invariant broken — neither
visibility scheme is wrong, they're just different design picks within
the heap-tuple visibility contract). Scope is the same (90% overlap), so
we're not at C (which requires 3+ diffs or <70% overlap) and not at D
(invariant broken). The A threshold says "no novel-concern divergence" —
a design diff IS a divergence, so A is excluded.

**Sub-track applicability**:
- **REJECT-A / REJECT-B / REJECT-C do NOT apply.** Those are for runs that
  correctly rejected a flawed proposal (REJECT-A = identified all critical
  design problems + proposed correct alternative; REJECT-B = identified
  most but missed one major concern; REJECT-C = rejected for wrong
  reasons). This run did NOT reject — it implemented, and matched 90%.
  The REJECT track is mutually exclusive with the A-F track because the
  shadow output type differs (a thread reply vs a patch).
- **`(design-only)` tag does NOT apply** either — that's the M1 fallback
  marker when the upstream patch couldn't be fetched. This run produced a
  full file-line comparison, so we're scoring on the implementation track.

**Reviewer-reflex match** (which the question notes Critic E predicted
correctly) is a separate field in `comparison.md` §"Reviewer-reflex match"
and supports the grade — it doesn't shift it. A correct Critic E
prediction reinforces "our backbone calibration is good"; a miss there
would NOT downgrade an implementation B because the grade scores
implementation, not reviewer prediction.

**Verdict: B.** Record in `comparison.md` §"Verdict" + flag the MVCC
design diff in §"Novel concerns" if our pick has merit, or §"Missed
concerns" if theirs is clearly better. The single divergence should
graduate to `skill-gaps.md` with an `M<N>` tag if it points at a
knowledge/idiom that `pg-feature-plan` should know.

### baseline answer

Sounds like a strong run — 90% match, no missed invariants, just one
design diff. I'd grade it around an A-minus or B+. The rubric likely
has letter grades A through F with thresholds. If A requires "exactly
matches" then 90% with a diff probably bumps to B. If A allows "minor
style differences" then a single design pick might still be A. I don't
know the exact threshold language. REJECT-A / REJECT-B sound like
sub-grades for design-rejection cases — they don't apply here because
this run produced an implementation, not a rejection. I'd guess: B,
noting the MVCC diff as a design divergence worth flagging in the
comparison doc. The Critic E reviewer-reflex match is good news but
doesn't change the implementation grade.

---

## Eval 3 — Anti-trigger: pg-shadow vs pg-feature-plan + pg-implement for real upstream work

### with_skill answer

**Do NOT invoke `pg-shadow-implement` here.** The skill's own
frontmatter is explicit: "Do NOT trigger for real upstream patches we
plan to send (use `pg-feature-plan` + `pg-implement` directly), for
already-committed threads (re-implementing landed code is meaningless),
or for non-PG calibration."

**What `pg-shadow-implement` IS for**: calibration. The whole point is
the Phase E loop — measure how close our planner suite
(`pg-feature-brainstorm` + `pg-feature-plan` + `pg-implement`) comes to
the actual implementation someone else posted. To make that measurement
honest, the skill enforces:

- **COVER-only read in Step 2** — read only the COVER message + reviewer
  replies, NEVER the attached `.patch` file. (Anti-pattern #1: "Don't
  read the patch before Step 4. That's the whole point — reading the
  patch first removes the calibration signal.")
- **Patch fetch only at Step 4** — after our shadow implementation
  (Step 3) is complete and committed to a `dev/` branch
  `shadow-<slug>-ours`. The upstream patch lands on
  `shadow-<slug>-upstream`. Only then do we diff.
- **Score against ground truth in Step 5** — `comparison.md` with
  Scope / Design / File:line accuracy / Missed concerns / Novel
  concerns / Reviewer-reflex match / Verdict (A/B/C/D/F or REJECT-A/B/C).

**Why that discipline matters for real upstream work**: you'd be working
*against* yourself. The calibration purpose makes you read less of the
thread (skip the patch), produce intentionally-unread-of-upstream output,
then compare. For real upstream-send-ready work, you want the
*opposite*: read everything (including any prior patch versions in the
thread), use all available context, iterate against reviewer feedback,
and produce something that lands cleanly on `master`. The two workflows
have inverted goals.

**What to use instead** for real upstream work:
- `pg-feature-brainstorm` to shape the idea.
- `pg-feature-plan` against the brainstorm + the full thread context
  (no read-order discipline) → `planning/<slug>/plan.md`.
- `pg-implement` against the plan, per
  `.claude/rules/pg-implement-discipline.md` (one plan, one branch,
  per-phase commits with `Plan:` trailer).
- `pg-patch-review --self` for self-review before sending.
- `review-checklist` + `patch-submission` for the final send.

**Other anti-trigger cases** the skill explicitly skips:
- Already-committed threads (re-implementing landed code is
  meaningless).
- Multi-thread series where the COVER doesn't fully specify scope (too
  much guessing — calibration signal is lost).
- Touched subsystem isn't documented in our corpus (guessing not
  calibrating — we'd be measuring our absence-of-knowledge, not our
  skills).
- Non-PG calibration.

In short: `pg-shadow` is a **measurement tool**, not a development tool.
Calling it for real upstream work confuses the two.

### baseline answer

Skipping pg-shadow makes sense here. From the name, "shadow" implies
producing a parallel/alternate version to compare against — that's
useful for calibrating skills but not for actually shipping a patch.
For real upstream work you'd just want to use pg-feature-plan and
pg-implement directly. pg-shadow probably has some discipline like
"don't peek at the upstream patch until later" that would actively
hurt real implementation work where you want all the context you can
get. I'd recommend: skip pg-shadow, go straight to feature-brainstorm
→ feature-plan → implement → patch-review → patch-submission. The
exact wording of the anti-trigger rule and the calibration-vs-
development distinction I'm pattern-matching from the name and general
shape; the actual SKILL.md probably names this more crisply.
