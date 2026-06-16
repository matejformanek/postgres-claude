# Proposed edits — iteration 1 (NOT applied)

## Summary of gaps found in grading

The skill (with its 8-section structure + scenarios-layer integration)
covered every assertion on the with_skill side — 33/33. Baseline scored
14/33 (≈+57pp lift), mostly losing on:

- The 8-section structure itself (no baseline can guess Problem → Why →
  Subsystems → Has-this-been-tried → Approaches-with-Pros-Cons-Scope →
  Recommend → DECISIONs → NOT-figured-out).
- Naming corpus subsystem docs by name.
- The scenarios-layer consultation (specific to this repo, no baseline
  can possibly do it).
- Surfacing 3+ DECISION: questions with non-trivial framing.
- The honesty pattern of `[unverified]` tags rather than confident-
  sounding wrong claims.

The prior `progress/skill-creator-pg-feature-brainstorm.md` note
(2026-06-14) found the DESCRIPTION was already on-pattern (5+ trigger
phrasings, bolded "Use proactively"). My verification: the current
description still has all of that, plus the "even when they don't use
the literal word 'brainstorm'" hedge, plus a strong skip list. The
description doesn't need further work.

**Leverage is in the BODY** — structure, examples, anti-patterns —
which is where my iter-1 saturated rubric still revealed seams:

1. **`<CF#>` placeholder is wrong in §Method step 3.** The current
   URL template `https://commitfest.postgresql.org/<CF#>/?q=<keyword>`
   is broken — CF# is a *current commitfest number* (e.g. `52`), not a
   placeholder, and the `?q=` parameter isn't a documented search. The
   actual cross-CF text search is `?text=<keyword>` at the root, and a
   numbered URL `commitfest.postgresql.org/52/` scopes to that CF's
   open entries only. An agent following this skill literally as
   written will run an unhelpful `WebFetch`.

2. **No "extension already exists" reframe is explicit in the skill.**
   Eval 3 (`plpgsql_check`) hinged on the agent NOT outlining the
   feature from scratch — instead recognizing prior art reframes the
   brainstorm into "upstream / make-easier / move-to-contrib".
   The skill's §"Has this been tried?" mentions corpus + git log + CF
   but does not call out **"out-of-tree extension that already does
   most of this"** as one of the four prior-art categories. This is the
   single most-common gotcha for PG brainstorms.

3. **"Genuinely distinct" approaches has no guidance.** §Method step 4
   says "Keep them genuinely distinct (not three flavors of the same)"
   but doesn't say how to recognize a flavor-of-same vs a distinct
   approach. A simple heuristic ("approaches differ on at least one of:
   which subsystem owns the change, whether it adds new invariants,
   whether it's user-visible at SQL or at config level") would help.

4. **No "Anti-patterns" section.** Other skills in this repo (e.g.
   `pg-implement`) list explicit anti-patterns. For brainstorming the
   common ones are: "designed a plan instead of a brainstorm",
   "exhaustive 5-approach list (resist the urge to be exhaustive
   ALREADY in §Output but the skill should also explicitly forbid it)",
   "no recommendation = bland brainstorm", "DECISION: list that's
   really an excuse to defer thinking" (i.e. low-leverage DECISIONs).

5. **No worked DECISION: examples.** The skill says DECISIONs must be
   specific and gives ONE good/bad example
   ("Should the MVP support DEFAULT clauses or only NOT NULL?" vs
   "scope (MVP vs full)"). Three more examples covering the
   *different categories* of high-leverage decision (does-this-already-
   exist, semantics-tradeoff, contrib-vs-core, target-version) would
   make the bar concrete.

