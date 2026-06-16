# Iteration 2 — edits applied

Applied 6 of 7 edits from `iteration-1/proposed-edits.md` to
`.claude/skills/pg-shadow-implement/SKILL.md`. Edit 7 was folded into
Edit 3 (single rubric block with mutual-exclusivity + tag modifier
together) rather than added as a separate row.

Final `git diff --stat`: **1 file changed, 107 insertions(+), 14
deletions(-)** (verified before finalisation).

## Verification of cited paths against source / repo

- `knowledge/personas/domain-ownership.md` exists; bare
  `domain-ownership.md` does not. [verified-by-code]
- `.claude/commands/pg-shadow.md` exists. [verified-by-code]
- `knowledge/shadow-implementations/README.md` exists. [verified-by-code]
- `knowledge/shadow-implementations/money-fx-exchange/`
  {`spec.md`, `plan.md`, `comparison.md`, `skill-gaps.md`} all exist.
  [verified-by-code]
- `knowledge/shadow-implementations/temp-file-compression/spec.md`
  exists (plan/comparison deferred per SKILL.md). [verified-by-code]
- `pg-feature-brainstorm` SKILL.md:46 writes to
  `planning/<slug>/brainstorm.md`, which the shadow skill's Step 3.1
  parameterises as `planning/shadow-<slug>/brainstorm.md`.
  [verified-by-code, grep 2026-06-16]
- `knowledge/calibration/shadow-implementation-methodology.md` exists
  and houses the canonical recipe. [verified-by-code]

## Edits applied

1. **Edit 1 — Inline comparison.md schema in Step 5.** Replaced the
   "per the template in the methodology doc" hand-wave with a code-
   block skeleton showing frontmatter + Scope match table + Design
   match bullets + File:line accuracy + Missed/Novel concerns +
   Reviewer-reflex match + Verdict. The skill is now self-contained
   at use time.

2. **Edit 2 — Inline skill-gaps.md schema in Step 6.** Added a code-
   block skeleton mirroring the money-fx-exchange/skill-gaps.md shape:
   frontmatter, per-gap section with Where/Symptom/Fix/Owner-skill
   fields, "What this run did NOT surface", and "Recommendation for
   next skill-creator pass" sections. Locks in the shape that the
   first run already followed.

3. **Edit 3 — REJECT-track mutual exclusivity + disambiguating A vs B
   note + (design-only) tag modifier** (combines original Edits 3 and
   7). Replaced the bare `**Scoring rubric:**` heading with a
   paragraph stating: "Pick exactly one grade. The A-F track applies
   when Step 3 produced an implementation; the REJECT-A/B/C track
   applies when Step 2 terminated at the M4 REJECT decision and the
   deliverable was a thread reply, not a patch. The two tracks are
   mutually exclusive (different shadow-output types). Append
   `(design-only)` to any grade when the M1 fallback chain failed."
   Also added a "Disambiguating A vs B" trailing note: "1-2 design
   choices diverge is the B-threshold. Any single design divergence —
   even one that doesn't break an invariant — moves the grade from A
   to B. A is reserved for runs where the only differences are style
   or minor variable naming." The REJECT rows in the table now
   prefix with "(M4 track)" for visual grouping.

4. **Edit 4 — Promote COVER-only / patch-not-fetched rationale into
   Step 2 prose.** Added a follow-on sentence after the existing
   "Do NOT read or fetch the attached `.patch` file yet" bold call:
   "Reading the patch before Step 4 contaminates the calibration
   signal: the shadow loop measures what our planner suite produces
   from the COVER alone, so any patch-derived knowledge poisons the
   diff. If you catch yourself wanting to peek, the answer is no —
   Steps 3-5 will surface the gap explicitly." The rationale is now
   at the read site, not just in the §"Anti-patterns" list.

5. **Edit 5 — M-finding lineage paragraph at Step 2 head.** Added a
   bulleted block enumerating M1-M5 (archive-fetch fallback / posting-
   date context / cite verification / REJECT-as-valid-output /
   thread-engagement classification), cited to
   `knowledge/shadow-implementations/money-fx-exchange/skill-gaps.md`,
   with "Future shadow runs may add M6+ to this lineage" as the
   forward link. A new contributor reading the skill in isolation can
   now decode the M-tags.

6. **Edit 6 — `domain-ownership.md` path fix.** Both occurrences
   updated to `knowledge/personas/domain-ownership.md` (the actual
   path). Stale-cite hygiene.

## Edits NOT applied as separate items

- **Edit 7** — folded into Edit 3 as a single rubric paragraph with
  the `(design-only)` tag modifier built into the mutual-exclusivity
  language. Keeping it as a separate row would have split the
  grade-related guidance unnecessarily.
