# Five-run trilogy retro — 2026-07-13

**Session shape:** one continuous interactive session, ~4 hours,
five back-to-back blind-trilogy calibration runs against known-fixed
historical PG memory-related bugs, plus 5 lesson graduations along
the way. Every calibration is a data point on the planner-suite's
ability to blindly reproduce upstream fixes and surface where it
does/doesn't converge.

## The five runs at a glance

| # | Target commit  | Subsystem              | Bug shape                    | Diff size (upstream) | Diff size (ours) | Blind trilogy verdict            |
|---|----------------|------------------------|------------------------------|---------------------:|-----------------:|----------------------------------|
| 1 | `5a2043bf713`  | utils/adt/jsonpath     | transient-lifetime leak      |            +362/-233 |         +342/-80 | working fix, ~30% clunkier design |
| 2 | `b20c952ce70`  | utils/activity/pgstat  | redundant double-init        |                   -2 |               -2 | **byte-identical**                |
| 3 | `abdeacdb0920` | executor/TupleHashTable| ownership-boundary API       |             +33/-43 |         +107/-1 | same 2 sites, additive vs restructure |
| 4 | `232d8caeaaa`  | contrib/postgres_fdw   | PG_TRY-not-enough            |             +35/-27 |         +82/-25 | same category, heavier details    |
| 5 | `b46efe90482`  | replication/pgoutput   | UAF on retry after error     |              +24/-5 |         +45/-0  | same category, 2 detail divergences |

Total planning artifacts across the 5 runs: **~9 000 lines** of
baseline / triage / brainstorm / plan / notes / comparison
markdown, plus ~300 lines of executable C.

## Lessons graduated during this session

Three lessons landed as skill/idiom/scenario edits, all in the
same day:

- **L5** — storage-representation adversarial pass (already landed
  before this session, from run #1 jsonpath_leak's comparison).
- **L6** — approach-E control-flow restructure mandatory in
  brainstorm §5 (landed as commit `55e853cf`, motivated by run #3
  nodesubplan_leak's F32).
- **L7** — callback-based approach detail sub-block mandatory in
  plan §7 (landed as commit `eb838af6`, motivated by run #4
  fdw_directmodify_leak's F34+F35+F36).

Findings graduated (all cross-referenced from the comparison
files):

| Finding | Origin run | Codification location |
|---------|-----------|----------------------|
| F30     | 1 jsonpath_leak | pg-feature-plan §7 ownership grep-pass |
| F31     | 3 nodesubplan   | scenario#34 Phase 0 Step 0.4 reproducer-shape verification |
| F32     | 3 nodesubplan   | source of L6 |
| F33     | 3 nodesubplan   | notable but not codified (docs-scope judgment call) |
| F34     | 4 fdw_directmodify | memory-contexts.md §"Idioms for callback-based ownership" |
| F35     | 4 fdw_directmodify | same section |
| F36     | 4 fdw_directmodify | same section |
| F37     | 4 fdw_directmodify | scenario#34 Phase 0 Step 0.5 target-suite health check |
| F38     | 5 pgoutput_uaf  | F34 refinement — public-header caveat |
| F39     | 5 pgoutput_uaf  | F36 refinement — share-the-implementation |

## Cross-cutting patterns

### Pattern 1 — blind trilogy adds behavior; upstream restructures

Three of the five runs (#1 jsonpath, #3 nodesubplan, #4
fdw_directmodify) landed a working fix but with a **larger net
LOC** than upstream. In each case the blind trilogy preserved the
parent code's existing shape and added the invariant on top,
while upstream restructured the surrounding code to make the
invariant fit more naturally.

This pattern is codified as L5 (data structure representation) and
L6 (control-flow shape), both of which extend the brainstorm §5
candidate-approach enumeration with an adversarial pass that
explicitly asks "if I were writing this from scratch given the new
invariant, would the parent's shape survive?"

### Pattern 2 — trilogy details are independently choice-able from category

Once L6 landed, run #4 (fdw_directmodify) correctly identified the
approach category (E: memory-context reset callback) matching
upstream. But the implementation details — where to store the
callback struct, what function to register, how to handle the
existing cleanup path — still diverged from upstream. L7 codified
those three detail choices as a mandatory sub-block in plan §7,
and run #5 (pgoutput_uaf) then correctly named the 3 choices
explicitly before Phase 3 started, letting Phase 4 score them
individually against upstream.

Run #5 still diverged from Sawada on 2 of the 3 details (F38,
F39), but for reasons that were surface-able and codifiable at the
comparison step, not at the "what did we miss?" step.

### Pattern 3 — signal shapes are diverse

Each run required a different signal-observation approach:

- Run #1: RSS climb (32 → 70 MB over 5s query) — direct.
- Run #2: per-parallel-worker cumulative — needed amplified
  workload.
- Run #3: per-hash-probe query-lifespan — 15 MB/s during 5s query,
  released at query end.
- Run #4: session-lifespan libpq malloc — needed 20 000×
  amplification (3.3 MB/s over 25s).
- Run #5: UAF crash-on-retry — needed cassert +
  `MALLOC_PERTURB_=209` for poisoning; direct crash reproduction on
  macOS was fragile.

Codification: F31 (reproducer-shape verification) + F37
(Phase 0.5 target-suite health check) formalize the "confirm your
signal exists before assuming your fix works."

### Pattern 4 — F30 grep-pass pays off every run

Every one of the 5 runs used the F30 grep-pass in plan §7 to
verify ownership claims. In runs #1 and #4, the grep pass
identified specific sites the plan needed to acknowledge (jsonpath's
mixed copy/borrow at line 1741; postgres_fdw's PG_TRY-inside-
FDW-frame-fires-outside). In runs #3 and #5, F30 confirmed the
plan's assumed invariant was already followed by 4/5 sister callers
(nodesubplan; the callback idiom is well-established).

**F30 is the trilogy's most durable payoff so far.** It surfaces
plan errors at plan-time rather than R4 phase-end-check time.

## Novel bug shapes probed this session

- **API-contract ownership change** (run #3) — the fix wasn't
  adding cleanup; it was documenting and enforcing "the caller
  resets the tempcxt." L6 codifies the control-flow shape needed
  to make this legible.
- **PG_TRY-not-enough** (run #4) — the throw fires outside the
  code's stack frame, so PG_TRY at the acquisition site cannot
  catch. Motivates callback-based ownership.
- **UAF on retry** (run #5) — not a leak per se; a stale HTAB
  outliving its referenced state. Same callback fix pattern as #4
  but different bug taxonomy.

The first two runs (#1 jsonpath, #2 pgstat_progress) probed
"classic" leak shapes (transient-lifetime, redundant init). The
last three probed structurally novel shapes. The trilogy scaffold
generalized in every case.

## Where the trilogy still under-fits

Two systematic gaps still visible after 5 runs:

1. **Over-adds public-header changes.** Run #5's F38 shows F34's
   "embed callback struct" advice wasn't public-header-aware.
   Codified now. But other public-header considerations
   (`typedef` visibility, ABI compat for loadable plugins) aren't
   in the plan-skill template yet.
2. **Under-refactors pre-existing cleanup paths.** Run #5's F39
   codifies the "share-the-implementation" pattern for reset
   callbacks. But the deeper pattern — "when I add an
   error-path safety net, does the happy path still need its own
   code?" — is a special case of L6 (restructure control flow to
   match new invariant) that the current L6 codification
   doesn't quite reach.

Both gaps are further refinements of F34+F36; codified as F38+F39
this session.

## Branch inventory (all 5 runs' feature branches preserved)

- `feature_jsonpath_leak` HEAD `e92433395ff` (3 commits above `7724cb9935a`)
- `feature_pgstat_progress_leak` HEAD `193187edd3a` (1 commit above `a450dd7ad4f`)
- `feature_nodesubplan_leak` HEAD `d7cfd1daf94` (3 commits above `9016fa7e3bc`)
- `feature_fdw_directmodify_leak` HEAD `fa4030506f2` (1 commit above `d98cefe1143`)
- `feature_pgoutput_uaf` HEAD `00db6795dbd` (1 commit above `71540dcdcb2`)

None pushed upstream. All 5 upstream fixes are already on master
(`5a2043bf713`, `b20c952ce70`, `abdeacdb0920`, `232d8caeaaa`,
`b46efe90482`). Branches exist as methodology-calibration artifacts.

## Skill & scenario deltas landed this session

Meta commits in `postgres-claude/` main:

- `57f8aacf` — planning docs for nodesubplan_leak (run #3)
- `55e853cf` — **L6 approach E landed** in pg-feature-brainstorm SKILL.md + F31 landed in fix-memory-leak scenario
- `e190b8f8` — planning docs for fdw_directmodify_leak (run #4)
- `eb838af6` — **L7 callback-detail sub-block landed** in pg-feature-plan SKILL.md + F34/F35/F36/F37 landed in memory-contexts idiom + scenario#34
- `eb256e1a` — planning docs for pgoutput_uaf (run #5) + F38/F39 refinements

Every improvement to a skill or idiom is anchored to at least one
`planning/*/comparison.md` §-section that motivates it. The
citation chain — skill → idiom → planning artifact → upstream fix
— is intact for all landings.

## Net assessment

**The blind trilogy is a working methodology.** Five runs across
five distinct subsystems (utils/adt, utils/activity, executor,
contrib, replication) all produced semantically correct fixes
matching the upstream fix's category. Two runs converged
byte-identically (#2) or line-for-line semantically (#3 phase 2,
#5 phase 1 approach), and the three that diverged surface
codifiable lessons rather than one-off mistakes.

Each new run either **exercises a codification landed in the
previous run** (run #5 exercised L7 landed same day; run #4
exercised L6 landed same day; run #3 predicted F32 that became L6)
or **surfaces a refinement** (F38 refining F34; F39 refining F36).

The methodology's remaining under-fits (systematic over-add of
LOC, systematic under-refactor of pre-existing cleanup) are now
well-characterised, with L5+L6+L7 spread across brainstorm and
plan skills to address them at the right stage.

**Recommended next runs (when time permits):**
- A run that stresses F38 (public-header state struct + callback)
  — the first target that would score the F38 codification.
- A run in a subsystem not yet probed: WAL/recovery, autovacuum,
  planner/optimizer, GIN parallel-build, FDW-other-than-postgres_fdw.
- A run whose upstream fix is NOT callback-based — validate the
  trilogy isn't over-fitting to reset-callback patterns after
  three consecutive callback runs (#4, #5, and the potential 6th).

## Cross-references

- Planning docs: `planning/{jsonpath_leak,pgstat_progress_leak,nodesubplan_leak,fdw_directmodify_leak,pgoutput_uaf}/`.
- Skills: `.claude/skills/pg-feature-brainstorm/SKILL.md` (L5+L6),
  `.claude/skills/pg-feature-plan/SKILL.md` (F30 grep-pass + L7 sub-block).
- Idioms: `knowledge/idioms/memory-contexts.md` §"Idioms for
  callback-based ownership" (F34+F35+F36+F38+F39).
- Scenario: `knowledge/scenarios/fix-memory-leak.md` §"Phases"
  Step 0.4 (F31) + Step 0.5 (F37).
- Prior session retros: `sessions/2026-06-23-memory-hunt-calibration.md`
  (Phase 0 + run #1 origin), `sessions/2026-06-22-sesvars-v3-retro.md`
  (methodology origin).
- STATE.md — five head entries in reverse-chronological order
  covering runs #1-#5.