6. **Composite-features pattern from `_index.md` is not surfaced in
   SKILL.md.** The scenarios index explicitly documents that "a
   real-world feature often spans 2-3 scenarios" with worked examples.
   The skill's §4 cites the index but doesn't tell the agent: "if your
   approach maps to 2-3 scenarios, name all of them — Phase 2 will
   compose the §3 file checklist." All three of my eval brainstorms
   ended up naming scenario composites (TTL = #9 ∪ #13 ∪ #23 ∪ #21;
   plpgsql_check = #30 ∪ #21; rewind = #13 ∪ #19 + gap). The skill
   should explicitly invite this.

7. **Scenarios-layer GAP-flagging is implicit.** §4 says
   "Scenarios layer gap: <one-line description> if no scenario
   matches and the change-class is recurring." But the agent has no
   guidance on *when* to flag a gap vs just say "no scenario matches".
   Heuristic: flag a gap when the same change-class would plausibly
   come up in a *different* future brainstorm. Worth one sentence.

## Concrete edits

### Edit 1 — Fix the CommitFest URL in §Method step 3

Current text (line ~128-129):
```
   - `WebFetch` `https://commitfest.postgresql.org/<CF#>/?q=<keyword>` (or
     the CF search page); skim for relevant entries.
```

Replace with:
```
   - `WebFetch` `https://commitfest.postgresql.org/?text=<keyword>`
     (cross-CF text search; matches entries from any CommitFest). For
     in-progress CF: `https://commitfest.postgresql.org/` shows the
     current CF's entries. Skim for matching titles + status.
```

Rationale: a literal agent will fail with the current placeholder.
This is a real correctness bug in the procedure.

### Edit 2 — Add "out-of-tree extension that already does this" as an
explicit prior-art category in §Output / §4

Current §4 lists CommitFest + git log + pgsql-hackers + Corpus +
Scenarios layer. Add a sixth bullet:

```
   - **Out-of-tree extensions on PGXN / community repos**: search
     pgxn.org and the well-known per-area extension lists for the
     idea keyword. Many feature requests already have a maintained
     extension solving 80% of the problem (examples: `pg_partman`
     for time-bucket retention, `plpgsql_check` for plpgsql static
     analysis, `pg_cron` for in-DB scheduling, `pgvector` for vector
     ops before native). When this hits, the brainstorm pivots from
     "design from scratch" to "upstream vs harden the extension vs
     move to contrib" — surface this as a DECISION:.
```

Rationale: this is the most-common reframe and the skill currently
treats it as an afterthought. Eval 3 demonstrated the leverage.

### Edit 3 — Add a "what makes approaches genuinely distinct" heuristic
to §Method step 4

Current text:
```
4. **Sketch 2-3 approaches.** Keep them genuinely distinct (not three
   flavors of the same approach). If you can only name one approach,
   say so explicitly — it usually means the design space is narrow OR
   you haven't thought hard enough.
```

Add after it:
```
   Test for distinctness: two approaches are flavors-of-the-same
   when they share ALL of (a) the owning subsystem, (b) the
   invariant footprint, and (c) the user-visible surface (SQL vs
   GUC vs reloption vs extension). If at least one of those differs
   meaningfully, they're distinct. Example: "TTL via autovac" and
   "TTL via dedicated bgworker" differ on (a) but share (b) and (c) —
   borderline-flavors. "TTL via autovac" and "TTL via tuple-
   visibility predicate" differ on all three — genuinely distinct.
```

Rationale: removes ambiguity around the skill's existing instruction.

### Edit 4 — Add an "Anti-patterns" section after §Style notes

Add:
```
## Anti-patterns

- **Designing instead of brainstorming.** If you find yourself naming
  catalog columns, picking SQLSTATEs, or proposing test files — stop.
  That's Phase 2. The brainstorm answers "*which* direction" not
  "*how* exactly".
- **Three-equivalent-approaches with no recommendation.** A bland
  brainstorm wastes the user's time. Pick one. If you genuinely
  can't, that itself is a DECISION: for the user — surface it.
- **Exhaustive prior-art search.** §4 is a triage pass, not a
  literature review. Top 3 git-log hits + first page of CF + a
  quick PGXN check is enough. The user can ask for more later.
- **Low-leverage DECISION: questions.** "What should the GUC name
  be?" or "Should we document this?" are not decisions; they're
  Phase-2 implementation details. DECISION: questions are
  *tradeoffs only the user can adjudicate* (scope, semantics,
  target version, core-vs-contrib).
