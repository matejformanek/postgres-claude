# Phase 2 brainstorm — nodesubplan_leak

**Target:** upstream commit `abdeacdb0920d94dec7500d09f6f29fbb2f6310d`
"Fix memory leakage in nodeSubplan.c." (blind: only summary line + triage.md +
baseline.md were read).

**Parent pin:** `9016fa7e3bc` (worktree
`postgresql-dev-feature-nodesubplan-leak`).

**Scope:** patch — not a new feature. The `pg-feature-brainstorm` skill is
adapted: §0 enumerates ownership-boundary sites instead of usage examples; §5
enumerates fix locations instead of syntax choices; §7 is the leak reproducer
instead of a load-bearing SQL row.

---

## §0 Usage surface — every `TupleHashTable*` caller in the tree

Grep pass over `src/backend/executor/`:

```
$ grep -RnE 'BuildTupleHashTable|LookupTupleHashEntry|LookupTupleHashEntryHash|FindTupleHashEntry|TupleHashTableHash\(' \
    dev/src/backend/executor/
```

**Callers of `BuildTupleHashTable`** (5 sites; the `tempcxt` arg passed here is
what must be reset):

| Site                                        | `tempcxt` argument                                        | Who resets it?                                                                    |
|---------------------------------------------|-----------------------------------------------------------|-----------------------------------------------------------------------------------|
| `nodeAgg.c:1527` (`build_hash_table`)       | `aggstate->tmpcontext->ecxt_per_tuple_memory`             | `ResetExprContext(tmpcontext)` per outer tuple in `agg_retrieve_direct` line 2542 |
| `nodeSetOp.c:98` (`build_hash_table`)       | `econtext->ecxt_per_tuple_memory` (ps_ExprContext)        | `ResetExprContext(econtext)` per outer/inner tuple, lines 454 + 491               |
| `nodeRecursiveunion.c:45`                   | `rustate->tempContext` (dedicated AllocSet)               | `MemoryContextReset(node->tempContext)` per lookup, lines 105 + 159               |
| `nodeSubplan.c:539` (`buildSubPlanHash` for main table)      | `node->hashtempcxt`                            | **NOBODY** — leak site #1                                                         |
| `nodeSubplan.c:568` (`buildSubPlanHash` for null table)      | `node->hashtempcxt`                            | **NOBODY** — leak site #1 (same context, shared)                                  |

**Callers of `LookupTupleHashEntry` / `LookupTupleHashEntryHash` /
`FindTupleHashEntry` / `TupleHashTableHash`** (the sites where per-lookup
tempcxt allocation actually happens):

| Site                                                            | Path                       | Preceded / followed by tempcxt reset?                          |
|-----------------------------------------------------------------|----------------------------|----------------------------------------------------------------|
| `nodeAgg.c:2204` (`LookupTupleHashEntry`, `lookup_hash_entries`) | HashAgg outer tuple probe  | Yes — `ResetExprContext(tmpcontext)` in caller's outer loop    |
| `nodeAgg.c:2765` (`LookupTupleHashEntryHash`)                   | HashAgg spill re-load      | Yes — outer loop resets `tmpcontext` per re-loaded tuple       |
| `nodeSetOp.c:438` + `nodeSetOp.c:478` (`LookupTupleHashEntry`)   | outer / inner build probes | Yes — `ResetExprContext(econtext)` lines 454, 491              |
| `nodeRecursiveunion.c:103, 157` (`LookupTupleHashEntry`)        | recursive union probes     | Yes — `MemoryContextReset(node->tempContext)` per lookup       |
| `nodeSubplan.c:160` (`FindTupleHashEntry`, `ExecHashSubPlan`)   | outer-tuple main-table probe   | **NO** — leak site #2                                       |
| `nodeSubplan.c:169` (`findPartialMatch` on `hashnulls`)         | outer-tuple null-table probe   | **NO** — leak site #3                                       |
| `nodeSubplan.c:202, 209` (`findPartialMatch`)                   | LHS-has-nulls fallback         | **NO** — leak site #4 (rare in practice)                    |
| `nodeSubplan.c:631, 636` (`LookupTupleHashEntry` in `buildSubPlanHash`) | per inner tuple insert  | **NO** — leak site #5 (build-phase, not probe)              |

