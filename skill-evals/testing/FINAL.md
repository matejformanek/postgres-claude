# Testing skill — final eval report

Skill under test: `.claude/skills/testing/SKILL.md`
Evals: `iteration-1/evals.json` (3 prompts covering regress / TAP / isolation)

## Iteration 1 — methodology flaw

Iter-1 ran two attempts per eval and labeled them "A" and "B", reporting
22/22 and 21/22. **Both attempts were produced with the SKILL.md loaded.**
That measures intra-skill variance (how consistently the skill produces a
correct answer across re-rolls), not skill *value* (how much better the
skill makes the answer vs. no skill). The 22/22 vs 21/22 split is therefore
not a meaningful "skill works" signal — it only says the skill is reasonably
deterministic.

No content corrections were warranted from iter-1 because both attempts
already passed nearly every assertion. Five small refinements were proposed
(`iteration-1/proposed-edits.md`):

- E1 — inline isolation-spec skeleton in SKILL Step 1
- E2 — explicit LSN-sync recipe (`wait_for_replay_catchup` / `poll_query_until`)
- E3 — explicit "TAP verifies replicated state, not WAL-record identity" caveat
- E4 — `done_testing();` reminder
- E5 — name the `source/src/test/modules/injection_points/` path instead of
  saying "use injection points"

All five were applied for iter-2 (`iteration-2/edits-applied.md`); the path
and helper name were verified against `source/`
(`source/src/test/modules/injection_points/` exists;
`PostgreSQL::Test::Cluster::wait_for_replay_catchup` is defined at
`source/src/test/perl/PostgreSQL/Test/Cluster.pm:3543`).

## Iteration 2 — corrected methodology

For each of the 3 evals, answers were produced **twice**:

- `iteration-2/eval-N/with_skill/answer.md` — with the edited SKILL.md
  available.
- `iteration-2/eval-N/baseline/answer.md` — without the testing skill,
  drawing only on general PG-internals knowledge.

Graded against iter-1's assertion list (same 22 assertions):

| Eval | with_skill | baseline |
|---|---|---|
| 1 — regress for new builtin | 7/7 | 5.5/7 |
| 2 — TAP streaming rep + WAL | 8/8 | 6.5/8 |
| 3 — isolation for new lock path | 7/7 | 4/7 |
| **Total** | **22/22** | **16/22** |

Skill lift: **+6 assertions** (+27 percentage points).

## Where the skill earns its lift

The 6-point gap concentrates in exactly the kind of knowledge a generalist
session lacks:

- **House rules** — max 20 tests per `parallel_schedule` group (eval 1 a4);
  don't renumber TAP tests to keep backports safe (eval 2 a2 partial credit);
  prefer permutation markers over `_1.out` variants (eval 3 a6).
- **Exact paths and flags** — `source/src/test/recovery/meson.build` rather
  than vague "the build system" (eval 2 a3); `pg_isolation_regress
  --temp-instance --top-builddir` rather than just `pg_isolation_regress`
  (eval 3 a7); `build/testrun/<suite>/<test>/log/regress_log_*` rather than
  "somewhere under tmp_check" (eval 2 a7).
- **Non-obvious gotchas** — `isolationtester` only sees heavyweight locks;
  LWLock / buffer-pin races need `src/test/modules/injection_points/`
  instead (eval 3 a4). A baseline session would write a green isolation
  spec for an LWLock race, ship it, and have it pass non-deterministically
  forever.

The iter-2 edits also fired as intended: the isolation grammar skeleton is
reproduced verbatim in eval-3 `with_skill`, and the LSN `poll_query_until`
form appears in eval-2 `with_skill`.

## Bottom line

Skill is in good shape. The decision tree + wiring table + fast-loop recipe
structure maps cleanly onto the kind of question a PG contributor actually
asks. No further edits planned.
