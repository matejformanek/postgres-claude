---
name: pg-feature-brainstorm
description: Brainstorm a half-formed PostgreSQL backend feature idea before it's worth a heavy plan — Phase 1 of the two-phase PG planner, the open-design-space stage that comes BEFORE pg-feature-plan. Frame the problem, name the relevant PG subsystems (parser / planner / executor / heap-AM / index-AM / WAL / replication / catalog / autovac / extensions), sketch 2-3 candidate approaches with explicit tradeoffs, run a "has this been tried?" check against CommitFest entries + git log + the local corpus, surface DECISION: questions only the user can answer before Phase 2, and output a short ~150-300-line brainstorm doc (NOT a file:line-cited implementation plan — that's pg-feature-plan's job). **Use this skill proactively whenever the user says "let's brainstorm a PG idea", "i have an idea for PG", "rough idea: [PG thing]", "what if we let PG [do X]", "what would it take to add [X] to PG", "could we do [Y] in PG", "explore the design space for [Z]", "i want PG to support [...]", "what are the 2-3 candidate approaches for [PG feature]", invokes \`/pg-brainstorm\`, or names a still-fuzzy half-formed PG-backend feature — even when they don't use the literal word "brainstorm". The signal is: the design space is still open, no approach is locked yet, the user wants to scope the problem before committing to file:line cites.** Skip when an approach is already picked and the user wants the heavy implementation plan (use pg-feature-plan or /pg-plan), the brainstorm is for product / SaaS / UX / marketing / business / sprint / roadmap (non-PG), the feature is for a different database engine (MongoDB / Redis / MySQL / SQLite / Snowflake / DuckDB / Cassandra / Kafka), the user is at the design-review stage of an already-written plan (use pg-patch-review or review-checklist), or the question is about already-committed PG features ("how does X work" — that's a corpus / explanation question, not a brainstorm).
when_to_load: Explore a PG feature idea before any plan is appropriate; narrow the design space; "has this been tried?" triage; surface DECISION: questions only the user can answer.
companion_skills:
  - pg-feature-plan
  - pg-claude
  - pg-implement
  - meta-commit-style
---

# pg-feature-brainstorm — Phase 1 of the PG planner

The first stage of the two-phase PostgreSQL feature planner. Output is a
**short, opinionated sketch** that frames the problem and offers
candidate approaches — not an implementation plan.

The pairing:
- **Phase 1 — brainstorm** (this skill) → narrow the design space
- **Phase 2 — plan** (`pg-feature-plan` skill) → make it implementable

Per the user's split: brainstorm explores, plan commits.

## When to use vs not

**Use** when the idea is exploratory:
- "What would it take to add server-side variables?"
- "Could we add a new hook for X?"
- "I want to make EXPLAIN show Y, what are the options?"
- "Should this be a contrib extension or a core change?"

**Don't use** when the task is already scoped:
- "Add a `pg_buffercount()` builtin" → go to `pg-feature-plan` directly.
- "Fix this specific bug" → no brainstorm needed; cite + patch.

**Don't use** for non-PG brainstorming, app architecture, infra design.

## Inputs

