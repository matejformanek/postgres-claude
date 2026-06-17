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

0. **Concrete usage surface** (REQUIRED, comes FIRST). 20-30
   enumerated example lines showing what the feature must let the
   user *write*. Each example is one SQL / PL/pgSQL / DDL line.
   Group by usage class. Generate this BEFORE answering DECISION
   questions — every DECISION must take these examples as inputs,
   not abstractions.

   Why this is §0: the sesvars first calibration (2026-06-17)
   produced an MVP that covered ~30% of what the user actually
   wanted, because DECISION questions were phrased so narrowly
   they excluded entire usage classes (array indirection, composite
   access, PL/pgSQL direct writes, DDL DEFAULT, SELECT INTO,
   aggregate semantics). The §0 enumeration prevents that failure
   mode — if a usage class isn't on the list, the brainstorm has
   admitted it's out of scope; if it IS on the list, the candidate
   approaches MUST be able to support it.

   How to generate the examples — **parallel fan-out via subagents**:
   - Agent A reads `knowledge/scenarios/_index.md` + every pinned
     scenario; lists usage examples that show up in those scenarios.
   - Agent B greps `source/src/test/regress/sql/` and
     `contrib/*/sql/` for similar-shaped features; extracts
     idiomatic SQL surface lines.
   - Agent C web-searches pgsql-hackers + CommitFest entries for
     the feature keyword; extracts examples from recent threads.
   - Agent D — **if the user has a manual reference implementation**
     (see §0.7) — reads the reference's regress SQL file as the
     UPPER BOUND. Every example line that file contains becomes a
     candidate for §0.
   - Synthesize the four agent outputs into a deduplicated 20-30
     line table grouped by usage class.

   Format:
   ```
   ## §0 Usage surface (comprehensive)

   ### Reader
   - SELECT @x
   - SELECT @arr[2], @arr[2:3]
   - SELECT (@typ).field
   - SELECT @js -> 'k'
   ...

   ### Utility writer (SET)
   - SET @x := expr
   - SET @x := expr, @y := expr, @z := expr
   - SET @x TYPE DATE := expr
   - SET @arr[2] := v
   - SET @arr[2:3] := v
   ...

   ### Inline writer (SELECT :=)
   - SELECT @x := expr
   - SELECT @a := 1, @b := 2
   - SELECT @x := (subquery)
   - SELECT col, @cum := @cum + col FROM t
   ...

   ### Cross-feature
   - PL/pgSQL DO block: BEGIN SET @pl := 3; END
   - SELECT col INTO @v, @w FROM t
   - CREATE TABLE t (c INT DEFAULT @v)
   - EXECUTE FORMAT('SELECT @x := %L', val)
   ...

   ### Adversarial / edge
   - Multi-target SET with self-referential type inference
   - Chained inline := with type-shift across columns
   - Quoted identifiers @"name with spaces"
   - WHERE-clause assignment evaluation order
   ...
   ```

   The DECISION questions in §7 then say things like "should the
   feature support the array-indirection examples above (rows 5-8)?"
   — concrete, bound to specific lines, not abstract.

0.5. **Existing-PG-mechanism survey** (REQUIRED, before
   candidate approaches). What existing PG nodes / mechanisms /
   patterns could carry this feature? The default is **REUSE over
   INVENT**. Inventing a new Expr node, new EEOP step, new
   parsetree shape is 5× more touch points than reusing an
   existing one (walker coverage, EEOP_*_EXEC interpreter step,
   JIT mirror, ruleutils support, copy/equal/out/read funcs
   regen).

   How to survey — **parallel fan-out via subagents**:
   - Agent A: grep `source/src/include/nodes/primnodes.h` +
     `parsenodes.h` for similar-shaped Expr / Stmt nodes. Note
     `Param` (with `paramkind` discriminator), `SQLValueFunction`
     (with `op` discriminator), `XmlExpr` (with `op`), etc.
     Discriminator-bearing existing nodes are PRIME candidates
     for reuse.
   - Agent B: grep `source/src/include/executor/execExpr.h` for
     existing `EEOP_*` steps that could be specialized via a
     `d.union.*` arm without inventing a new opcode.
   - Agent C: grep `source/src/include/access/` for RangeTblEntry
     kinds (`RTE_*`) and FunctionScanState patterns. New row-source
     features often fit RTE kinds without inventing a Path / Plan
     node.
   - Agent D: search the corpus `knowledge/idioms/*.md` and
     `knowledge/subsystems/*.md` for "existing mechanism" /
     "reuse" / "PARAM_*" / "RTE_*" patterns. The corpus is built
     to surface these.

   Output a short matrix in §0.5:
   ```
   ## §0.5 Existing PG mechanisms considered for reuse

   | Mechanism | Could it carry this? | Cost of reuse | Cost of invent |
   |---|---|---|---|
   | Param + new paramkind | YES — text-named, value-bearing, dynamically-typed | tiny — paramkind enum + paramsesvarid field | 5× more touch points |
   | SQLValueFunction + new op | NO — designed for parameterless time/role funcs | n/a | n/a |
   | New T_SessionVar Expr | YES but expensive | nodeFuncs.c 6 cases + parse_collate.c + clauses.c (3 walkers) + ruleutils.c + JIT mirror | baseline |
   | RTE_*KIND* | NO — sessvars are scalar, not row-source | n/a | n/a |
   ```

   **The recommended approach in §6 MUST justify its mechanism
   choice with reference to this matrix.** If §6 picks invent-
   new, the recommendation has to argue why the existing mechanism
   doesn't fit — not just "it's cleaner".

   Sesvars-calibration evidence: the user's manual implementation
   chose `PARAM_SESSION_VARIABLE` (new paramkind on Param). My
   AI-driven implementation invented `T_SessionVar` +
   `T_SessionVarAssign`. Mine ended up with 5× more touch points
   for ~30% less coverage. The §0.5 step exists to prevent that
   repeat.

