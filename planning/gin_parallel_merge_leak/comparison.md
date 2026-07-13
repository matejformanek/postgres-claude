# Comparison — our blind fix vs Vinod Sridharan's `1681a70df3d68`

**Date:** 2026-07-13
**Our chain (`feature_gin_parallel_merge_leak`):**
- `4f17ba1aeae` "Reset tmpCtx per ginEntryInsert in _gin_parallel_merge"

**Upstream fix:** `1681a70df3d68b6f9dc82645f97f8d4668edc42f`
(Vinod Sridharan author, Tomas Vondra reviewer + committer,
2025-05-02).

Both branches start from parent `e83a8ae4472`.

## Non-callback validation — L6/L7 stayed silent

**This run was picked from the 2026-07-13 five-run retro's
"recommended next runs" list specifically to validate the
trilogy handles a non-callback fix correctly.** After 3
consecutive callback-heavy runs (nodesubplan, fdw_directmodify,
pgoutput_uaf), there was a risk the trilogy would over-fire
L6 (approach E) and L7 (callback details) on inappropriate
targets.

Brainstorm §5 correctly identified L6 approach-E as **NOT
firing** on this target: `_gin_parallel_merge` has 1 exit path
and the fix is inline switch/reset at 3 call sites, not a
control-flow restructure.

L7 sub-block correctly **NOT fired**: the fix is not
callback-based.

**Verdict: trilogy correctly ignored L6+L7 triggers on this
non-callback target.** No false positives.

## Leak outcome

Both fixes bound the per-ginEntryInsert transient by resetting
`state->tmpCtx` after each call. Both prevent the OOM under
wide-key custom opclasses.

Empirical validation on macOS deferred — the reproducer (1M row
× 3KB keys parallel `CREATE INDEX`) is a multi-minute build; not
run in this session's timebox. R13 phase-end gate was regress
(230 subtests) + isolation (122 subtests), both green.

## Diff comparison

| author  | files | insertions | deletions | net LOC | sites treated |
|---------|------:|-----------:|----------:|--------:|--------------:|
| Vinod   |     1 |         12 |         0 |     +12 |         2 of 3 |
| Ours    |     1 |         17 |         0 |     +17 |         3 of 3 |

**Two structural differences:**

### F40 — coverage of the "final flush" site

Vinod covered the 2 sites INSIDE the `while` loop body (lines
1688, 1714 in parent-pin numbering): the buffer-flush on
`GinBufferCanAddKey` transition, and the buffer-trim on
`GinBufferShouldTrim`. Vinod did NOT wrap the final
`ginEntryInsert` at line 1738, which executes exactly ONCE at
the end of `_gin_parallel_merge` to flush the last key's buffer.

**Rationale for Vinod's minimal choice:** the final flush's
`ginEntryInsert` fires exactly once per index build. Its
allocation is bounded to a single leaf-tuple's-worth of
memory, not scaling with the input. Under the bug conditions
(custom opclass + wide keys) even this single allocation could
be ~KBs, but that's a one-shot leak, released at portal end —
not a scaling leak that OOMs the build.

**We chose to cover it too** for consistency (all 3 sites
treated uniformly). Not wrong, but adds 5 lines to the diff
without addressing a genuine leak-scaling site.

**Codifiable pattern (F40):** distinguish between **scaling
leak sites** (fire N times, leak is O(N)) and **one-shot leak
sites** (fire O(1) times, leak is O(1)). The scaling sites
justify the fix; one-shot sites are "cleanliness at cost of
diff." The trilogy defaulted to uniform coverage; upstream's
minimal-diff style skips one-shot sites for the same overall
outcome.

Codify in `pg-feature-plan/SKILL.md` §7 as a sub-note under
the F30 grep-pass: "categorize each site by fire-count class
(O(1) vs O(N)); the plan should treat only the O(N) sites
unless the O(1) sites carry an independent correctness
concern."

### F41 — oldCtx declaration scope

Vinod declared `MemoryContext oldCtx;` **inside the
`while (…) { … }` loop body**, as a local within the same
block as the switch. We declared it at function-scope top with
the other locals.

Both are legal C. Vinod's is tighter scope; ours reuses one
declaration across all 3 sites.

Tighter-scope decl is idiomatic for a variable used only inside
one block. Function-scope decl is idiomatic for a variable
used across multiple sites. Since we DO use `oldCtx` at all 3
sites, function-scope is a reasonable choice — if we hadn't
covered the third (final-flush) site, tighter scope would have
been cleaner.

**F41 doesn't rise to a codifiable finding** — it's an
implementation-style preference that follows naturally from
F40's coverage-choice question. If the trilogy adopts F40's
"treat only scaling sites" heuristic, the tighter scope
follows.

## Everything else — aligned

- Both used **`state->tmpCtx`** (the existing GinBuildState
  field), not a fresh AllocSetContextCreate. Brainstorm §5
  Approach A vs B — Approach A won on both sides.
- Both used **per-insert reset frequency** (not per-outer-iteration).
- Both used the **switch → insert → switch-back → reset**
  4-step pattern.
- No struct changes.
- No new fields.
- No header changes.

## What we got right

1. **L6 approach-E did NOT fire** on this non-restructure
   target. Trilogy correctly ignored the trigger.
2. **L7 sub-block did NOT fire** on this non-callback target.
   Trilogy correctly ignored the trigger.
3. **F30 grep-pass** identified all 6 `ginEntryInsert` callers
   and correctly diagnosed 3 as the leak sites.
4. **Approach A** (reuse existing `state->tmpCtx`) was picked
   correctly over Approach B (fresh context) — matches Vinod's
   choice.
5. **Per-insert reset frequency** matches the commit message's
   "reset after each insert" recommendation.

## What we got wrong (minor)

- **F40 — uniform coverage vs O(N)-only coverage.** We treated
  all 3 `ginEntryInsert` sites; Vinod treated only the 2 that
  fire O(N) times, skipping the one-shot final flush. Same
  leak-scaling outcome, +5 lines heavier.

## Methodology validation verdict (post 6 runs)

Sixth calibration run — first non-callback fix in the
calibration series since run #3 (nodesubplan_leak). Confirms:

- **The trilogy handles non-callback fixes correctly.** L6
  approach-E did not fire; L7 sub-block did not fire. No
  false-positive over-firing of the newly-codified lessons.
- **F30 grep-pass** identifies the leak site inventory reliably
  across widely different subsystems (executor,
  contrib/postgres_fdw, replication, and now access/gin).
- **Approach A vs B** enumeration surfaces the "reuse existing
  context field" vs "create fresh context" trade-off cleanly.

New finding to graduate:

- **F40 — scaling vs one-shot leak sites.** Distinguish sites
  that fire O(N) times (real leak, worth fixing) from sites
  that fire O(1) times (cleanliness, +LOC). Plan template §7
  (F30 grep-pass) should categorize sites accordingly.
  Anchored in this run's coverage divergence from Vinod's
  minimal diff.

No new L-lessons this run. F40 is a plan-template refinement,
not a methodology change.

## Cross-references

- baseline.md — bug etiology from parent-pin source alone
- triage.md — non-callback target selection rationale
- brainstorm.md — Approach A vs B enumeration
- plan.md — §7 F30 grep-pass identifying 3 vs 6 sites
- Previous retro: `sessions/2026-07-13-five-trilogy-runs-retro.md`
- `pg-feature-plan/SKILL.md` §7 — F30 grep-pass (F40 to be
  appended)
- upstream `1681a70df3d68` — Vinod Sridharan's actual fix
