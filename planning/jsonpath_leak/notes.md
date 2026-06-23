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

## Phase 2 — audit + free at all 15 transient sites

- **Status:** done.
- **Commit:** `6510b8a1e2d` on `feature_jsonpath_leak`.
- **Title:** *jsonpath: stop transient predicate-eval lists from leaking quadratically*
- **Test scope:** pre-commit hook ran `--suite regress` (243 subtests
  clean).  Full R13 executor tier independently run before commit:
  385 subtests (setup + regress + isolation + pg_stat_statements),
  zero diff vs parent.
- **TC-LB-1 harness verification:**
  `planning/memory-hunt/container/inside-jsonpath.sh` against the
  Phase 2 source ran with **peak backend RSS = 32,272 KB (32 MB),
  flat for the full 31s probe window**.  Identical envelope to Tom
  Lane's actual fix at `5a2043bf713` (32,160 KB).  177× memory
  reduction vs parent's 5,686,688 KB.  The trilogy's blind path
  reached the same outcome via a different mechanism.
- **What changed (one line per site):**
  - `executePredicate()` — wrapped entire predicate eval (both
    operand executions and the cross-product comparison) in a
    short-lived `AllocSetContext`.  All `lseq`/`rseq` `values[]`
    arrays AND the JsonbValue structs they hold via
    copyJsonbValue() get released in one `MemoryContextDelete`.
    No `JsonValueListFree` calls needed inside — the context
    cleans up.  **This is the dominant leak fix.**
  - `executeBinaryArithmExpr()` — single-exit refactor with
    `goto cleanup` → `JsonValueListFree(&lseq)` +
    `JsonValueListFree(&rseq)`.  Local `lval` → `jbv` rename
    so the final output JsonbValue isn't shadowed.
  - `executeUnaryArithmExpr()` — added `JsonValueListFree(&seq)`
    before every return path (3 paths).
  - `executeItemOptUnwrapResult()` unwrap branch — added
    `JsonValueListFree(&seq)` at both exit paths (error + success).
  - `executeBoolItem()` `jpiExists` strict-mode branch — added
    `JsonValueListFree(&vals)` at both exits.
  - `executeJsonPath()` strict-mode branch — added
    `JsonValueListFree(&vals)` at both exits.
  - `getArrayIndex()` — added `JsonValueListFree(&found)` at all
    return paths (3 paths, including the RETURN_ERROR macro path).
  - `jsonb_path_match_internal()` — `JsonValueListFree(&found)`
    before each `PG_RETURN_*` macro.
  - `jsonb_path_query_internal()` SRF — `JsonValueListFree(&found)`
    after `JsonValueListGetList()` materializes the user_fctx list.
  - `jsonb_path_query_array_internal()` — `JsonValueListFree(&found)`
    after `wrapItemsInArray` produces the output Jsonb.
  - `jsonb_path_query_first_internal()` — `JsonValueListFree(&found)`
    at both branches.
  - `JsonPathQuery()` — `JsonValueListFree(&found)` before each of
    the 5 return paths.
  - `JsonPathValue()` — `JsonValueListFree(&found)` before each of
    the return / ereport paths (4 paths).  Note: `res` is read
    from the list head BEFORE Free; the JsonbValue itself lives in
    the outer context so the pointer remains valid post-Free.
- **Surprises / drift:**
  - **R7 tier-1 escalation: ownership invariant in plan §7 was
    wrong.**  The plan said `JsonValueListFree` only releases the
    `values[]` array, not the JsonbValue elements -- with the
    justification that elements come from the input jsonb (binary
    view).  But in fact `executeAnyItem` calls
    `JsonValueListAppend(found, copyJsonbValue(&v))` which palloc's
    a fresh JsonbValue for EVERY appended item, in the surrounding
    CurrentMemoryContext.  At 10000 elements × 10000 iterations ×
    ~50 B/JsonbValue, that's the dominant ~5 GB of leaked memory.
    Just freeing values[] (the ~80 KB pointer array per call)
    drops the leak from 6 GB to 4.9 GB -- still way over budget.
    Two recovery paths considered: (a) extend `JsonValueListFree`
    to pfree elements too -- breaks the mixed-ownership site at
    `JsonValueListAppend(found, item)` (line 1776 area) which
    transfers borrowed pointers from one list iterator to another;
    (b) per-call MemoryContext at the hot site.  Picked (b) -- it
    sidesteps ownership tracking entirely and gives the same
    32 MB envelope as Tom Lane's actual fix.
  - **Plan §8 Phase 1 "lands TC-LB-1" claim was wrong** -- struct
    redesign alone reduces per-list overhead 7-8× but doesn't fix
    the leak.  TC-LB-1 lands in Phase 2 instead.  Already noted
    in Phase 1's notes section above.
- **What this phase did NOT do:**
  - Did not add the regress test rows.  That's Phase 3.
  - Did not consult Tom Lane's `5a2043bf713` source or commit
    message -- blind trilogy constraint still holds.
- **Counts:**
  - 15 transient `JsonValueList` declarations identified at
    pre-Phase-2 line numbers 478, 558, 613, 646, 732, 1751, 1900,
    2052-2053, 2131-2132, 2202, 3483, 3964, 4056.
  - All 15 covered in this phase.  Plus
    `JsonTableResetRowPattern`'s two `Clear` → `Free` rename calls
    from Phase 1 (lines 4306, 4323).  Net 17 sites + struct + 9
    helpers + new Free + 6 caller updates touching one file.