0.7. **User-reference-implementation readthrough** (REQUIRED IF
   one exists). Ask the user explicitly: "do you have a manual
   reference implementation of this feature?" Look at the
   conversation history, the working directory, and any prior
   session logs for hints (e.g. user mentions a thesis, a private
   branch, a "my version" repo path).

   **If a reference exists, READ IT as the upper-bound spec.** The
   §2 out-of-scope lock is for features the user EXPLICITLY
   EXCLUDES, not "things we haven't thought of yet". The reference
   tells you what the user actually wants; the §0 usage surface
   becomes the union of (the reference's surface) + (any additions
   the user calls out).

   This is the R15 default: comprehensive scope, not minimal MVP.
   If the user has built it once already manually, the planner
   suite's job is to produce something *comparable to* the
   reference, not 30% of it.

   How to readthrough:
   - Read the reference's main regress SQL file in full
     (`session_variables.sql` for sesvars). This IS the spec.
   - Read the reference's expected output to confirm semantics.
   - Skim the reference's main implementation file (the
     equivalent of `commands/<feature>.c`) just for ARCHITECTURE
     — what existing PG mechanism did they reuse? (This feeds
     §0.5.)
   - Note any features the reference SHIPS that look like scope
     expansions worth including, AND any features that look
     genuinely out-of-scope (e.g. experimental / personal-pref).
   - Surface in §7 as a DECISION: "the reference ships X, Y, Z
     — should we match all of these or scope down? If scope
     down, which?"

   Anti-pattern this rule prevents: "I won't read the reference
   because it might bias me toward their design." Wrong framing.
   The bias is helpful: the reference encodes the user's real
   intent. The planner suite's job is to match or exceed it, not
   reinvent it independently.

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
   - **Out-of-tree extensions on PGXN / community repos**: search
     pgxn.org and well-known per-area extension lists for the idea
     keyword. Many feature requests already have a maintained
     extension solving 80% of the problem (`pg_partman` for
     time-bucket retention, `plpgsql_check` for plpgsql static
     analysis, `pg_cron` for in-DB scheduling, `pgvector` for vector
     ops before native, …). When this hits, the brainstorm pivots
     from "design from scratch" to **upstream into core vs harden
     the extension vs move to contrib** — surface this as the FIRST
     DECISION: in §7.
   - **Scenarios layer: match against `knowledge/scenarios/_index.md`**.
     If a scenario (or a composite of scenarios) matches the
     brainstormed approach, name it in this section. Phase 2
     (`pg-feature-plan`) will PIN to it as the authoritative §3 file
     checklist — knowing in advance which scenario applies lets the
     user spot a scope mismatch early. Format: `Scenario(s): <slug>`
     or `Scenarios layer gap: <one-line description>` if no scenario
     matches and the change-class is recurring.
     A brainstormed approach often spans 2-3 scenarios at once;
     name all of them. The scenarios index documents the common
     compositions explicitly (see `knowledge/scenarios/_index.md`
     §"Composite features"). Phase 2 will UNION the file checklists.
     Heuristic for when to flag a `Scenarios layer gap:` — flag it
     when the same change-class would plausibly recur in a future
     brainstorm. If it's truly one-off, just say "no scenario
     matches" without flagging.
