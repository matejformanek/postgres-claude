---
slug: money-fx-exchange
comparison-status: DESIGN-LEVEL ONLY (patch body not fetched, archive 503)
verdict: A (correctly rejected — same direction as a real PG reviewer would go)
---

# Shadow vs upstream — comparison

## What this comparison can + can't say

**CAN**: compare the proposed DESIGN (from COVER) against our
plan's response. This is a complete comparison because the
COVER itself states the design clearly and our plan's response is
"reject the design", not "implement it differently".

**CAN'T**: line-by-line comparison of patch code against our patch
code. Two reasons: (1) we deliberately did not produce code,
because the design is wrong (the right output is a reply, not a
patch); (2) the archive returned 503 on the patch attachment URL
even with direct curl.

## Methodology note: this run is partly a meta-test

This is **the first shadow run** in Phase E. The methodology doc
(`shadow-implementation-methodology.md`) assumed every run would
have a real implementation comparison. This run produced a more
useful result: a calibration finding about **the methodology
itself**, plus a clean design-level result.

## Design comparison

### Their proposed design (from COVER)
- Network I/O (libcurl HTTPS to api.frankfurter.app) inside
  `money_out` / `cash_out`
- New GUC `money_source_currency`
- Per-session cache; "future" shared persistent cache
- Hardcoded API URL with "future" multi-URL config

### Our planner's response (from plan.md)
- REJECT the design
- Cite 5 specific reasons (network I/O in type fn, provolatile/
  proparallel cascade, GUC-vs-stored stability, hard external
  dependency in core, type-system-vs-business-logic boundary)
- Propose alternative shape: contrib extension with user-managed
  rate table

### Match against actual reviewer behavior
- **Andreas Karlsson's reply** (the only thread response): deadpan
  "thanks, add to commitfest". **No technical engagement.**
  Our plan's response is substantially MORE substantive than
  what the actual thread surfaced.
- This is an April-Fools post — community pragmatically declined
  to engage at the design level. Our planner not knowing the
  date context engaged seriously, and produced a serious-but-
  correct rejection. That's the right behavior for the calibration.

## Quality of the rejection — scored

| Criterion | Our plan | Score |
|---|---|---|
| Identified design violates type-I/O contract | ✓ (Reason 1) | A |
| Cited correct invariant + file path | ✓ (`source/src/include/fmgr.h`, `source/src/backend/utils/adt/cash.c`) | A |
| Noted `provolatile`/`proparallel` cascade | ✓ (Reason 2) — but small cite-accuracy error: I wrote `'i' (immutable)` for `cash_out` initially; actual is `'s' (stable)` per `source/src/include/catalog/pg_proc.dat:1954`. The point still holds (`'s'` → `'v'` is still a regression). | B (-1 for cite accuracy) |
| Identified GUC-vs-stored stability (DateStyle precedent) | ✓ (Reason 3) | A |
| Flagged external-service dependency in core | ✓ (Reason 4) | A |
| Proposed alternative shape (contrib extension) | ✓ | A |
| Predicted lead reviewer (Tom Lane) correct | ✓ — matches persona `tom-lane.md` "API/ABI back-compatibility" reflex | A |
| Caught the April-Fools context | ✗ — planner output proceeded as if patch were serious | B (-1 for context) |

**Overall grade: A**
(Per the methodology's rubric: "patch-equivalent within minor
style" — except in this case "patch-equivalent" = the correct
rejection. Our plan would result in essentially the same outcome
as a serious-thread review by Tom Lane: the patch dies, the author
is invited to pivot to a contrib extension.)

## What the upstream patch ACTUALLY contains (inferred)

Without the patch body, inferring from the COVER's claims:
- Modified `source/src/backend/utils/adt/cash.c` to add the libcurl
  call in `cash_out`
- New GUC `money_source_currency` registered in
  `source/src/backend/utils/misc/guc_tables.c`
- New per-session cache (likely a `HTAB` in `PortalContext` or
  `CacheMemoryContext`)