Notes:
- `nodeSubplan.c` has `ResetExprContext(innerecontext)` at line 644 — but that
  resets a DIFFERENT context (`node->innerecontext`, the ExecProject context
  for forming projected tuples from the inner subplan's raw output). It does
  NOT reset the hash tempcxt.
- The parent pin's `MemoryContextReset(node->hashtablecxt)` at line 528 tears
  down the whole hashtable on rescan; it does NOT run per lookup.

**Load-bearing site (R15a):** the leak reproducer is dominated by outer-tuple
probes at **`nodeSubplan.c:160` (`FindTupleHashEntry` in `ExecHashSubPlan`)**.
This is the site executed 2 000 000 times in the reproducer; each call runs
the hash + eq machinery in `hashtempcxt` and leaves per-call detoast / palloc
crumbs behind. If we fix ONLY this site + the hashnulls-probe at line 169, the
reproducer's RSS becomes bounded.

The build-phase leak at line 631 is real but bounded (fires 500 times in the
reproducer, once per row of `t_probe`); it does not by itself amplify. But it
still leaks per-inner-tuple during larger inner scans and must be fixed for the
API contract to be consistent.

---

## §0.5 Existing-mechanism survey — how do adjacent callers reset a tempcxt?

Three patterns are visible in the tree, all doing the same thing under
slightly different clothing:

1. **`ResetExprContext(econtext)`** — used when the tempcxt is
   `econtext->ecxt_per_tuple_memory` of some `ExprContext`.
   - `nodeAgg.c:2542` — `ResetExprContext(tmpcontext)` after each outer tuple
   - `nodeSetOp.c:454, 491` — `ResetExprContext(econtext)` after each lookup
   Uses macro `ResetExprContext` from `executor.h:551`:
   ```
   #define ResetExprContext(econtext) \
       MemoryContextReset((econtext)->ecxt_per_tuple_memory)
   ```

2. **`MemoryContextReset(tempcxt)`** — used when the tempcxt is a
   dedicated `AllocSetContext` not tied to an `ExprContext`.
   - `nodeRecursiveunion.c:105, 159` — `MemoryContextReset(node->tempContext)`
   - `execGrouping.c:687` (in `execTuplesUnequal`) — `MemoryContextReset(evalContext)`

3. **Loop-invariant reset before entering the hash routine**, seen in the
   old `execTuplesUnequal` at line 687: the routine resets `evalContext` at
   entry, then does its work. This is a "callee owns the reset" pattern.

`node->hashtempcxt` in `nodeSubplan.c` is created at
`nodeSubplan.c:918-921` as a dedicated `AllocSet` (not tied to an
`ExprContext`), so pattern (2) — `MemoryContextReset(node->hashtempcxt)` — is
the natural fit.

**Cross-check from `knowledge/idioms/memory-contexts.md`:** the canonical
short-lived-work pattern in PG is (a) create a dedicated tempcxt at setup
time, (b) allocate per-work-unit inside it, (c) reset at the end of each
work-unit. The reset is CHEAP because AllocSet holds onto its first
keeper-block. Frequency of reset is a tuning knob — resetting after every
call is fine; batching resets across N calls is a micro-optimization that
doesn't apply here (the leak is per-call, not per-batch).

---

## §1 Problem statement

Under the reproducer (see `baseline.md`), a hashed `SubPlan` evaluates
`FindTupleHashEntry` on a 6.4 KB TOAST'd `text` key on every outer tuple. The
hash function machinery (attribute detoast + hash + eq via the ExprState) runs
in `node->hashtempcxt`, which is intended as a short-lived scratch context.
But nothing resets `hashtempcxt` between probes — so its allocations
accumulate for the duration of the query, growing linearly with the number of
outer tuples probed. Backend RSS rises from ~32 MB to ~70 MB over 2 M rows in
~5 s (~15 MB/s), and is only released when `ExecutorState` tears down at
query end. Not a permanent leak, but a query-scoped one large enough to OOM
long-running or high-concurrency workloads.

The same accumulation happens in `buildSubPlanHash` on the inner-tuple
loop, though bounded by inner cardinality.

The invariant that OTHER `TupleHashTable*` callers rely on — that the caller
resets `tempcxt` between lookups — is silently violated by `nodeSubplan.c`.

---

## §2 Scope contract

### IN scope

- `src/backend/executor/nodeSubplan.c`:
  - `ExecHashSubPlan` (outer probe path, ~lines 100-217).
  - `buildSubPlanHash` (inner build path, ~lines 495-657).
- `src/backend/executor/execGrouping.c`:
  - Header comments on `LookupTupleHashEntry`, `LookupTupleHashEntryHash`,
    `FindTupleHashEntry`, `TupleHashTableHash` (~lines 279-403) — document
    the "caller owns the tempcxt reset" contract explicitly.
  - `BuildTupleHashTable` header (line 135-160) — same doc.
- A regression test that exercises the fix. The reproducer is too heavy for
  the check-world suite (2M rows, ~5 s); a scaled-down variant belongs in
  `src/test/regress/sql/subselect.sql`.

### OUT of scope

- The four already-correct callers (`nodeAgg.c`, `nodeSetOp.c`,
  `nodeRecursiveunion.c`, HashAgg spill re-load). We VERIFY they're
  correct in F30 §7 and leave them alone.
- `simplehash.h` internals — the leak is above that layer.
- `execExprInterp.c` hash-function dispatch — the machinery is correct;
  what's broken is the memory-management contract around the machinery.
- Any change to the hash / eq ExprState building path
  (`ExecBuildHash32FromAttrs`, `ExecBuildGroupingEqual`).
- Parallel workers (the reproducer forces serial via
  `max_parallel_workers_per_gather = 0`; parallel path doesn't add
  anything relevant since each worker has its own SubPlanState).

### Blind constraint (Phase 3 hook)

Everything below is arrived at from the corpus + parent-pin source ONLY.
`abdeacdb092`'s file contents, commit-message body, and Bug #19040 thread
are OFF-LIMITS through end of Phase 3.

---

## §5 Candidate approaches

### Approach A — reset inside `TupleHashTableMatch` / `TupleHashTableHash_internal`

Push the reset DOWN into `execGrouping.c` so that
`TupleHashTableHash_internal` and/or `TupleHashTableMatch` reset the tempcxt
themselves (either on entry or on exit). Makes the routines "self-cleaning";
callers stop being responsible.

**Pros:**
- Fixes ALL callers at once — no per-caller edit needed.
- Impossible to forget on future callers.
- Simplest single-site change (one `MemoryContextReset` inside each
  routine's context switch).

**Cons:**
- Changes contract for the FOUR already-correct callers who reset
  `tempcxt` themselves in a different rhythm (e.g. `nodeSetOp.c` resets
  the whole `econtext` for reasons beyond just the hash table; that
  reset also frees other econtext-scoped memory the caller uses). If
  the routine resets `tempcxt` too, those callers are now
  double-resetting — probably harmless but wasteful and confusing.
- If `TupleHashTableMatch` is called MULTIPLE times per
  `LookupTupleHashEntry` (hash collision on non-empty bucket), resetting
  inside `TupleHashTableMatch` would free memory an in-progress match
  is still holding (the very tuple being compared may have been detoasted
  into that context). **Dangerous.**
- Resetting on entry to `LookupTupleHashEntry` would work — but that's
  the caller's ADT boundary anyway, so functionally it's the same as
  approach B without the flexibility.
- Breaks the pattern where callers can amortize resets over N lookups
  (nobody does this today, but nodeAgg's outer-loop reset is a real
  batching pattern we shouldn't preclude).

**Blast radius:** 2 files (execGrouping.c core + a compensating comment
update in every caller). Test impact: every hashing suite needs to
re-verify. **Medium-high.**

**R14 test-suite implication:** need to add tests that verify the
routine actually resets — hard to observe without a memory-tracking
hook. Would rely on the leak reproducer itself as regression.

**Verdict:** rejected. The "reset in the callee" design is subtly wrong
for hash collision cases and breaks the amortization affordance.

### Approach B — reset in each `nodeSubplan.c` caller (align with existing convention)

Add `MemoryContextReset(node->hashtempcxt)` calls at the three
per-tuple probe/insert points in `nodeSubplan.c`:
1. In `ExecHashSubPlan` after the main-table `FindTupleHashEntry` and
   `findPartialMatch` calls (~line 217 area, before return).
2. In `buildSubPlanHash` after each `LookupTupleHashEntry`
   (~lines 632, 637).

Update the `execGrouping.c` header comments on `LookupTupleHashEntry` and
friends to document the "caller resets tempcxt" contract explicitly.

**Pros:**
- Matches the existing convention that ALL other `TupleHashTable*`
  callers already follow (nodeAgg, nodeSetOp, nodeRecursiveunion).
- Preserves the batching affordance — a caller with N cheap lookups per
  outer tuple can still reset once per batch.
- Local — no risk of surprise to the other four callers.
- Small diff — 4-6 lines of code + ~20 lines of comment doc updates.
- The API contract change is DOCUMENTED, not just implied; future
  callers cargo-cult from the docs, not from adjacent files.

**Cons:**
- Future callers may still forget. Mitigated by (a) the caller-side
  pattern being cargo-cult-visible in every existing caller and
  (b) the `execGrouping.c` header now saying it explicitly.
- If someone adds a NEW `LookupTupleHashEntry` site to `nodeSubplan.c`
  and forgets, the leak reappears. But that's true of any caller-owns
  contract; static analysis would catch it before commit.

**Blast radius:** 2 files, 4-6 new lines of executable code +
documentation. **Small.**

**R14 test-suite implication:** need a regression test that runs the
reproducer at reduced scale (say 50 k outer rows) with
`pg_backend_memory_contexts()` snapshotting `Subplan HashTable Temp
Context` before and after the query and asserting the running-total
stays below some cap. Alternatively (simpler): rely on the RSS-based
harness in Phase 3 and add a regress row that just runs a hashed
SubPlan on a wide TOAST'd key — that catches the shape without
needing memory instrumentation.

**Verdict:** RECOMMENDED. See §6.

### Approach C — change the storage representation entirely

Rework `TupleHashTable` so that hash + eq functions do NOT allocate
transient memory. Options:

- **C1 — Inline detoast into the tuple slot.** Change the caller
  contract so the LHS tuple's varlena attributes are already detoasted
  in place, in the caller's slot memory. Hash functions then see
  in-line values, no palloc.
- **C2 — Reference-count shared pool.** Give `TupleHashTable` a
  reference-counted pool of detoasted values; each lookup checks in,
  each `ResetTupleHashTable` decref-clears. Complex and probably
  slower.
- **C3 — Per-lookup arena stack.** Give each `LookupTupleHash*` call
  an on-stack `AllocSetContext` created + destroyed per-call. Simple
  but allocator overhead per-call may dominate.
- **C4 — Redesign to avoid the tempcxt entirely.** Have the hash /
  eq ExprState allocate into `CurrentMemoryContext` and trust the
  caller's per-tuple context to be reset by higher levels
  (`ExecEvalExpr`'s usual per-tuple discipline). This just DELETES the
  `tempcxt` field.

**L5 mandatory sub-question — storage representation: by-value inline,
by-pointer, or by-reference-to-shared-pool?**

- **By-value inline (C1):** matches lifetime perfectly (data lives in
  caller's slot for the duration of the lookup, no separate context
  needed). But: forcing pre-detoast at the caller layer is an
  invasive callee-to-caller inversion; it duplicates logic that
  currently lives inside the hash-function fmgr calls
  (`hashvarlena` etc. detoast on demand). And "inline" in a
  MinimalTuple means storing the detoasted bytes back into the tuple
  slot's owner memory — which for outer probes is the parent's
  `ecxt_per_tuple_memory`, so it's essentially approach B with extra
  steps.
- **By-pointer with dedicated tempcxt (status quo + reset):** matches
  lifetime as long as the reset fires at the right cadence. This IS
  approach B.
- **By-reference-to-shared-pool (C2):** matches the "table entries live
  for the hash-table lifetime" case but is a POOR fit for
  per-lookup transient allocations, which are the actual leak. A pool
  would just accumulate references and defer the reset by one level
  of indirection. Wrong lifetime match.

**Verdict on L5:** by-pointer with dedicated tempcxt + explicit
per-lookup reset (approach B) matches the actual lifetime requirement
best. Inline (C1) would work in principle but is a much larger
refactor for zero perf gain over B. Shared-pool (C2) mismatches
lifetime.

**Pros of C overall:**
- Would definitively kill the class of leak.
- Might expose other hidden assumptions worth fixing.

**Cons of C overall:**
- Massive diff. Touches at least `execGrouping.c`, `execExpr.c` (hash
  ExprState codegen), `nodeAgg.c`, `nodeSetOp.c`,
  `nodeRecursiveunion.c`, `nodeSubplan.c`, `simplehash.h` template
  usage. Regression-test blast radius covers ALL hashing.
- No performance win — the tempcxt reset in approach B is O(1) per
  outer tuple because AllocSet keeps its first block.
- Every reviewer will ask "why not just add the reset?" —
  which is exactly approach B.

**Blast radius:** 6+ files, hundreds of lines, cross-cutting API
change. **Very high.**

**R14 test-suite implication:** every hash-table caller needs its own
regression + isolation coverage re-verified. Not a fit for a
back-patch (Bug #19040 explicitly wants a backport to PG13 per triage).

**Verdict:** rejected. Right idea for a green-field design; wrong idea
for a leak fix that must back-patch cleanly to PG13.

### Approach D — reference-count on `TupleHashEntry` with lazy free

Attach a reference count to each `TupleHashEntry` that tracks whether
any outer-tuple probe is still using detoasted values pointed to from
the entry; free lazily when the count drops to zero.

**Pros:**
- Would work for cases where entry-referenced data outlives the
  entry itself.

**Cons:**
- Solves a problem we don't have. The leak isn't in entry data — it's
  in the per-lookup TRANSIENT allocation (LHS detoast, hash function
  scratch). Reference counts don't help.
- Complexity balloon.

**Verdict:** rejected. Wrong problem.

---

## §6 Recommended approach — B, with F30-verified ownership contract

**Approach B (reset in `nodeSubplan.c` callers, document contract in
`execGrouping.c`)** is the recommendation, on grounds of:

1. **Matches the existing convention.** Four of five `BuildTupleHashTable`
   callers already reset the tempcxt themselves; nodeSubplan is the
   outlier. Aligning it removes a special case rather than adding one.
2. **Smallest diff, safest back-patch.** Bug #19040 is back-patched to
   PG13 per triage; approach B is ~4-6 executable lines plus
   documentation, fits every branch cleanly.
3. **Preserves batching.** Callers can still amortize resets across
   multiple lookups when performance-appropriate.
4. **Documentable contract.** The `execGrouping.c` header updates make
   the "caller owns tempcxt reset" contract explicit, so future
   callers won't repeat this mistake without at least reading past
   the doc.
5. **Passes the L5 test.** Storage-lifetime match: per-lookup
   allocations live for exactly one lookup; a dedicated tempcxt reset
   between lookups is exactly the right lifetime primitive.

Specific edits (details in `plan.md §3`):

- **`nodeSubplan.c ExecHashSubPlan`**: reset `node->hashtempcxt` at
  entry to the probe path, after `buildSubPlanHash` returns (if it
  ran) — before any `FindTupleHashEntry` / `findPartialMatch` calls.
  Or (equivalently) reset AFTER the lookups, before returning. The
  entry-side reset is safer because it also cleans up any prior
  probe's residue; the exit-side reset is symmetric with
  `nodeSetOp.c`. I'll pick entry-side (see §7 rationale).
- **`nodeSubplan.c buildSubPlanHash`**: reset `node->hashtempcxt`
  either after each `LookupTupleHashEntry` (matching nodeSetOp) or
  once at entry (before the loop) — the outer subplan scan runs the
  per-inner-tuple loop, and each lookup runs hash + eq machinery in
  `hashtempcxt`. Per-lookup reset is safer here because inner
  cardinality can be large.
- **`execGrouping.c`**: extend the header comments on
  `BuildTupleHashTable` (line ~135-160), `LookupTupleHashEntry`
  (line ~279-297), `LookupTupleHashEntryHash` (~345-352),
  `FindTupleHashEntry` (~372-385), `TupleHashTableHash` (~323-330)
  with "The caller must reset the tempcxt between calls (or on some
  cadence that keeps it bounded), because hash and equality
  functions allocate transient memory into it."

---

## §7 Load-bearing test — the reproducer

From `baseline.md`:

```sql
CREATE TABLE t_probe (id int, k text);
ALTER TABLE t_probe ALTER COLUMN k SET STORAGE EXTERNAL;
INSERT INTO t_probe SELECT g, repeat(md5(g::text), 200) FROM generate_series(1, 500) g;

CREATE TABLE t_outer (id int, key text);
INSERT INTO t_outer SELECT g, repeat(md5((g % 500)::text), 200) FROM generate_series(1, 2000000) g;
ANALYZE;

SET max_parallel_workers_per_gather = 0;
SELECT count(*) FROM t_outer o
WHERE (o.id < 0) OR (o.key IN (SELECT k FROM t_probe));
```

Verified plan shape (`baseline.md`):

```
 Aggregate
   ->  Seq Scan on t_outer o
         Filter: ((id < 0) OR (ANY (key = (hashed SubPlan 1).col1)))
         SubPlan 1
           ->  Seq Scan on t_probe
```

**Success signal on fix:** backend RSS stays flat at ~32 MB throughout
the query (was 32 MB → 70 MB pre-fix over ~5 s).

**Regression-test scaled variant (proposed for `src/test/regress`):**

```sql
-- Scaled-down leak canary. Runs in <1 s.
BEGIN;
CREATE TEMP TABLE t_probe (id int, k text);
ALTER TABLE t_probe ALTER COLUMN k SET STORAGE EXTERNAL;
INSERT INTO t_probe SELECT g, repeat(md5(g::text), 200) FROM generate_series(1, 50) g;

CREATE TEMP TABLE t_outer (id int, key text);
INSERT INTO t_outer SELECT g, repeat(md5((g % 50)::text), 200) FROM generate_series(1, 50000) g;

SET LOCAL max_parallel_workers_per_gather = 0;

-- Expect: query completes. If leak reintroduced, memory contexts named
-- 'Subplan HashTable Temp Context' would be huge (they're not checked
-- automatically; the shape passes the smoke test).
SELECT count(*) FROM t_outer o
 WHERE (o.id < 0) OR (o.key IN (SELECT k FROM t_probe));
ROLLBACK;
```

This regress row exercises the hashed-SubPlan probe path with wide
TOAST'd keys. It does NOT auto-detect leaks (that would need
`MemoryContextMemAllocated`-based probing not exposed in SQL). It DOES
ensure the code path is walked so any future breakage of the reset
would be visible under valgrind / asan runs on the buildfarm and any
future memory-tracking test infra.

Additional TAP or targeted check: parse `pg_backend_memory_contexts`
mid-query via a second backend to verify the Temp Context size stays
below (say) 1 MB. Optional; may be too flaky for check-world.

---

## §8 Open questions for the plan phase

1. **Entry-side vs exit-side reset in `ExecHashSubPlan`?**
   Exit-side matches nodeSetOp exactly ("reset after lookup"). Entry-side
   is more defensive against a caller path that returns without
   resetting (early-exit branches). Pick one; the plan should decide.
   *Working choice: entry-side, because `ExecHashSubPlan` has ~6
   early-return points and each needs a reset if we go exit-side.*

2. **Reset frequency in `buildSubPlanHash`?**
   Per-inner-tuple reset is the strictly-safe choice. But is
   once-per-buildSubPlanHash-invocation enough? The build path already
   holds one `MemoryContextReset(node->hashtablecxt)` at line 528; that
   reset applies to a DIFFERENT context (table entries). The hashtempcxt
   needs its own cadence. Recommend per-inner-tuple to match
   nodeSetOp / nodeRecursiveunion.

3. **Regress test placement — subselect.sql, or a new sql/subselect_leak.sql?**
   subselect.sql already exists and has hashed-SubPlan tests. Adding
   there keeps the surface small. Plan chooses.

4. **Backport concerns.**
   Triage confirms upstream back-patched through PG13. Our blind fix
   doesn't need to worry about backport (Phase 4 comparison will show
   whether the shape matches theirs). But note: any `execGrouping.c`
   comment additions are safe on all branches; nodeSubplan.c edits
   should apply cleanly if the surrounding code hasn't diverged.

5. **Is there a case where callers rely on hashtempcxt containing
   long-lived data past the lookup?**
   Grep says no — `hashtempcxt` is only used inside
   `LookupTupleHash* / FindTupleHash* / TupleHashTableHash` calls (the
   `MemoryContextSwitchTo(hashtable->tempcxt)` sites in execGrouping.c).
   No caller ever reads memory allocated into it after the routine
   returns. Reset-between-lookups is safe.

6. **Does resetting hashtempcxt free the `hashtable` structure itself?**
   No. `hashtable` lives in `metacxt` (see `BuildTupleHashTable`
   line 192-194: `MemoryContextSwitchTo(metacxt); hashtable = palloc(...)`).
   `hashtempcxt` and `metacxt` are separate. Confirmed by grep on line 200:
   `hashtable->tempcxt = tempcxt` and the caller's own separate storage.

---

## §9 Brainstorm exit

- 5 candidate approaches enumerated (A, B, C1-C4, D).
- L5 storage-representation sub-question fired on approach C.
- F30 grep pass on `TupleHashTable*` callers completed; all 4 other
  callers verified to already reset their tempcxt in their outer loop.
- Load-bearing site named per R15a: `nodeSubplan.c:160`
  `FindTupleHashEntry` in `ExecHashSubPlan`.
- Recommendation: approach B (align nodeSubplan with the existing
  convention; document contract in execGrouping.c).
- Blind constraint respected: no read of `abdeacdb092` sources or
  Bug #19040 thread.