- **DECISION:-as-deferral.** If the brainstorm offloads every
  question to the user, you haven't thought hard enough.
  Recommend a default; let the user override.
```

Rationale: matches the anti-patterns shape used in sibling skills
(`pg-implement`, `commit-message-style`). Anti-patterns harden the
skill against regressions in future iterations.

### Edit 5 — Add 3 worked DECISION: examples to §Output point 7

Current §Output point 7 lists categories (scope, backcompat,
perf/UX, core-vs-contrib, target-CF-window) but only one inline
worked example. Add:

```
   Example DECISION: questions at the right level:
   - "Are you aware the `<extension>` extension already covers
     ~80% of this? Does it not meet your need, and if so, why?"
     (Prior-art reframe; ranks first if §4 found an extension.)
   - "Should expired rows be query-invisible *immediately* at the
     clock crossing, or is autovacuum-eventual acceptable?"
     (Semantics tradeoff; user mental model.)
   - "Ship as contrib first, or aim for core in one go?"
     (Path-to-release; cheap-to-revert vs harder-to-iterate.)
```

Rationale: the skill currently gives one example. Three more —
each in a different category — makes the bar concrete.

### Edit 6 — Add the composite-scenarios pattern to §4

After the existing "Scenarios layer" bullet, add:

```
     A brainstormed approach often spans 2-3 scenarios at once;
     name all of them. The scenarios index documents the common
     compositions explicitly (see
     `knowledge/scenarios/_index.md` §"Composite features").
     Phase 2 will UNION the file checklists. If the approach
     matches no scenario AND the change-class is recurring
     (same shape will plausibly appear in a different future
     brainstorm), flag a `Scenarios layer gap:` so
     `progress/scenarios-coverage.md` can be updated. If the
     change-class is one-off, don't bother flagging.
```

Rationale: All three of my evals named scenario composites
(or flagged gaps). The skill currently invites a single-scenario
match; the index documents compositions are the norm. This edit
aligns the skill with the index.

### Edit 7 (optional) — Surface the "have you tried the extension"
DECISION: as a *named pattern*

Within §Output point 7, after the worked examples, add:

```
   When §4 surfaced a mature out-of-tree extension covering most of
   the ask, ALWAYS include this DECISION: as the first one. It's
   the most likely brainstorm-killer and you owe the user the
   reframe before they read the candidate approaches below it.
```

Rationale: subtle but high-leverage. The skill's recommendation +
DECISION: ordering can change the user's read.

## Non-edits

- The 8-section §Output structure is correct as-is; no reorder
  needed. All 3 evals filled it cleanly.
- The Forbidden-in-Phase-1 list is correct.
- The `<keyword>` substitution in `git log --grep` works.
- The companion_skills + cross-references are accurate (verified:
  `.claude/skills/pg-feature-plan/`, `pg-implement/`, `pg-claude/`,
  `meta-commit-style/` all exist; `.claude/commands/pg-brainstorm.md`
  exists; `knowledge/scenarios/_index.md` exists).
- Description (frontmatter) is already on-pattern per prior
  iter recap; no edit needed.

## Score delta expectation if all edits applied

Iteration 1 already saturates at 33/33 with_skill, 14/33 baseline.
Iter-2 with_skill will likely stay at 33/33; baseline will stay at
~14/33 (the edits don't leak into baseline knowledge). The value
of these edits is **defensive** — hardening against:

- An agent literally `WebFetch`ing the broken URL (Edit 1, hard
  bug fix).
- An agent skipping the prior-art-extension reframe and writing
  a from-scratch brainstorm for a feature an extension already
  covers (Edit 2, 5, 7 — biggest UX risk).
- An agent producing a three-equivalent-flavors brainstorm with
  no recommendation (Edit 3, 4).
- An agent missing the composite-scenarios pattern (Edit 6).

Measuring this is qualitative on iter-2: the rerun should show
that the agent (a) names the broken URL pattern is fixed,
(b) surfaces the extension-reframe DECISION: ahead of approaches
when applicable, (c) calls out flavor-of-same vs distinct when
sketching approaches, (d) flags gaps with the right heuristic.