- New `Makefile` / `meson.build` addition for libcurl link (or
  reused from the OAuth machinery)
- Inferred size: 15.3 KB patch ≈ 200-400 LOC

We can't validate this inference without the patch body.

## Missed concerns (theirs raised, ours didn't)

None visible from the thread. Andreas's reply raised no technical
points.

## Novel concerns (ours raised, theirs didn't)

All 5 reasons in our plan.md are concerns the public thread didn't
surface (Andreas's reply was professionally deadpan). The April-
Fools context likely explains this — but Reason 1 through 5 are
real concerns that **would** be raised against a serious version
of this patch.

## Phase E methodology findings (feed into next iteration)

### Finding M1 — Archive .patch attachment URLs are unreliable
The Varnish cache returns 503 on attachment-id lookups. Methodology
needs a fallback. Options:
- (a) Try the gitweb mirror via message-id lookup
- (b) Apply patches from CommitFest URLs (which have their own
  patch hosting)
- (c) Have the shadow-run worker retry attachments at intervals
  and fail gracefully (this run did the latter)

Recommend updating the methodology doc to require (a)+(b) chain
before falling back to (c).

### Finding M2 — Date / context awareness is a gap
The planner output is correct on the design but didn't note the
April-1 timestamp. For shadow runs against archive content, the
date context matters: April-1 posts may be jokes, commit-freeze
posts may carry release-stress signals, etc.

**Recommend**: the spec-extraction step's frontmatter capture
includes the `posted-at` date. The plan step should explicitly
reason about whether the date implies special context.

### Finding M3 — Cite-accuracy errors in the planner output
The plan.md initially cited `cash_out` as `provolatile = 'i'`
(immutable); actual is `'s'` (stable). The point still holds
(both forbid the libcurl side-effect), but the cite was wrong.

**Recommend**: the `pg-feature-plan` skill should mandate a final
"verify each file:line cite against `source/...` at the anchor"
sweep before emitting the plan. Phase A's `pg-quality-auditor`
already does this for already-merged docs; adapting that
discipline to fresh plans is a skill-edit candidate for the next
skill-creator pass.

### Finding M4 — "Reject" is a valid plan output
The methodology doc implicitly assumed every shadow run would
produce code. Add to the methodology: a REJECT verdict at the
plan stage is a valid (and sometimes correct) terminal state.
Update `shadow-implementation-methodology.md` Step 3 + Step 5
scoring rubric to handle this.

### Finding M5 — Andreas-style deadpan acknowledgments aren't useful signal
For shadow runs, "thanks, add to commitfest" tells us nothing
about the patch's technical correctness. The methodology's
"Open questions from thread (already raised by their reviewers)"
field should explicitly note when the thread is technically
unengaged and use that as a flag (either: thread was a joke, or
thread is too early, or topic is uncontroversial).

## What this shadow run validated about our backbone

- **`pg-feature-plan` skill produced a correct rejection** with
  cited reasons. Phase E's first run was a defensive shape (anti-
  pattern detection); the skill handled it.
- **Persona docs surfaced the right lead reviewer** (Tom Lane).
- **Phase C calibration patterns generalised**: even though none
  of the 11 catalog items quite matched, the same reflex-driven
  pattern produced 5 specific Reasons in the plan.
- **The corpus had the right cites** for type-I/O contract,
  pg_proc.dat annotations, and `cash.c`. The one cite that was
  WRONG (provolatile initial value) was a model error, not a
  corpus gap.

## What this shadow run flagged about our backbone

Five methodology gaps surfaced (M1-M5 above). These graduate to
`knowledge/shadow-implementations/gap-catalog.md` once we have
3-5 shadow runs and can see patterns. For now, recorded here.

## Cross-references

- `spec.md` — the proposal as captured
- `plan.md` — the planner's rejection
- `skill-gaps.md` — gaps separated for the next skill-creator pass
- `knowledge/calibration/shadow-implementation-methodology.md` —
  methodology under test; will need M1-M5 patches
- `knowledge/calibration/gap-catalog.md` — Phase C catalog (sibling)
