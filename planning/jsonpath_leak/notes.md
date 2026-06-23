# Notes — jsonpath_leak implementation

## Phase 1 — JsonValueList redesign (struct + 9 helpers + new Free)

- **Status:** done.
- **Commit:** `74cbe74f713` on `feature_jsonpath_leak`
  (worktree `/Users/matej/Work/postgres/postgresql-dev-feature-jsonpath_leak`).
  Branched from parent commit `7724cb9935a96eabba80f5e62ee4b32068967dd2`.
- **Title:** *jsonpath: redesign JsonValueList as an expansible JsonbValue-pointer array*
- **Test scope:** R13 phase-end check via pre-commit hook —
  `PG_PRECOMMIT_SCOPE=regress` (243 subtests pass).  Independently
  verified the broader R13 executor tier (`--suite setup --suite
  regress --suite isolation --suite pg_stat_statements`) at 385
  subtests before commit.  Baseline (parent commit, pre-change) was
  also 385 — zero net diff.
- **What changed (one line per site):**
  - `jsonpath_exec.c:147-151` — struct `JsonValueList` now
    `(singleton, values, n, capacity)` instead of `(singleton, list)`.
  - `jsonpath_exec.c:153-158` — struct `JsonValueListIterator` now
    just `(pos)` instead of `(value, list, next)`.
  - `jsonpath_exec.c:354` — forward decl `JsonValueListClear` →
    `JsonValueListFree`.
  - `jsonpath_exec.c:3525-3596` — rewrote `JsonValueListClear` →
    `JsonValueListFree` (now frees `values[]`), `JsonValueListAppend`,
    `JsonValueListLength`, `JsonValueListIsEmpty`,
    `JsonValueListHead`, `JsonValueListGetList`,
    `JsonValueListInitIterator`, `JsonValueListNext`.  Net ~93/49.
  - `jsonpath_exec.c:4306, 4323` — `JsonTableResetRowPattern`'s
    `JsonValueListClear(&planstate->found)` → `JsonValueListFree(...)`.
    This is the only behavior-visible change: row-refill now actually
    releases the prior row's array (under the old struct that was a
    silent List leak too).
- **Surprises / drift:**
  - **Plan claim "Phase 1 lands TC-LB-1" was incorrect.**  The struct
    redesign reduces per-list overhead from ~60 B/cell to ~8 B/ptr
    (a 7-8× win), but the transient JsonValueLists at
    `executePredicate`, `executeBinaryArithmExpr`, etc. are still
    leaked once per call.  For TC-LB-1 (10K outer iterations ×
    ~80 KB per leaked rseq) that's still ~800 MB peak — well over
    the 100 MB target.  TC-LB-1 actually lands in Phase 2 when the
    explicit `JsonValueListFree` calls go in at the 14 transient
    sites.  R7 tier-1 plan update: TC-LB-1 row moved from Phase 1's
    "tests covered" to Phase 2's.  Phase 1 still passes its R13
    gate (regress + iso + pgss clean) which is the only
    R4-binding condition.
- **What this phase did NOT do:**
  - Did not free transient JsonValueLists at the 14 declaration sites
    (lines 459, 539, 594, 627, 713, 1732, 1881, 2033, 2034, 2112,
    2113, 2183, 3464, 3920, 4012 in the original numbering).  That's
    Phase 2.
  - Did not add regress test additions.  That's Phase 3.
  - Did not consult Tom Lane's `5a2043bf713` source or commit
    message — blind trilogy constraint holds.
- **Pre-commit hook health (per F23 in meta-repo):** the hook fired
  cleanly with `PG_PRECOMMIT_SCOPE=regress` set — no `skip` override
  needed.  Verified worktree-aware DEV_ROOT detection works on
  `postgresql-dev-feature-jsonpath_leak` per meta commit `d89efca`.