5. **Candidate approaches** (2-3, no more). For each:
   - One-paragraph description.
   - **Pros** (2-3 bullets).
   - **Cons / risks** (2-3 bullets).
   - **Approximate scope** (small / medium / large — measured in files
     touched + invariants risked, not lines of code).
   - **Existing PG mechanism it reuses** (a hook? an existing API? a
     parser pattern? a catalog table? a PARAM kind? an RTE kind?).
     **REQUIRED**: cite the §0.5 mechanism survey row this approach
     came from. If "invent new", explain why §0.5's reuse candidates
     don't fit.
   - **Coverage of §0 usage surface** (which usage classes does this
     approach support? List the §0 example-row numbers explicitly.
     If an approach covers only rows 1-10 out of 25, it's a 40%-
     scope approach — say so and flag whether the remaining 60%
     is in-scope but deferred or genuinely out-of-scope.).
   - **Citations** (REQUIRED): at least 3 `knowledge/scenarios/*.md`
     this approach draws on, 2 `knowledge/personas/*.md` whose
     reviewer reflexes apply, 2 `knowledge/idioms/*.md` whose
     patterns it follows. Inline format:
     `[scenarios: #11 add-new-sql-keyword, #15 add-new-expression-eval-step]`
     `[personas: tom-lane (parse-tree durability), andres-freund (JIT mirror)]`
     `[idioms: lexer-and-grammar, node-types]`.
     If any cited file doesn't exist, flag as a corpus gap to fix
     (don't fake it).
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

   Worked examples at the right level (one per category):
   - "Are you aware the `<extension>` extension already covers ~80%
     of this? Does it not meet your need, and if so, why?"
     (Prior-art reframe; ranks FIRST whenever §4 found a mature
     out-of-tree extension — see Edit-2 note in §4.)
   - "Should expired rows be query-invisible *immediately* at the
     clock crossing, or is autovacuum-eventual acceptable?"
     (Semantics tradeoff; shapes the user's mental model.)
   - "Ship as contrib first, or aim for core in one go?"
     (Path-to-release; cheap-to-revert vs harder-to-iterate.)

   Anti-example (too vague): "What should the GUC name be?" — that
   is a Phase-2 implementation detail, not a brainstorm DECISION:.
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

Run as a parallel-fan-out loop (NOT a sequential tight loop —
the old single-context method under-explored). The fan-out is
load-bearing.

1. **Set up:** create `planning/<slug>/` if it doesn't exist. Pick the
   slug from the user's idea (snake_case, ≤30 chars). If a brainstorm
   already exists, ask the user if they want to overwrite or revise.

2. **Ask about user reference impl.** Explicit question: "do you
   have a manual reference implementation of this feature
   anywhere?" Check conversation history + working dirs + STATE.md
   for hints. If yes, locate the regress SQL file path before
   proceeding — Agent D in step 4 needs it.

3. **Load minimal corpus:** read the master `knowledge/subsystems/`
   index to pick 1-3 subsystem docs to load. Do NOT load per-file docs
   at this stage. Do NOT walk source/ in-context (the agents below
   will).

4. **PARALLEL FAN-OUT — usage surface enumeration (§0).** Spawn
   4 subagents in the same message (Agent tool, subagent_type
   general-purpose):

   - **Agent A — scenario mining.** Read
     `knowledge/scenarios/_index.md` + every plausibly-relevant
     scenario file. Return 10-15 example usage lines extracted
     from scenario examples + every scenario slug that matches.

   - **Agent B — source-tree mining.** Grep
     `source/src/test/regress/sql/` + `contrib/*/sql/` for
     similar-shaped features (e.g. for sesvars: grep for
     `Param`, `PREPARE`, `SET`, `:=` patterns). Return 10-15
     idiomatic SQL lines extracted from PG's own tests.

   - **Agent C — community mining.** WebFetch
     `https://commitfest.postgresql.org/?text=<keyword>` + the
     top 5 git log hits for the keyword + a WebSearch for
     "pgsql-hackers <feature> proposal". Return any recent
     proposal threads + the SQL surface lines they propose.

   - **Agent D — user-reference mining (if reference impl
     exists per step 2).** Read the reference's regress SQL
     file in full. Read its expected output. Skim its main
     implementation file's TOP-OF-FILE comment for architecture
     notes. Return: every distinct usage line from the regress
     file + a one-paragraph architecture summary + the existing
     PG mechanism the reference reuses (if discernible).

   Synthesize Agents A/B/C/D outputs into the §0 usage surface
   table (20-30 lines, grouped by usage class — see the §0
   format in "Required sections" above).

5. **PARALLEL FAN-OUT — existing-PG-mechanism survey (§0.5).**
   Spawn 4 subagents:

   - **Agent A — primnodes/parsenodes mining.** Grep
     `source/src/include/nodes/primnodes.h` +
     `parsenodes.h` for Expr/Stmt nodes with discriminator
     fields (`paramkind` on Param, `op` on SQLValueFunction,
     `op` on XmlExpr, etc.). Return a list of nodes that
     could plausibly be specialized via a new discriminator
     value.

   - **Agent B — execExpr mining.** Grep
     `source/src/include/executor/execExpr.h` for `EEOP_*`
     steps + their `d.union.*` arms. Return a list of steps
     that handle similar value-domain operations (could a new
     case fit into an existing step's union?).

   - **Agent C — RTE / FunctionScan mining.** Grep
     `source/src/include/nodes/parsenodes.h` for `RTE_*`
     kinds. Grep for FunctionScanState + similar patterns.
     Return any row-source mechanisms that could carry the
     feature.

   - **Agent D — corpus pattern mining.** Read
     `knowledge/idioms/*.md` for "reuse"-pattern docs (e.g.
     node-types.md, lexer-and-grammar.md). Return a short list
     of "X is the canonical way to add a Y" patterns.

   Synthesize into the §0.5 matrix (mechanism × can-it-carry-
   this × cost-of-reuse × cost-of-invent). The recommended
   approach in §6 must cite one row from this matrix.

6. **Sketch 2-3 approaches.** Keep them genuinely distinct (not three
   flavors of the same approach). If you can only name one approach,
   say so explicitly — it usually means the design space is narrow OR
   you haven't thought hard enough.

   Distinctness test: two approaches are flavors-of-the-same when
   they share ALL of (a) the owning subsystem, (b) the invariant
   footprint, (c) the user-visible surface (SQL vs GUC vs reloption
   vs extension). If at least one of those differs meaningfully,
   they're distinct. Example: "TTL via autovacuum extension" vs
   "TTL via dedicated bgworker" differ on (a) but share (b) and (c)
   — borderline-flavors. "TTL via autovacuum" vs "TTL via tuple-
   visibility predicate" differ on all three — genuinely distinct.

7. **Recommend.** Pick one. **Default to COMPREHENSIVE scope, not
   minimal MVP** (per R15 in pg-implement-discipline.md). If the
   user's framing or a reference impl from step 2 implies the
   comprehensive approach, take it as the default. MVP framing
   requires the user's EXPLICIT consent — name the tradeoff in the
   recommendation and let them opt down.

   The recommendation must:
   - Cite the §0.5 mechanism row this approach uses (reuse-vs-
     invent).
   - Cite the §0 usage-class coverage (row-numbers list).
   - Name 3 scenarios, 2 personas, 2 idioms the approach draws on
     (per §5 Citations requirement).
   - If a reference impl exists from §0.7, explicitly state how the
     recommendation COMPARES to the reference: "matches reference
     surface" OR "extends reference by X" OR "scopes down vs
     reference by dropping Y, see DECISION 2".

8. **Decisions.** Name 3-5. Be specific — "scope (MVP vs full)" is too
   vague; "Should the MVP support DEFAULT clauses or only NOT NULL?" is
   right. Each DECISION must reference §0 example rows by number:
   "Should we support array-indirection (§0 rows 5-8) in v1?".

9. **Write.** Single file, ~250-450 lines (raised from the old
   150-300 limit — the §0 + §0.5 + §0.7 + citation requirements
   make brainstorms LONGER, and that's correct: the cost of going
   deep at brainstorm time is far less than the cost of
   under-scoping at plan time).

10. **Hand off.** End with one short paragraph: *"Run `/pg-plan <slug>`
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

## Anti-patterns

- **Designing instead of brainstorming.** If you find yourself naming
  catalog columns, picking SQLSTATEs, or proposing test files — stop.
  That's Phase 2. The brainstorm answers "*which* direction" not
  "*how* exactly".
- **Three-equivalent-approaches with no recommendation.** A bland
  brainstorm wastes the user's time. Pick one. If you genuinely
  can't, that IS the DECISION: — surface it.
- **Exhaustive prior-art search.** §4 is a triage pass, not a
  literature review. Top 3 git-log hits + first page of CF + a
  quick PGXN check is enough. The user can ask for more later.
- **Skipping the extension-already-exists reframe.** If §4 hits a
  mature out-of-tree extension covering most of the ask, the
  candidate approaches MUST be framed against it (upstream vs
  harden vs move-to-contrib), not designed from scratch. The
  first DECISION: must surface this — see §Output 7 examples.
- **Low-leverage DECISION: questions.** "What should the GUC name
  be?" or "Should we document this?" are Phase-2 implementation
  details, not brainstorm DECISIONs. A DECISION: is a tradeoff
  only the user can adjudicate (scope, semantics, target version,
  core-vs-contrib).
- **DECISION:-as-deferral.** If the brainstorm offloads every
  question to the user, you haven't thought hard enough.
  Recommend a default; let the user override.

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
