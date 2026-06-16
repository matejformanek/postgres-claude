# pg-feature-brainstorm — iteration 1 summary

**Skill:** `.claude/skills/pg-feature-brainstorm/SKILL.md`
**Methodology:** single-context heavy (per `skill-evals/SUMMARY.md`).
**Date:** 2026-06-16.

## Eval set

Three realistic prompts probing different facets of Phase 1 brainstorming:

1. **Half-formed idea probe** — "rough idea: row-level TTL". Forces the
   agent to name autovacuum / heap-AM, sketch >=2 distinct approaches
   with Pros/Cons/Scope, surface DECISION:s.
2. **Subsystem-naming probe** — "online rewind to LSN X without
   restart". Forces naming WAL / recovery / replication / buffer pool,
   recognizing pg_rewind + PITR as prior art.
3. **Has-this-been-tried trap probe** — "plpgsql_check as core". Tests
   whether the agent recognizes `plpgsql_check` (Pavel Stěhule's
   extension) already exists in the wild and reframes the brainstorm
   accordingly rather than designing from scratch.

11 assertions per eval × 3 evals = 33 total.

## Scores

| Condition | Pass | Total | Rate |
|---|---|---|---|
| with_skill | 33 | 33 | 1.000 |
| baseline | 14 | 33 | 0.424 |

**Lift: +0.576 (≈+58pp).** In line with cohort average (mean iter-1
with_skill: 98%; mean iter-1 baseline: 49%; mean lift: +49pp).

## Where the skill won over baseline (high-confidence)

- 8-section structure (Problem → Why → Subsystems → Has-this-been-tried
  → Approaches[Pros/Cons/Scope] → Recommend → DECISIONs → NOT-figured-out).
  Baseline never reproduces all 8.
- Scenarios-layer consultation. Naming candidate scenarios from
  `knowledge/scenarios/_index.md` is impossible for baseline.
- Subsystem-doc names (`access-heap.md` not just "heap").
- DECISION: framing (specific tradeoffs vs vague "scope MVP vs full").

## Where baseline kept up

Eval 2 and Eval 3 had several assertions that baseline passed — the
closer the brainstorm is to a well-trodden topic (PITR / plpgsql_check),
the smaller the lift. Matches the cohort pattern: "baseline lift
correlates with skill specificity".

## Proposed edits (7 total — see proposed-edits.md)

1. Fix CommitFest URL in §Method step 3 — current `<CF#>` placeholder
   is broken; replace with `?text=<keyword>`. **Hard bug fix.**
2. Add "out-of-tree extension that already does this" as an explicit
   prior-art category in §4.
3. Add a "what makes approaches genuinely distinct" heuristic to
   §Method step 4.
4. Add an Anti-patterns section matching the shape used in sibling skills.
5. Add 3 worked DECISION: examples to §Output point 7.
6. Surface the composite-scenarios pattern from `_index.md` in §4.
7. (Optional) Name the "have-you-tried-the-extension" DECISION: as a
   named pattern that comes first when applicable.

## What the iteration did NOT measure

- Creativity of approach 2 vs approach 3.
- DECISION: quality — rubric counts DECISIONs but doesn't grade whether
  they're high-leverage.
- Real-world triage — none of the evals actually ran WebFetch against
  commitfest.postgresql.org. Skill's triage procedure is graded by
  intent, not by fetched-result quality.
- Whether the agent gracefully RESISTS the brainstorm being a brainstorm
  (recognizes "this isn't a brainstorm, you've picked an approach").

## Verdict (iter-1)

Skill is strong as-is — 100% with_skill against a fair rubric. Edits
are defensive (one URL-bug fix + six structural hardenings). Apply
all seven in iter-2.
