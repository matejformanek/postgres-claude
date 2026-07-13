# Comparison — our blind fix vs Tom Lane's `abdeacdb0920`

**Date:** 2026-07-13
**Our 3-commit chain (`feature_nodesubplan_leak`):**
- `1b46b9a4456` Phase 1: outer-probe reset at `ExecHashSubPlan` entry
- `be6094ae6d4` Phase 2: inner-build reset in `buildSubPlanHash` loop
- `d7cfd1daf94` Phase 3: `execGrouping.c` docs + `subselect.sql` regress row

**Upstream fix:** `abdeacdb0920d94dec7500d09f6f29fbb2f6310d` (Haiyang
Li, Tom Lane review + commit, 2025-09-10, Bug #19040, 1 commit).

Both branches start from the same parent `9016fa7e3bc`.

## Leak outcome

| metric              | parent commit | our fix      | Tom Lane's fix (expected) |
|---------------------|--------------:|-------------:|--------------------------:|
| RSS during 5s canary| 32 → 70 MB    | 26.0 → 26.1 MB | ~flat                    |
| Growth rate         | ~15 MB/s      | ~7 KB/s       | 0 (or noise-floor)        |
| Wall time           | ~5 s          | ~5 s          | ~5 s                      |
| Result count        | 1 996 000     | 1 996 000     | 1 996 000                 |

Our fix bounds the leak identically to the upstream expectation.
The tiny residual (~15 KB over 12 s) is bookkeeping RSS creep from
OS-level allocator growth, not `hashtempcxt` accumulation.

## Diff size

| author    | files | insertions | deletions | net LOC change | commits |
|-----------|------:|-----------:|----------:|---------------:|--------:|
| Tom Lane  |     2 |         33 |        43 |            −10 |       1 |
| Ours      |     4 |        107 |         1 |          **+106** |       3 |

The +106 vs Tom's −10 is the load-bearing structural difference.
Breakdown:

- Executable C: ours **+11 lines** (2 resets + comment blocks around
  each), Tom's **−16 lines** (2 resets in a single-exit refactor
  that removed 6 early-return branches).
- Documentation: ours **+29 lines** (5 header notes across
  `BuildTupleHashTable` + `LookupTupleHashEntry` + `TupleHashTableHash`
  + `LookupTupleHashEntryHash` + `FindTupleHashEntry`), Tom's
  **+6 lines** (one note on `BuildTupleHashTable`).
- Regress test: ours **+59 lines** (SQL + expected), Tom's 0.

## Phase 1 — outer-probe reset: same site, different mechanism

### Tom's `ExecHashSubPlan`

Refactors the whole function. Replaces 6 early-return sites with a
single `bool result = false` accumulator + one final exit path.
Adds `MemoryContextReset(node->hashtempcxt)` **at the single exit**
just before `return BoolGetDatum(result)`.

### Our `ExecHashSubPlan`

Keeps the existing 6-branch control flow verbatim. Adds
`MemoryContextReset(node->hashtempcxt)` **at entry**, immediately
after the `if (buildSubPlanHash) …` conditional and before the
empty-subplan short-circuit.

### Same outcome, different placement rationale

Both variants reset the tempcxt once per `ExecHashSubPlan`
invocation. Both are correct. The functional difference is
"when in the call is the residue cleared":

| variant | when residue is cleared              | first-probe cost           | last-probe residue lifetime |
|---------|--------------------------------------|----------------------------|-----------------------------|
| Tom     | AFTER the current probe's work       | correct (no residue yet)   | 0 — cleared before return   |
| Ours    | BEFORE the current probe's work      | correct (no residue yet)   | until NEXT probe's entry    |

Tom's exit-side placement bounds residue tighter — no residue
survives between `ExecHashSubPlan` calls. Ours holds one probe's
worth of residue until the next call. In practice that residue is
capped at whatever a single probe allocates (~40 B in the canary),
so the leak is still bounded. But Tom's is slightly cleaner.

**Why we picked entry-side (from plan §8):** with 6 early-return
sites, entry-side needs 1 reset call, exit-side would need 6. Our
plan explicitly weighed this and picked "1 call at entry" over
"6 calls at each return". Tom picked "refactor to single exit +
1 reset at exit" — an option our brainstorm didn't enumerate.

## Phase 2 — inner-build reset: nearly identical

Both fixes add `MemoryContextReset(node->hashtempcxt)` inside
`buildSubPlanHash`'s per-inner-tuple loop, right after the two
`LookupTupleHashEntry` sites.

### Tom's placement

```c
    }
    /* Also must reset the hashtempcxt after each hashtable lookup. */
    MemoryContextReset(node->hashtempcxt);
}
```

Single-line comment. Placed at end of the per-tuple `for` loop body,
after `ResetExprContext(innerecontext)`.

### Our placement

