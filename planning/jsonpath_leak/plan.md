# Plan — fix transient memory leakage in jsonpath evaluation

**Slug:** `jsonpath_leak`
**Brainstorm:** [planning/jsonpath_leak/brainstorm.md](brainstorm.md)
**Approach:** C+A (struct redesign + explicit free) — recommended
locked by user.
**Target version:** PG 19 (current master)
**Source pin (parent of fix):** `7724cb9935a96eabba80f5e62ee4b32068967dd2`
**Comparison commit (Tom Lane's fix, not consulted during planning):**
`5a2043bf713113b0f6e9dbf2046499a5ca67883c`
**Implementation site:** new dev worktree `worktree-jsonpath_leak` off
`7724cb9935a` so the diff stays comparable to Tom Lane's.

## §0 Context

Calibration plan, blind methodology validation. The leak is known
+ fixed upstream; we re-derive a fix without consulting the actual
patch, then compare at Phase 4. Not a thread / CommitFest plan —
**no engagement classification, no REJECT track**.

The reproducer (validated):

```sql
SELECT jsonb_path_query(
  (SELECT jsonb_agg(i) FROM generate_series(1, 10000) i),
  '$[*] ? (@ < $)');
```

Pre-fix backend RSS: 5.7 GB peak. Target post-fix: <100 MB peak,
<5 s wall time. (Tom's fix: 32 MB, 3 s.)

## §1 What this plan is

Replace `JsonValueList`'s `List *list` with a compact, expansible
JsonbValue-pointer array (Approach C from brainstorm), AND add
`JsonValueListFree` calls at every transient call site
(Approach A from brainstorm). Together: kill the per-cell palloc
overhead AND ensure transient lists are released before scope exit.

## §2 Scope contract

**IN scope:**
- Redesign `JsonValueList` struct in
  `src/backend/utils/adt/jsonpath_exec.c:147-151` to use an
  expansible JsonbValue-pointer array, retaining the singleton fast-path.
- Rewrite the 9 helper functions
  (`JsonValueListClear/Append/Length/IsEmpty/Head/GetList/InitIterator/Next`
  plus a new `JsonValueListFree`) at
  `jsonpath_exec.c:3507-3596`.
- Audit all 15 `JsonValueList` declarations in `jsonpath_exec.c`
  (per R15-scope decision: audit-mode, not just the 4 known leak sites).
  Add `JsonValueListFree` at every transient site.
- Comprehensive regression test additions (per R14 + test-scope decision):
  TC-LB-1 (10K reproducer) + N-microbench rows for N ∈ {10, 100, 1000, 10000}.

**OUT of scope:**
- Changing jsonpath semantics or query results.
- The `JsonValueListIterator` data structure beyond what the
  array-backed JsonValueList requires (iter still has value + position).
- Backport to PG 17/18.
- Changing `JsonTablePlanState.found` lifecycle (line 196) — it's a
  long-lived list managed by JSON_TABLE; the struct redesign improves
  its memory footprint automatically, but ownership rules don't
  change in this plan.
- Touching `src/test/regress/expected/jsonb_jsonpath.out` beyond
  adding the new TC rows (no existing-row deltas expected).
- Performance microbenchmark suite beyond TC-LB-1 — those go in a
  follow-up.

## §3 Files that change

| File | Change | Size | Summary |
|------|:------:|:----:|---------|
| `src/backend/utils/adt/jsonpath_exec.c` | modify | medium (~200 lines) | Redesign `JsonValueList` struct (line 147) + 9 helpers (line 3507-3596) + add `JsonValueListFree` calls at 14 transient sites (lines 459, 539, 594, 627, 713, 1732, 1881, 2033-2034, 2112-2113, 2183, 3464, 3920, 4012). |
| `src/test/regress/sql/jsonb_jsonpath.sql` | modify | small (~30 lines) | Add TC-LB-1 (Tom Lane's 10K reproducer wrapped in `SELECT count(*)`) + N ∈ {10, 100, 1000, 10000} microbench rows asserting bounded result-count not memory growth. |
| `src/test/regress/expected/jsonb_jsonpath.out` | modify | small | Expected output for new TC rows (deterministic counts: N, N, N, N for the four sizes). |

**Notes on §3 completeness:**
- `JsonValueList` is `static` in `jsonpath_exec.c` (verified by grep
  across `src/include/` — zero hits). No header / ABI impact.
- `JsonValueListIterator` (line 153) gets minor adjustments to track
  `(values, pos, n)` instead of `(value, list, next)`. Same file.
- `JsonTablePlanState.found` (line 196) keeps its current declared
  type and lifecycle; the struct redesign passes through transparently.

## §4 Catalog + on-disk impact

- New `pg_proc.dat` entries: **no**.
- `catversion.h` bump: **no** (no catalog changes).
- New on-disk format: **no**.
- `genbki.pl` re-run: **no**.

## §5 WAL impact

- New rmgr / record types: **no**.
- Existing record extensions: **no**.
- Replay function changes: **no**.
- `pg_waldump` updates: **no**.
- Hot Standby conflict generation: **no**.

## §6 Locking + concurrency

- New LWLock: **no**.
- New heavyweight lock mode: **no**.
- Buffer lock ordering: **no**.
- Atomic-vs-spinlock decisions: **no**.
- SSI predicate-lock implications: **no**.

(JsonPath evaluation is per-backend, in-memory, no shared state.)

## §7 Memory + resource management

This is the meat. The fix's whole point.

- **New MemoryContext?** No — we keep using `CurrentMemoryContext`
  (the surrounding executor context). The fix is per-list, not
  per-context.
- **Per-tuple allocations?** Yes, by definition: transient
  JsonValueLists are populated and freed within a single predicate
  evaluation. The expansible-array design uses one `palloc` for the
  array + the JsonbValue pointers inside; one `pfree` releases the
  array. The `JsonbValue` storage itself is OWNED BY the surrounding
  jsonb (binary view), so we MUST NOT `pfree` the elements — only
  the array of pointers.
- **Singleton fast-path:** if a list contains 0 or 1 element, the
  array isn't allocated at all (kept in the struct's inline storage).
  This matches the existing `singleton` optimization. ~95% of
  jsonpath queries on real data have ≤1 element per intermediate
  list; the singleton path matters.
- **Ownership invariant** (new contract): a `JsonValueList`'s
  `values` array IS OWNED BY the list. JsonbValue elements pointed
  to ARE NOT (they live in the original jsonb or in a separately-
  palloc'd JsonbValue from `copyJsonbValue`). `JsonValueListFree`
  only releases the array.
- **`JsonValueListGetList()` retains compat:** for the (small) set
  of callers needing PG's `List*` API, we materialize on demand via
  `list_make_n`. Cost: O(n) one-shot copy, but only at the boundary.

### Citation chain

- `knowledge/idioms/memory-contexts.md` — general MemoryContext
  hierarchy (touch but don't materially affect).
- `knowledge/idioms/memory-context-allocset-internals.md` — palloc
  cost model (~60 bytes overhead per chunk).
- 2026-06-01 mmgr file-by-file session §F4 — the noted exact-fit
  power-of-two AllocSet gotcha. Not relevant to *this* fix but cited
  to confirm we're not stepping into that landmine.

## §8 Phased implementation

Three phases. Each phase is a single dev/ commit per R5.

### Phase 1 — Redesign JsonValueList struct + helpers (architectural centerpiece, lands TC-LB-1)

- **Files:** `src/backend/utils/adt/jsonpath_exec.c`.
- **Edits:**
  1. Replace the `JsonValueList` struct at line 147 with the
     array-backed form (singleton + values+n+cap inline +
     optional palloc'd array overflow).
  2. Replace `JsonValueListIterator` struct at line 153 with
     `(jvl, pos)` form.
  3. Rewrite `JsonValueListClear` (now `Free` — releases array if
     allocated; resets to empty).
  4. Rewrite `JsonValueListAppend` (grow array doubling cap; first
     append stays in singleton).
  5. Rewrite `JsonValueListLength` (return n).
  6. Rewrite `JsonValueListIsEmpty` (return n == 0 && !singleton).
  7. Rewrite `JsonValueListHead` (return singleton ?: values[0]).
  8. Rewrite `JsonValueListGetList` (materialize List on demand
     via `list_make1`/`list_make_n`).
  9. Rewrite `JsonValueListInitIterator` (set pos = 0).
  10. Rewrite `JsonValueListNext` (return values[pos++]; handle
      singleton).
  11. Add new `JsonValueListFree` (release values array; reset).
- **Phase-end check** (R13 scope: executor / expr → regress + iso +
  pg_stat_statements per R13's executor tier):
  `meson test --suite regress --suite isolation --suite pg_stat_statements --no-rebuild`
  must pass green (with the new TC-LB-1 row included). Plus the
  JSONPath harness from `planning/memory-hunt/container/inside-jsonpath.sh`
  showing TC-LB-1 RSS bounded.
- **Tests covered:** TC-LB-1, TC-N10, TC-N100, TC-N1000, TC-N10000.

This is the architectural centerpiece (R15a). TC-LB-1 must pass
green by the end of Phase 1. Subsequent phases can only fail
TC-LB-1 if they break Phase 1's struct.

### Phase 2 — Audit + free at all 14 transient sites

- **Files:** `src/backend/utils/adt/jsonpath_exec.c`.
- **Edits:** at each of the 14 transient-declaration sites
  (lines 459, 539, 594, 627, 713, 1732, 1881, 2033, 2034, 2112,
  2113, 2183, 3464, 3920, 4012), insert `JsonValueListFree(&...)`
  before the lexical scope exits OR before the function returns.
  Classify each site as transient (free) or result-out-param
  (don't free — caller owns).

  Classification at parent:
  - Lines 459, 539, 594, 627: in `executeJsonPath` /
    `jsonb_path_query_*_internal` — result lists, caller consumes,
    function returns. These are technically owned by the surrounding
    context which gets freed at function return — but per R15-scope
    decision (audit-mode), add explicit `JsonValueListFree` for
    consistency.
  - Lines 713, 1732, 1881: nested transient — explicit free.
  - Lines 2033, 2034 (executePredicate): THE LEAK — explicit free.
  - Lines 2112, 2113 (executeBinaryArithmExpr): same pattern —
    explicit free.
  - Lines 2183, 3464, 3920, 4012: classify on read, free if transient.
- **Phase-end check:** regress + isolation as Phase 1 + harness
  run showing no new leaks for any of the §0 usage-surface rows.
- **Tests covered:** all §0 usage rows pass with bounded RSS.

### Phase 3 — Tests + documentation

- **Files:** `src/test/regress/sql/jsonb_jsonpath.sql`,
  `src/test/regress/expected/jsonb_jsonpath.out`.
- **Edits:**
  1. Append a "memory-bounded predicate evaluation" section to
     `jsonb_jsonpath.sql` with TC-LB-1 (the 10K reproducer wrapped
     in `SELECT count(*) FROM (... )` to materialize) +
     four microbench rows for N ∈ {10, 100, 1000, 10000}.
  2. Add the expected output rows.
- **Phase-end check:** regress passes green; TC-LB-1 wall-time
  < 5 s on the test rig.
- **Tests covered:** the regress test rows themselves are the
  added coverage; they're the test-side artifact of Phases 1-2's
  behavioral guarantee.

## §9 Risks (high-severity unknowns per R15)

1. **JsonbValue ownership.** The new `JsonValueListFree` MUST NOT
   pfree the JsonbValue pointers themselves — they're either owned
   by the input jsonb (binary view) or by a separately-palloc'd
   JsonbValue from `copyJsonbValue`. Misclassifying ownership = UAF
   or double-free. **Mitigation:** sentinel comment block on
   `JsonValueListFree` body documenting the invariant; cassert in
   the implementation that checks values[i] is non-NULL.
2. **JsonTablePlanState.found semantics.** Line 196 declares a
   `JsonValueList found` as struct member. The lifecycle is "fill
   from one jsonpath eval, iterate per row, refill at next call to
   `JsonTableResetRowPattern`." Currently, refill leaks the prior
   list. Our redesigned struct + `JsonValueListFree` in the reset
   path should fix this transparently — but verify
   `JsonTableResetRowPattern` (line 4262) calls `Clear` (now `Free`)
   first.
3. **Iterator semantics across reset.** Some callers init an iterator
   on a list, then call back into executeItem which may APPEND to
   the same list. The new (values, pos) iterator captures `values`
   by reference (since it lives in the JsonValueList struct), so
   appends that grow the array DON'T invalidate the iterator's
   pointer — but they DO change the `n` and may realloc `values`.
   **Mitigation:** iterator must re-read `jvl->values` and `jvl->n`
   on each Next() call; never cache `values` locally.
4. **Singleton-vs-array transitions.** When a list transitions from
   singleton (1 element in inline storage) to array (2+ elements
   in palloc'd buffer), the prior singleton pointer is no longer
   the canonical pointer. Iterator state must transition cleanly.
   **Mitigation:** appendone-then-append helper that handles the
   case, with regress coverage for sizes 0/1/2/3 boundary.
5. **Scope creep into JSON_TABLE.** §3 omits `JsonTableInitOpaque`
   and friends. If Phase 2 audit reveals JSON_TABLE specifically
   needs sites beyond what the struct change handles, this expands
   §3 — that's an R7 tier-1 (small + tightly coupled) inline plan
   update, NOT a re-plan.
6. **Test fragility on slower CI.** Wall-time assertion on TC-LB-1
   ("must complete in < 5s") may flake on slow CI runners. Switch
   to result-count + manual-only timing check rather than asserting
   wall time in regress.

## §10 Sites checklist (R3 R13 ladder)

Tier — executor / expression eval (per R13 ladder).

Phase-end check scope: `--suite regress --suite isolation --suite
pg_stat_statements`. Plus a harness re-run.

## §11 Performance

For TC-LB-1 (10K, full filter `(@ < $)`):
- Pre-fix: 5.7 GB peak, ~60 s wall.
- Target post-fix: <100 MB peak, <5 s wall.
- Tom Lane's actual: 32 MB peak, 3 s wall.

For N=1 (singleton path):
- Must NOT regress vs. parent — singleton fast-path is preserved.
- Microbenchmark: 1000× `SELECT jsonb_path_query('[1]'::jsonb, '$[*] ? (@ > 0)')`
  must take ≤ parent's wall-time × 1.1 (10% noise band).

For N=2-10 (small-array transition):
- Allocation cost: 1 `palloc` for values array (typically cap=4),
  vs. parent's 2-10 `palloc`s for List cells. Net: faster.

## §12 Plan-end gate

After Phase 3 commits land:
- Full `meson test --no-rebuild` clean.
- `git -C dev log --oneline base..HEAD` shows exactly 3 commits,
  each with `Plan: planning/jsonpath_leak/plan.md (phase N: ...)` trailer.
- TC-LB-1 RSS bounded under <100 MB measured via container harness.
- Phase 4 (comparison to Tom Lane's `5a2043bf713`) executes
  separately — see §14.

## §13 Open questions

1. **Iterator stability under append.** If a predicate's `lseq`
   iterator yields a JsonbValue *while* the predicate's
   `executePredicate` recursion appends to `lseq` from within
   `exec(pred, lval, rval, ...)`, the array realloc may move the
   storage. Mitigation in §9.3 — verify against real call patterns.
2. **JsonTable refill leak.** Does the parent leak via
   `JsonTableResetRowPattern` line 4262/4279? Audit during Phase 2.
3. **JsonbValue copyJsonbValue ownership** — many sites call
   `JsonValueListAppend(found, copyJsonbValue(&v))`. The copied
   JsonbValue is palloc'd. If JsonValueList doesn't own it but
   the caller doesn't track it, that's ALSO a leak. Audit:
   are copied JsonbValues tracked anywhere for free, or are
   they implicitly context-freed?

These are flagged for the implementer; answers expected during
Phase 2 audit. If any answer changes the design fundamentally,
escalate per R7.

## §14 Citation chain + comparison hook

**Plan → corpus citations:**
- `knowledge/idioms/memory-contexts.md` for the MemoryContext
  invariants this fix relies on (CurrentMemoryContext is
  per-tuple-ish during executor; explicit free is the standard
  release pattern).
- `knowledge/idioms/memory-context-allocset-internals.md` for the
  per-chunk overhead model that justifies the array-vs-List
  redesign (8 bytes ptr vs ~60 bytes List cell + chunk header).

**Plan → source citations** (all pinned at `7724cb9935a`):
- `source/src/backend/utils/adt/jsonpath_exec.c:147-151` —
  current `JsonValueList` struct.
- `source/src/backend/utils/adt/jsonpath_exec.c:3507-3596` —
  current helpers we replace.
- `source/src/backend/utils/adt/jsonpath_exec.c:2026` —
  `executePredicate` — primary leak site.
- `source/src/backend/utils/adt/jsonpath_exec.c:2106` —
  `executeBinaryArithmExpr` — secondary leak site.

**Phase 4 comparison hook (not executed during planning):**
- After Phase 3 lands, fetch `5a2043bf713`, diff our
  `jsonpath_exec.c` vs. that commit's, write the comparison to
  `planning/jsonpath_leak/comparison.md`. Expected dimensions:
  struct shape (we both end at array-backed), iterator design
  (Tom may have inlined differently), audit completeness (Tom may
  have hit sites we missed or vice versa), test coverage shape.

## Hand-off

Next step: `/pg-implement jsonpath_leak` to execute Phase 1.

Per the blind-trilogy pick, **do NOT consult `5a2043bf713` source
or commit message** during Phases 1-3. Only at Phase 4.
