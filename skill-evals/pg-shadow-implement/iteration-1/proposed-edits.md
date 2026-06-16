# Proposed edits — iteration 1 (NOT applied)

## Summary of gaps found in grading

The skill covered nearly every assertion in the with-skill answers (29/29).
Baseline scored 11/29 — strong lift (~62pp). The skill is in good shape but
several improvements would harden it against regressions and clarify
known-subjective edges:

1. The grade rubric's A-vs-B-vs-C boundary is fuzzy. "1-2 design choices
   diverge" vs "3+ design diffs" is countable but "novel-concern
   divergence" (the A-blocker) overlaps with "design choices diverge."
   A reader can plausibly grade the same run A or B.
2. The REJECT track is presented as a parallel rubric row but the
   mutual-exclusivity with A-F isn't stated.
3. The `(design-only)` tag mentioned in the anti-patterns section isn't
   wired into the rubric table — readers don't know how to formally tag a
   grade when M1 fallback failed.
4. The COVER-only / patch-not-fetched discipline is in the anti-patterns
   list but isn't visually emphasised inside Step 2 itself. A re-reading
   agent could overlook it.
5. The `comparison.md` and `skill-gaps.md` schemas are referred to ("per
   the template in the methodology doc") but not embedded inline. A user
   running this skill without the methodology doc open would have to
   bounce between files.
6. The cross-reference to `domain-ownership.md` doesn't carry its actual
   path (`knowledge/personas/domain-ownership.md`).

## Concrete edits to consider

### Edit 1 — Inline the comparison.md schema in Step 5

Step 5 currently says "Produce `comparison.md` per the template in the
methodology doc. Sections: …". This is fine but reading the methodology
doc just to learn the schema is a round-trip the skill could spare.

**Add an inline block in Step 5** (right after the existing sentence):

````
The `comparison.md` skeleton:

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
````

Rationale: keeps the skill self-contained at use time; the methodology doc
remains the audit-of-record.

### Edit 2 — Inline the skill-gaps.md schema in Step 6

Currently Step 6 lists three required bullets but doesn't show the file
shape. Add:

````
The `skill-gaps.md` skeleton:

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
**Owner skill**: <pg-feature-plan | pg-implement | etc.>

(repeat per gap; M-ordinals are unique across the whole run, not per gap-class)

## What this run did NOT surface
<corpus gaps that did NOT appear — useful negative signal>

## Recommendation for next skill-creator pass
<bulletted list keyed to skill-creator-brief.md tiers>
```
````

Rationale: same as Edit 1; the money-fx-exchange skill-gaps.md already
follows this shape — formalising it in SKILL.md locks it in.

### Edit 3 — Clarify REJECT-track mutual exclusivity with A-F track

Step 5's rubric table is good but doesn't say REJECT-A/B/C are mutually
exclusive with A/B/C/D/F. A re-reading agent could ask "does REJECT-A
mean A-grade rejection-of-rejection, or a separate axis?"

**Replace** the line directly above the rubric table:

> **Scoring rubric:**

**With**:

> **Scoring rubric.** Pick exactly one grade. The A-F track applies when
> Step 3 produced an implementation; the REJECT-A/B/C track applies when
> Step 2 terminated at the M4 REJECT decision and the deliverable was a
> thread reply, not a patch. The two tracks are mutually exclusive
> (different shadow-output types). Append `(design-only)` to any grade
> when the M1 fallback chain failed and Step 5 ran without an upstream
> patch body.

Rationale: tightens the "grade B if 90% match" vs "grade REJECT-A if we
rejected" boundary the way the methodology doc intended.

### Edit 4 — Move the COVER-only / patch-not-fetched rule into Step 2 prose

The rule exists in the §"Anti-patterns" list ("Don't read the patch
before Step 4"). But Step 2's first sentence is already "Read the COVER
message + any reviewer replies in the thread. **Do NOT read or fetch the
attached `.patch` file yet** — that's Step 4." So this is already
emphasised — but consider promoting it to its own paragraph and bolding
the reasoning so the calibration-signal rationale is visible at the
read site, not just in the anti-patterns list.

**Replace** Step 2's first paragraph:

> Read the COVER message + any reviewer replies in the thread. **Do
> NOT read or fetch the attached `.patch` file yet** — that's Step 4.

**With**:

> Read the COVER message + any reviewer replies in the thread. **Do
> NOT read or fetch the attached `.patch` file yet** — that's Step 4.
> Reading the patch before Step 4 contaminates the calibration signal:
> the shadow loop measures what our planner suite produces from the
> COVER alone, so any patch-derived knowledge poisons the diff. If you
> catch yourself wanting to peek, the answer is no — Steps 3-5 will
> surface the gap explicitly.

Rationale: the discipline is the entire point of the skill (anti-pattern
#1) and a re-reader should hit the rationale at the obvious site.

### Edit 5 — Embed the M-finding lineage in Step 2's spec.md schema

Step 2's spec.md frontmatter and section list mention M2, M4, M5 by tag
but don't say *what* M1-M5 are. A reader who hasn't read the
money-fx-exchange comparison.md wouldn't know.

**Add a short block** at the start of Step 2 (before the spec.md schema):

> The M1-M5 tags throughout Step 2-5 come from the money-fx-exchange
> shadow run (Phase E run 1). They are durable methodology findings:
> M1 = archive-fetch fallback chain; M2 = posting-date / context
> awareness; M3 = pre-emit cite verification; M4 = REJECT as valid
> plan-stage terminal; M5 = thread-engagement classification. Future
> shadow runs may add M6+ to this lineage. Source:
> `knowledge/shadow-implementations/money-fx-exchange/skill-gaps.md`.

Rationale: a new contributor reading the skill in isolation can't decode
the M-tags. The lineage paragraph makes them self-explanatory in 5 lines.

### Edit 6 — Fix the `domain-ownership.md` path

Two cross-references say just `domain-ownership.md` (Step 2 §"Touched
subsystems" and §"Predicted reviewer set"). The actual path is
`knowledge/personas/domain-ownership.md` (verified —
`knowledge/personas/domain-ownership.md` exists; bare `domain-ownership.md`
does not).

**Replace**: `from `domain-ownership.md` lookup` → `from
`knowledge/personas/domain-ownership.md` lookup` (both occurrences).

Rationale: stale-cite hygiene. The path drift would silently break for an
agent following the skill text literally.

### Edit 7 — Add the `(design-only)` tag to the rubric table itself

The rubric table currently doesn't carry the `(design-only)` tag column
or row, even though the anti-pattern bullet says to append it. Either:

(a) Add a "Tag modifiers" sub-row beneath the rubric table:

> **Tag modifier**: append `(design-only)` to any grade when Step 4's
> M1 fallback chain failed and the comparison is design-level-only
> (no upstream patch body). Example: `B (design-only)`.

OR (b) cross-reference the anti-pattern bullet from the rubric prose.

Option (a) is cleaner. Rationale: keeps all grade-related guidance in
one place.

## Non-edits

- The 7-step structure is correct as-is. Don't condense.
- The frontmatter description triggers correctly on all three eval
  prompts. No change needed there.
- The companion_skills list is accurate (verified the 7 listed skills
  all exist in `.claude/skills/`).
- The output volume + cadence section is fine.

## Score delta if all edits applied

Iteration 1 with_skill: 29/29 (1.000) — rubric saturated.
Iteration 2 expected: 29/29 again (no new assertion-failure surface).
Real benefit is **defensive**: edits 1, 2, 3, 4 harden against the
known subjectivity gaps; edits 5, 6, 7 are documentation-cleanup.

## Verification done before applying

- `knowledge/personas/domain-ownership.md` exists; bare
  `domain-ownership.md` does not. [verified-by-code,
  Bash ls 2026-06-16]
- `.claude/commands/pg-shadow.md` exists. [verified-by-code]
- `knowledge/shadow-implementations/README.md` exists. [verified-by-code]
- `knowledge/shadow-implementations/money-fx-exchange/{spec,plan,comparison,skill-gaps}.md`
  all exist. [verified-by-code]
- `knowledge/shadow-implementations/temp-file-compression/spec.md` exists
  (plan/comparison deferred per SKILL.md). [verified-by-code]
- `knowledge/calibration/shadow-implementation-methodology.md` exists
  and houses the canonical recipe. [verified-by-code]
- `pg-feature-brainstorm` skill writes to `planning/<slug>/brainstorm.md`
  per its own SKILL.md:46 — confirming the shadow-slug pattern
  `planning/shadow-<slug>/brainstorm.md` referenced in Step 3.1.
  [verified-by-code, grep 2026-06-16]