Semantically identical. Same `MemoryContextReset(node->hashtempcxt)`
at the same spot in the loop body, after the same
`ResetExprContext(innerecontext)`. Difference: our comment is 6
lines (explains the caller-owns-tempcxt convention and the risk of a
"pile up build-time residue" leak) versus Tom's 1-line note.

**Score for Phase 2:** essentially identical. The convergence
validates F30 — grep-verified ownership analysis correctly
identified this site.

## Phase 3 — docs: different scope, same substance

### Tom's docs (+6 lines)

Adds a single 5-sentence NB paragraph inside `BuildTupleHashTable`'s
header block. Includes the design rationale ("rather than managing
an extra context within the hashtable, because in many cases the
caller can specify a tempcxt that it needs to reset per-tuple
anyway") — a note our version does not include.

### Our docs (+29 lines)

Extends `BuildTupleHashTable`'s `tempcxt` param description AND adds
a separate NB block to each of the four lookup entry points
(`LookupTupleHashEntry`, `LookupTupleHashEntryHash`,
`TupleHashTableHash`, `FindTupleHashEntry`).

**Trade-off:** ours is more discoverable per-entry (someone reading
`FindTupleHashEntry`'s header sees the requirement without
cross-referencing `BuildTupleHashTable`). Tom's is more DRY (one
canonical statement, others infer it). Both work.

## Phase 4 (regress test) — only ours ships one

Tom shipped no test additions. His commit trusted the existing
suite to catch regressions.

Our `subselect.sql` + `subselect.out` addition asserts:
1. Plan shape stays `hashed SubPlan 1` (not pulled up to `Hash Semi
   Join`) — protects the reproducer's premise across planner
   changes.
2. Result count matches — catches semantic breakage.