- A natural-language description of the idea (the user's argument).
- Optional: a `slug` for the planning artifacts (otherwise derived from
  the idea, e.g. `server-side-variables` → `server_side_vars`).

## Output

A single file at `planning/<slug>/brainstorm.md` with the structure
below. ~150-300 lines total. Anything longer means you're doing
Phase 2 work prematurely — stop and hand off.

### Required sections (in this order)

1. **Problem statement** (3-5 sentences). What is the user actually
   asking for, in your own words? Restate the goal so misunderstandings
   surface early. Name the user who would benefit (DBA, extension
   author, hacker, end user).
2. **Why this might matter** (3-5 sentences). What does PG currently
   force the user to do that this would replace or improve?
3. **Relevant subsystems** (bulleted). Name 1-3 `knowledge/subsystems/*.md`
   docs that the implementation would touch. One-line summary of each.
   This is the **only** corpus you must load in Phase 1 — don't read the
   per-file docs yet.
4. **Has this been tried?** A short result of a triage pass:
   - CommitFest: search `https://commitfest.postgresql.org/` for the
     idea keyword. Note any matching entry by ID + status + last activity.
   - git log: `git log --oneline --grep='<keyword>' source/` for the
     last ~2 years. Note any related commits.
   - pgsql-hackers: if a recent thread is obvious from CF or git,
     reference it; otherwise skip (don't bulk-search the list).
   - Corpus: `grep -r '<keyword>' knowledge/` for anything already
     documented. Note any hit.
   - **Scenarios layer: match against `knowledge/scenarios/_index.md`**.
     If a scenario (or a composite of scenarios) matches the
     brainstormed approach, name it in this section. Phase 2
     (`pg-feature-plan`) will PIN to it as the authoritative §3 file
     checklist — knowing in advance which scenario applies lets the
     user spot a scope mismatch early. Format: `Scenario(s): <slug>`
     or `Scenarios layer gap: <one-line description>` if no scenario
     matches and the change-class is recurring.
5. **Candidate approaches** (2-3, no more). For each:
   - One-paragraph description.
   - **Pros** (2-3 bullets).
   - **Cons / risks** (2-3 bullets).
   - **Approximate scope** (small / medium / large — measured in files
     touched + invariants risked, not lines of code).
   - **Existing PG mechanism it reuses** (a hook? an existing API? a
     parser pattern? a catalog table?).
6. **Recommended approach** (1 paragraph). Pick one. Say why. Name
   what would have to be true for the *other* approaches to win
   (so the user can flag if those conditions hold).
7. **Decisions for the user** (3-5 max). Each is a concrete question
   prefixed with `DECISION:`. Things only the human can answer:
   - Scope (MVP vs full feature)
   - Backward-compat policy (break old API? add new flag?)
   - Performance/UX tradeoffs
   - Whether to do this as core or contrib/extension first
   - Whether to target current master or wait for next CF window
8. **What this brainstorm explicitly did NOT figure out**. A short list
   so the boundary with Phase 2 is clear. E.g. "did not enumerate
   catalog changes", "did not check WAL impact", "did not propose tests".

### Forbidden in Phase 1

- File:line citations from per-file `knowledge/files/...` docs.
  (Phase 2 does this.)
- Phase-by-phase implementation plan.
- Catalog-bump decisions.
- WAL format decisions.
- Test surface enumeration.
- Patch-series structure.

If you find yourself writing those — stop. Save them for Phase 2.

## Method

Run this as a tight loop:

1. **Set up:** create `planning/<slug>/` if it doesn't exist. Pick the
   slug from the user's idea (snake_case, ≤30 chars). If a brainstorm
   already exists, ask the user if they want to overwrite or revise.

2. **Load minimal corpus:** read the master `knowledge/subsystems/`
   index (or use the `pg-claude` skill's flowchart) to pick 1-3 subsystem
   docs to load. Do NOT load per-file docs at this stage. Do NOT walk
   source/.

3. **Run the triage pass:**
   - `WebFetch` `https://commitfest.postgresql.org/<CF#>/?q=<keyword>` (or
     the CF search page); skim for relevant entries.
   - `git -C source log --oneline --grep='<keyword>' --since='2y'` — top 5.
   - `grep -rli '<keyword>' knowledge/` — note hits, don't read them
     deeply.

4. **Sketch 2-3 approaches.** Keep them genuinely distinct (not three
   flavors of the same approach). If you can only name one approach,
   say so explicitly — it usually means the design space is narrow OR
   you haven't thought hard enough.

5. **Recommend.** Pick one. Default to the smallest approach that meets
   the stated goal. If the user's framing implies they want the bigger
   approach, name that tradeoff in your recommendation.

6. **Decisions.** Name 3-5. Be specific — "scope (MVP vs full)" is too
   vague; "Should the MVP support DEFAULT clauses or only NOT NULL?" is
   right.

7. **Write.** Single file, ~150-300 lines. Resist the urge to be
   exhaustive.

8. **Hand off.** End with one short paragraph: *"Run `/pg-plan <slug>`
   when you've picked an approach and answered the DECISION: questions
   inline above."* Or signal that the brainstorm itself surfaced a
   blocker that needs resolving before planning makes sense.

## Boundaries vs other skills

- **`pg-feature-plan`** (Phase 2): consumes this output. Don't do its
  work here.
- **`pg-claude`**: the master nav. Use to pick which subsystem docs to
  load.
- **`patch-submission`**: only relevant once a patch exists. Don't
  pre-empt.
- **`/implement`**: takes over after Phase 2 + a real plan.

## Style notes

- Be opinionated. A bland brainstorm with three equivalent approaches
  and no recommendation wastes the human's time.
- Be brief. The whole document should be readable in 5 minutes.
- Be honest about uncertainty. "I'm guessing the lockmgr would need a
  new lock type here, but I haven't verified" is more useful than a
  confident-sounding wrong claim.
- Cite the corpus when relevant: `[via knowledge/subsystems/X.md]` for
  any subsystem-level claim. Use `[unverified]` for everything else.

## Where the artifact lives

`planning/<slug>/brainstorm.md` — in a NEW top-level directory
`planning/`, sibling to `knowledge/` and `sessions/`.

The `planning/` directory is for **work-in-progress design docs**.
Difference from `knowledge/`: knowledge is distilled durable
reference; planning is messy WIP that may be discarded. Difference
from `sessions/`: sessions are logs of what happened; planning is
forward-looking.

Cleanup policy: planning docs stay in tree until the feature lands
(then the plan is referenced by the patch's commit message and can
be archived) or until the user explicitly says drop it.

## Cross-references

- `.claude/skills/pg-feature-plan/SKILL.md` — Phase 2 consumer of this skill's output; reads `planning/<slug>/brainstorm.md` + the inline DECISION: answers.
- `.claude/skills/pg-implement/SKILL.md` — Phase 3 consumer (via the plan); brainstorm is read for context only, not procedure.
- `.claude/skills/pg-claude/SKILL.md` — master index used to pick which 1-3 `knowledge/subsystems/*.md` docs to load.
- `knowledge/scenarios/_index.md` — the scenarios decision tree consulted in §4 (Has this been tried?).
- `.claude/skills/meta-commit-style/SKILL.md` — the brainstorm.md file commits to the meta repo via this style.
- `planning/README.md` — directory layout for `planning/<slug>/`.
- `.claude/commands/pg-brainstorm.md` — slash-command wrapper that invokes this skill.
