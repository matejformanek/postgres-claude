---
slug: money-fx-exchange
purpose: Gaps surfaced by this shadow run — input to next skill-creator pass
---

# Skill gaps surfaced by money-fx-exchange shadow run

Five methodology findings (M1-M5 in comparison.md) plus zero substantive
skill gaps. The backbone produced a correct verdict (REJECT with 5
specific reasons); the issues are all in the *shadow-implementation
methodology* layer.

## Gap M1 — Patch-attachment fetch is unreliable

**Where**: `knowledge/calibration/shadow-implementation-methodology.md`
Step 4 (Ground truth fetch).

**Symptom**: postgresql.org archive returns 503 on `.patch`
attachment URLs intermittently. Both WebFetch (binary-content
handling) and direct `curl` (Varnish 503) failed.

**Fix in methodology doc**: change Step 4 to:
```
1. Try gitweb mirror lookup via message-id
2. Try CommitFest patch-set URL if CF# is known
3. Try archive attachment URL with up to 3 retries
4. If all fail: proceed with design-level-only comparison and log
   the unavailability in comparison.md
```

**Owner skill**: this is the methodology doc itself, not a separate
skill. Update during next maintenance pass.

## Gap M2 — Date / context awareness

**Where**: `pg-feature-plan` skill (step that consumes the spec)

**Symptom**: thread was 2026-04-01 (April Fools); planner output
proceeded earnestly. Andreas Karlsson's professionally-deadpan
"thanks, add to commitfest" reply is the only public signal that
the community didn't engage technically.

**Fix in skill**: `pg-feature-plan` SKILL.md should explicitly
include a "context-awareness" pre-step that scans:
- Posting date (April-1 → flag for joke check; release-freeze dates
  → flag for late-cycle context)
- Author's prior threads (one-shot vs sustained contributor)
- Thread reply count + technical-engagement signal

**Owner skill**: `pg-feature-plan` (named in
`progress/skill-creator-brief.md` Tier 1 — but originally for
expansion, not context-awareness; add this to that scope).

## Gap M3 — Cite-accuracy verification before emit

**Where**: `pg-feature-plan` skill final step

**Symptom**: plan.md initially cited `cash_out` as
`provolatile='i'` (immutable). Actual is `'s'` (stable) per
`source/src/include/catalog/pg_proc.dat:1954`. The point still
holds (both `'i'` and `'s'` forbid network I/O), but the cite was
wrong.

**Fix in skill**: `pg-feature-plan` should end with a "verify each
file:line cite against `source/...` at the anchor" step. The
`pg-quality-auditor` cloud routine already has this discipline for
merged docs; adapt to fresh plan output.

**Owner skill**: `pg-feature-plan` + reuse logic from
`pg-quality-auditor` recipe. This is a clean integration point.

## Gap M4 — "REJECT" as valid plan output

**Where**: `knowledge/calibration/shadow-implementation-methodology.md`
Step 3 (Shadow implementation), Step 5 (Diff + score)

**Symptom**: Methodology assumed every shadow run would produce
code. This run's correct output is "REJECT — write a thread reply
instead." The 5-grade rubric (A patch-equivalent ↔ F wrong
direction) doesn't directly score "rejected the proposal correctly".

**Fix in methodology doc**: add a sixth grade or a REJECT-track:
```
REJECT-A — Identified all critical design problems, proposed
           correct alternative. Equivalent to A on a serious patch.
REJECT-B — Identified most critical problems but missed one major
           concern.
REJECT-C — Rejected for the wrong reasons OR rejected when the
           proposal was actually sound.
```

**Owner skill**: methodology doc + `pg-patch-review` Critic E
behavior (the critic should explicitly support a "design REJECT"
verdict, not just a "REFINE / GO" verdict).

## Gap M5 — Deadpan thread replies aren't useful signal

**Where**: `pg-feature-plan` spec-extraction step

**Symptom**: spec.md captured Andreas Karlsson's deadpan reply as
"Open questions from thread", but it raised no questions. The
methodology doesn't distinguish:
- Thread unengaged technically (joke / too early / uncontroversial)
- Thread engaged with no objections (community ack)
- Thread actively debated

**Fix in skill**: the spec-extraction step should classify thread-
engagement explicitly: `unengaged / acked / debated / contested`.

**Owner skill**: `pg-feature-plan` (spec-extraction subroutine).

## What this run did NOT surface

**No corpus gaps**. Every cite the planner needed was in the corpus
at the right place. `source/src/include/fmgr.h` for type-I/O
contract, `source/src/backend/utils/adt/cash.c` for the target
function, `source/src/include/catalog/pg_proc.dat:1954` for the
proc annotations, `knowledge/personas/tom-lane.md` for the
predicted reviewer. The backbone was sufficient.

**No persona gaps**. Tom Lane was correctly predicted as lead;
his persona's "API/ABI back-compatibility" bullet drove the
strongest reason in the plan.

**No Phase C catalog item triggered, but the pattern carried over**.
None of the 11 catalog items matched this case exactly (the patch
isn't a security DoS, isn't a binary-format change, etc.). But
the **persona-driven probe shape** that Phase C established
produced 5 specific Reasons — which is the same shape as the
Phase C calibration findings. The methodology generalises across
the review (Phase C) and implementation (Phase E) sides.

## Recommendation for next skill-creator pass

Add to `progress/skill-creator-brief.md` Tier 1:

- **`pg-feature-plan` enhancements**:
  - Context-awareness pre-step (M2)
  - Final cite-verification step (M3) — reuse `pg-quality-auditor`'s
    file:line check
  - Thread-engagement classification (M5)
  - Explicit "REJECT" plan-verdict support (M4)

- **Methodology doc fixes** (no skill change; doc edit):
  - Update Step 4 with archive-fallback chain (M1)
  - Update scoring rubric with REJECT-A/B/C grades (M4)

These fixes graduate to the next skill-creator pass + a
methodology-doc `hf(corpus)` update.

## Aggregate signal (1-run baseline)

After only one run, the implementation-gap catalog has 5 entries —
all in the "methodology improvement" rather than "skill correction"
direction. The skills themselves performed well. Future runs (against
serious threads) will test whether the skill-side is also tight.

Run 1 grade: **A (REJECT-A)** — backbone correctly rejected an
unimplementable proposal with cited reasons; predicted reviewer
correct; corpus cites correct; methodology improvements identified.

## Cross-references

- `comparison.md` — full scoring + grade rationale
- `plan.md` — the planner output being scored
- `spec.md` — input the planner consumed
- `progress/skill-creator-brief.md` — receives M2/M3/M4/M5 edits
- `knowledge/calibration/shadow-implementation-methodology.md` —
  receives M1/M4 edits