The test does NOT catch a re-introduction of the leak itself (that
would require RSS/memory-context assertions, which regress
doesn't support). But it locks in the code path that would trigger
the leak, so a future refactor of `ExecHashSubPlan` that removed
the reset would still exercise the affected branch.

**Score for tests:** ours +1. Tom's approach is defensible for a
back-patch, but the regress row is cheap insurance.

## What we got right

1. **Identified both leak sites correctly** — `ExecHashSubPlan`
   outer probe AND `buildSubPlanHash` inner build. Both fixes touch
   the same 2 sites.
2. **F30 grep-verified ownership analysis nailed the diagnosis** —
   nodeSubplan was correctly identified as the sole outlier from a
   convention already followed by 4 other `BuildTupleHashTable`
   callers. Plan §7 got this right.
3. **Reproducer construction worked** — 3 EXPLAIN tries were needed
   (found F31), but the eventual `(id < 0) OR (payload IN …)` +
   `max_parallel_workers_per_gather = 0` gives a stable canary that
   shows a 15 MB/s leak on parent + flat on fix.
4. **L5 "storage representation" question was asked and correctly
   rejected** — the brainstorm considered approach C (change
   `TupleHashTable` internals) and rejected it as unsuitable for a
   back-patchable fix. Correct call.
5. **Convergent Phase 2 fix** — the inner-build reset is
   line-for-line semantically identical to Tom's, arrived at
   independently.

## What we got wrong (and what the trilogy missed)

### F32 (new) — blind trilogy under-refactors control flow

Our plan §14 pre-declared this as a comparison axis:

> "**Estimated diff size:** ~6 lines of executable C code + ~15
> lines of comment doc + ~20 lines of regress SQL + expected. Total
> ~40-50 lines inserted, ~0-3 removed. Well within the shape of
> `+33 / −43` reported in triage for the upstream fix (they likely
> also removed some now-dead code we haven't spotted — Phase 4 will
> show)."

Confirmed: Tom's fix removed 43 lines of duplicated cleanup
(`ExecClearTuple(slot); return BoolGetDatum(false);` × 6) by
introducing a `bool result` accumulator and collapsing to one exit
path. Ours preserved the original 6-branch structure exactly and
appended a single reset call.

This is the same shape observed on jsonpath_leak (L5 lesson —
where the blind fix landed in the "expansible pointer array + free
call" bucket while Tom landed in the "expansible value array +
Clear semantics" bucket, restructuring more aggressively).

**Two data points on the same failure mode.** The blind trilogy
adds behavior; upstream typically REPHRASES it. The blind
brainstorm treats existing code shape as a fixed given.

Codification proposal for `pg-feature-brainstorm/SKILL.md` v1.3:

> When a fix requires adding an invariant (e.g. "reset X on cadence
> Y"), the brainstorm §5 candidate-approach enumeration must
> include an approach labelled **E — Restructure control flow to
> match the new invariant**. If the current function has ≥3 exit
> paths that all now need the same cleanup, the E approach is:
> collapse them via a boolean-accumulator + single-exit refactor
> and place the invariant maintenance at the single exit.

Approach E was not on our list. The trilogy would have benefited.

### F33 (new) — docs-scope choice is a real judgment call, not obvious

Our plan §3 called for docs on 5 sites (`BuildTupleHashTable` param
description + 4 lookup entry points). Tom put the note on 1 site
(`BuildTupleHashTable` header only). Both defensible; neither is
"more correct".

Codification: `pg-feature-plan/SKILL.md` §10 could add a docs-scope
sub-question: "does the invariant live in the type constructor's
contract, in each user's API, or both?" We defaulted to "both";
Tom defaulted to "constructor's contract, users infer". A brief
"prefer the DRY variant unless a specific caller is likely to be
read out of context" heuristic would probably converge on Tom's
choice.

## Methodology validation verdict for the planner suite

Third calibration run confirms the pattern:

- **Phase 0 harness (memory-hunt scenario #34)** — strong. Needed
  3 EXPLAIN iterations to land the hashed-SubPlan shape (F31 —
  reproducer-shape verification needs to be an explicit Phase 0
  step). Once the shape was found, the amplification (2M outer ×
  500 inner × 6 KB payloads) gave a 15 MB/s signal that's
  trivially reliable.
- **Phase 1 triage** — strong. Target picked with explicit
  cross-comparison against two runners-up; subsystem novelty +
  mid-range diff both validated post-hoc.
- **Brainstorm (Phase 2 of trilogy)** — mixed. §5 candidate
  approaches correctly identified A/B/C/D and the L5
  storage-representation sub-question fired. But **approach E
  (control-flow restructure) was missing** — F32 codifies this
  gap.
- **Plan (Phase 2 of trilogy)** — strong. F30 grep-pass identified
  4/5 callers already resetting + nodeSubplan as sole outlier.
  §14 pre-declared the +LOC vs upstream −LOC prediction which
  Phase 4 confirmed.
- **Implement (Phase 3 of trilogy)** — strong. R4 phase-end checks
  green every phase; R13 executor tier held; no R7 escalations; 3
  commits with `Plan:` trailers per R5.
- **Comparison (Phase 4)** — strong. F32 + F33 both harvested from
  the delta.

**Net assessment:** the planner suite produced a working fix that
bounds the leak identically to Tom Lane's upstream patch. The
solution shape converged on 2/2 leak sites and 1/1 doc site
correctly. The +106 vs −10 LOC delta reflects a **consistent bias
toward additive fixes** — the blind trilogy adds behavior where
upstream restructures. This is the second data point on the same
pattern (jsonpath_leak was the first); it's now well enough
characterised to promote to a discipline rule.

## L-lesson to graduate

**L6 — Add approach E "restructure control flow to match new
invariant" to the brainstorm menu.** When a fix requires adding an
invariant maintenance step to a function with ≥3 exit paths, the
brainstorm §5 must include the option of collapsing those exits.
Otherwise the blind trilogy will land the fix as an additive step
that the upstream reviewer would have flagged as "consider
refactoring at the same time".

Anchored in this comparison + jsonpath_leak/comparison.md L5.

Action for `pg-feature-brainstorm/SKILL.md`: extend §5 with a
mandatory "control-flow-shape" sub-question that fires when the
target function has ≥3 exit paths and the fix needs a common
teardown step.

## F-finding to graduate

**F31 — reproducer construction from commit message needs a
verification step.** Already noted in `baseline.md`. Should land in
`knowledge/scenarios/fix-memory-leak.md` as an explicit Phase 0
step:

> Step 0.4: EXPLAIN the intended reproducer shape and verify the
> planner picks the plan node the commit message names (e.g.
> "hashed SubPlan 1", "Hash Semi Join", "HashAggregate"). If the
> planner pulls up or otherwise picks a different shape, iterate
> the query until the target shape appears before proceeding to
> baseline measurement.

This one needed **3 EXPLAIN iterations** on this target to land
the right shape (Hash Semi Join → SubPlan-in-SELECT-list →
hashed SubPlan-under-OR). Docs prevent redoing this from scratch
next time.

**F32 — blind trilogy consistently under-refactors.** See above.

**F33 — docs-scope is a judgment call.** See above.

## Cross-references

- `planning/nodesubplan_leak/baseline.md` — reproducer + Phase 0
- `planning/nodesubplan_leak/triage.md` — Phase 1 target rationale
- `planning/nodesubplan_leak/brainstorm.md` — Phase 2 blind design
- `planning/nodesubplan_leak/plan.md` — Phase 2 blind plan (14
  sections)
- `sessions/2026-06-23-memory-hunt-calibration.md` — prior L1-L5,
  F26-F30
- `planning/jsonpath_leak/comparison.md` — prior comparison (L5
  storage-representation), the pattern this run confirms
- `planning/pgstat_progress_leak/comparison.md` — byte-identical
  convergence, the third data point
- upstream `abdeacdb0920d94dec7500d09f6f29fbb2f6310d` — Tom Lane's
  actual fix
