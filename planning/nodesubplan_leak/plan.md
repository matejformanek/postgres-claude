# Phase 2 plan — nodesubplan_leak

**Target:** upstream commit `abdeacdb0920d94dec7500d09f6f29fbb2f6310d`
"Fix memory leakage in nodeSubplan.c."

**Parent pin:** `9016fa7e3bc` (worktree
`postgresql-dev-feature-nodesubplan-leak`, branch
`feature_nodesubplan_leak`).

**Prior artifacts:** `triage.md`, `baseline.md`, `brainstorm.md`.

**Blind constraint:** upstream fix source, commit body beyond summary, and
Bug #19040 thread are OFF-LIMITS until Phase 4.

**Approach chosen (from brainstorm §6):** approach **B** — reset
`node->hashtempcxt` in the two `nodeSubplan.c` callers per lookup;
document the "caller owns tempcxt reset" contract in `execGrouping.c`.

---

## §0 Load-bearing test — canary the plan anchors on

The Phase 0 harness reproducer (see `baseline.md`):

```sql
CREATE TABLE t_probe (id int, k text);
ALTER TABLE t_probe ALTER COLUMN k SET STORAGE EXTERNAL;
INSERT INTO t_probe SELECT g, repeat(md5(g::text), 200)
   FROM generate_series(1, 500) g;

CREATE TABLE t_outer (id int, key text);
INSERT INTO t_outer SELECT g, repeat(md5((g % 500)::text), 200)
   FROM generate_series(1, 2000000) g;
ANALYZE;
SET max_parallel_workers_per_gather = 0;

SELECT count(*) FROM t_outer o
 WHERE (o.id < 0) OR (o.key IN (SELECT k FROM t_probe));
```

Success: RSS stays flat at ~32 MB during the query (was 32 → 70 MB
pre-fix). Every phase below cites this canary in its exit condition.

---

## §1 Problem statement

`nodeSubplan.c`'s hashed-SubPlan path passes a dedicated tempcxt
(`node->hashtempcxt`, created at `nodeSubplan.c:918-921`) as the
`tempcxt` argument to `BuildTupleHashTable` (call sites
`nodeSubplan.c:539` and `nodeSubplan.c:568`). The intent is that all
per-lookup hash-function + equality-function transient allocations
land in `hashtempcxt`. But nothing ever resets `hashtempcxt` — its
`MemoryContextReset` is not called anywhere in the file. Consequence:
per-lookup detoast copies and hash scratch accumulate for the
duration of the query, growing linearly with the number of outer
probes.

All FOUR other `BuildTupleHashTable` callers already reset their
tempcxt between lookups (F30 §7). `nodeSubplan.c` is the outlier.

---

## §2 Design

Two symmetric fixes plus a documentation update:

- **Fix 1 (probe path):** In `ExecHashSubPlan`, reset
  `node->hashtempcxt` on entry to the probe body, after any
  `buildSubPlanHash` initial-build (so the build-side's own resets
  don't stomp on outer-tuple state).
- **Fix 2 (build path):** In `buildSubPlanHash`, reset
  `node->hashtempcxt` after each `LookupTupleHashEntry` call on the
  inner-tuple loop.
- **Fix 3 (documentation):** In `execGrouping.c`, extend the header
  comments on `BuildTupleHashTable`, `LookupTupleHashEntry`,
  `LookupTupleHashEntryHash`, `TupleHashTableHash`, and
  `FindTupleHashEntry` to state explicitly: "The caller is
  responsible for resetting the tempcxt between calls (or on some
  cadence that keeps it bounded), because the hash and equality
  functions may allocate transient memory into it."

---

## §3 Files that change — at parent pin `9016fa7e3bc`

| File                                                    | Function(s)                            | Lines (parent-pin)                     | Nature of edit                                          |
|---------------------------------------------------------|----------------------------------------|----------------------------------------|---------------------------------------------------------|
| `src/backend/executor/nodeSubplan.c`                   | `ExecHashSubPlan`                      | ~117-120 (after `buildSubPlanHash` return, before probe body) | + `MemoryContextReset(node->hashtempcxt);` |
| `src/backend/executor/nodeSubplan.c`                   | `buildSubPlanHash`                     | ~631-638 (after both `LookupTupleHashEntry` sites, in the per-inner-tuple loop) | + `MemoryContextReset(node->hashtempcxt);` at end of the loop body |
| `src/backend/executor/execGrouping.c`                  | `BuildTupleHashTable` header comment   | ~150 (line describing `tempcxt` parameter) | Extend: "…and MUST be reset by the caller between lookup calls." |
| `src/backend/executor/execGrouping.c`                  | `LookupTupleHashEntry` header          | ~279-297                               | Add: "The caller is responsible for resetting the tempcxt between calls." |
| `src/backend/executor/execGrouping.c`                  | `LookupTupleHashEntryHash` header      | ~345-352                               | Same note.                                              |
| `src/backend/executor/execGrouping.c`                  | `TupleHashTableHash` header            | ~323-327                               | Same note.                                              |
| `src/backend/executor/execGrouping.c`                  | `FindTupleHashEntry` header            | ~372-385                               | Same note.                                              |
| `src/test/regress/sql/subselect.sql`                   | new test rows                          | end of file                            | Add a hashed-SubPlan-with-TOAST regress row (small-scale reproducer). |
| `src/test/regress/expected/subselect.out`              | matching expected output               | end of file                            | Corresponding expected result.                          |

**Estimated diff size:** ~6 lines of executable C code + ~15 lines of
comment doc + ~20 lines of regress SQL + expected. Total ~40-50 lines
inserted, ~0-3 removed. Well within the shape of `+33 / −43` reported
in triage for the upstream fix (they likely also removed some now-dead
code we haven't spotted — Phase 4 will show).

---

## §4 Catalog impact

None. No `pg_*.dat`, no header struct change. `SubPlanState` fields
`hashtempcxt` and `hashtablecxt` already exist (`execnodes.h:1022-1023`);
we don't add any.

---

## §5 Grammar / parse tree impact

None.

---

## §6 Planner impact

None. Purely executor-level.

---

## §7 Memory + resource management — F30 grep-verified ownership

**Ownership claim under test:**
> The `tempcxt` field of a `TupleHashTable` is owned by the caller,
> not the table. The caller passes a `MemoryContext` to
> `BuildTupleHashTable`, retains it, and is responsible for
> (a) resetting it between per-tuple lookup calls, and
> (b) deleting it (or letting a parent context reclaim it) when the
> table is torn down.

**Grep verification (F30):**

```
$ grep -RnE 'BuildTupleHashTable\(' \
    dev/src/backend/executor/
```

Result — 5 producers of `TupleHashTable` (each hands ownership of some
tempcxt to some `hashtable->tempcxt` slot):

| Caller producer                | tempcxt allocation           | tempcxt owner                     | Reset cadence (from source read)                             |
|---------------------------------|------------------------------|-----------------------------------|--------------------------------------------------------------|
| `nodeAgg.c:1527` `build_hash_table` | `aggstate->tmpcontext->ecxt_per_tuple_memory` | AggState (created in ExecInitAgg) | `ResetExprContext(tmpcontext)` in `agg_retrieve_direct` at `nodeAgg.c:2542` — per outer tuple |
| `nodeSetOp.c:98` `build_hash_table` | `econtext->ecxt_per_tuple_memory` (`ps_ExprContext`) | SetOpState's ps_ExprContext | `ResetExprContext(econtext)` at `nodeSetOp.c:454, 491` — per outer AND per inner tuple |
| `nodeRecursiveunion.c:45` `build_hash_table` | `rustate->tempContext` (dedicated AllocSet, created `nodeRecursiveunion.c:216`) | RecursiveUnionState | `MemoryContextReset(node->tempContext)` at `nodeRecursiveunion.c:105, 159` — per lookup |
| `nodeSubplan.c:539` `buildSubPlanHash` (main table) | `sstate->hashtempcxt` (dedicated AllocSet, created `nodeSubplan.c:918-921`) | SubPlanState | **NONE (leak)** — this plan adds it |
| `nodeSubplan.c:568` `buildSubPlanHash` (null table) | `sstate->hashtempcxt` (SAME dedicated AllocSet, shared with main table) | SubPlanState | **NONE (leak)** — this plan adds it |

**Grep verification (consumers, i.e. lookup sites):**

```
$ grep -RnE 'LookupTupleHashEntry\(|LookupTupleHashEntryHash\(|FindTupleHashEntry\(|TupleHashTableHash\(' \
    dev/src/backend/executor/
```

Result — 11 consumer sites; each is checked for whether it's followed
by a tempcxt reset before returning to a scope that could allocate
again into the same tempcxt:

| Consumer site                                          | Followed by reset?              |
|---------------------------------------------------------|---------------------------------|
| `nodeAgg.c:2204` `LookupTupleHashEntry`                | yes — outer loop resets tmpcontext line 2542 |
| `nodeAgg.c:2765` `LookupTupleHashEntryHash`            | yes — reload loop resets tmpcontext |
| `nodeSetOp.c:438` `LookupTupleHashEntry` (outer)       | yes — line 454 `ResetExprContext(econtext)` immediately after |
| `nodeSetOp.c:478` `LookupTupleHashEntry` (inner)       | yes — line 491 `ResetExprContext(econtext)` immediately after |
| `nodeRecursiveunion.c:103` `LookupTupleHashEntry`      | yes — line 105 `MemoryContextReset(node->tempContext)` immediately after |
| `nodeRecursiveunion.c:157` `LookupTupleHashEntry`      | yes — line 159 `MemoryContextReset(node->tempContext)` immediately after |
| `nodeSubplan.c:160` `FindTupleHashEntry` (main probe)  | **NO — fix target** |
| `nodeSubplan.c:169, 202, 209` `findPartialMatch`       | **NO — fix target** (all resolve to `ExecQual` on `hashtable->tempcxt` through `execTuplesUnequal` line 761) |
| `nodeSubplan.c:631` `LookupTupleHashEntry` (build main)  | **NO — fix target** |
| `nodeSubplan.c:636` `LookupTupleHashEntry` (build null)  | **NO — fix target** |

**F30 conclusion:** the ownership claim ("caller owns tempcxt reset")
is CONSISTENTLY OBSERVED across 4/5 producers and 6/6 non-nodeSubplan
consumer sites. `nodeSubplan.c` is the outlier; aligning it to the
existing invariant is exactly the fix scope.

**Cleanup path for `hashtempcxt` itself:** created in
`ExecInitSubPlan` (`nodeSubplan.c:918`) with parent
`CurrentMemoryContext` at that call — which is `es_query_cxt`
(the per-query context). No explicit `MemoryContextDelete` is needed;
the context is reclaimed at query end when `es_query_cxt` is deleted.
This matches the parent pin's behavior; our fix doesn't disturb the
cleanup.

**Verified: no double-reset risk.** The two proposed reset call sites
are (a) inside `ExecHashSubPlan` before the probe body, and (b) inside
`buildSubPlanHash` inside the per-inner-tuple loop. `buildSubPlanHash`
is called from `ExecHashSubPlan` line 118 BEFORE our proposed reset
at (a); the (b) reset fires per inner tuple during the build. So the
sequence per outer probe is: (build, if needed) → reset(a) → probe
lookups. No two resets can fire on the same allocation.

---

## §8 Phased implementation

Approach B, 3 phases.

### Phase 1 — Fix `ExecHashSubPlan` outer-probe leak

**Files:** `src/backend/executor/nodeSubplan.c`.

**Edit:** in `ExecHashSubPlan` (parent-pin lines 100-217), after the
`buildSubPlanHash` call at line 118 and before the early-return
FALSE at line 126, add:

```c
    /*
     * Reset the temp context in which the hash and equality functions
     * allocate transient memory (e.g. detoasted varlena values).  The
     * caller-owns-tempcxt convention is followed by every other
     * TupleHashTable* caller; nodeSubplan.c was previously the outlier.
     */
    MemoryContextReset(node->hashtempcxt);
```

**Where:** insert between the `buildSubPlanHash(node, econtext);`
block (parent line 117-119) and the `*isNull = false;` at line 124.
That way it runs on EVERY invocation of the probe path, including the
common non-first invocation where `buildSubPlanHash` didn't need to
re-run.

**Rationale for entry-side (not exit-side):** `ExecHashSubPlan` has ~6
early-return sites (lines 165, 173, 176, 191, 197, 206, 212, 215).
Reset at entry covers all of them without needing a reset at each
return. It also cleans up any residue from the previous outer tuple's
probe (which is when the residue was created).

**Phase-end check scope (R13 executor tier):**

```
meson test --no-rebuild --suite regress --suite isolation --suite pg_stat_statements
```

**Exit condition:**
1. Regress + isolation + pg_stat_statements green.
2. Re-run the load-bearing canary from §0. RSS during the query must
   grow at ≤ 1 MB/s (was 15 MB/s).
3. `pg_backend_memory_contexts()` mid-query shows
   `Subplan HashTable Temp Context` size ≤ 32 kB (small AllocSet
   keeper).

### Phase 2 — Fix `buildSubPlanHash` inner-build leak

**Files:** `src/backend/executor/nodeSubplan.c`.

**Edit:** in the per-inner-tuple loop in `buildSubPlanHash`
(parent-pin lines 601-645), after the `ResetExprContext(innerecontext);`
at line 644 (which resets a DIFFERENT context — the ExecProject
inner context), add:

```c
        /*
         * Also reset the hash tempcxt: the LookupTupleHashEntry above
         * ran hash and equality functions which may have allocated
         * transient memory (e.g. detoast copies) into node->hashtempcxt.
         * Every other TupleHashTable* caller resets its tempcxt between
         * lookups; align nodeSubplan with that convention.
         */
        MemoryContextReset(node->hashtempcxt);
```

**Where:** after line 644 (`ResetExprContext(innerecontext);`),
before the closing brace of the `for` loop at line 645.

**Phase-end check scope (R13 executor tier):**

```
meson test --no-rebuild --suite regress --suite isolation --suite pg_stat_statements
```

**Exit condition:**
1. Same test suites green.
2. Canary from §0 still flat.
3. A synthetic "many-inner-rows" variant with wide TOAST'd inner keys
   (~500 000 rows on the inner side, single outer row) shows bounded
   RSS. This isolates the phase 2 fix from phase 1.

### Phase 3 — Document the contract in `execGrouping.c` + regress row

**Files:**
- `src/backend/executor/execGrouping.c` (comment updates only).
- `src/test/regress/sql/subselect.sql` (add a hashed-SubPlan-with-TOAST
  regress row).
- `src/test/regress/expected/subselect.out` (matching output).

**Edits — `execGrouping.c`:**

1. In `BuildTupleHashTable`'s header block (parent line ~150), extend
   the description of the `tempcxt` parameter:

```
 *	tempcxt: short-lived context for evaluation hash and comparison functions.
 *	         The caller is responsible for resetting this context between
 *	         successive TupleHashTable lookup calls, because the hash and
 *	         equality functions may allocate transient memory into it (e.g.
 *	         detoasted varlena values).  See LookupTupleHashEntry etc.
```

2. In `LookupTupleHashEntry`'s header block (parent line 279-293), add
   a paragraph at the end:

```
 *
 * NB: the tempcxt passed to BuildTupleHashTable is used to evaluate the hash
 * and equality functions, which may allocate transient memory (e.g. detoasted
 * varlenas).  The caller is responsible for resetting the tempcxt between
 * calls (or on some cadence that keeps memory usage bounded).
```

3. Same paragraph, verbatim, on `LookupTupleHashEntryHash`
   (line ~345-348), `TupleHashTableHash` (line ~323-325), and
   `FindTupleHashEntry` (line ~372-380).

**Edits — regress test:**

Append to `src/test/regress/sql/subselect.sql`:

```sql
-- Regression: hashed SubPlan probe path must not leak per-lookup
-- transient allocations from the hash and equality functions
-- (see nodesubplan_leak fix).  Uses TOAST'd wide keys to amplify
-- the per-lookup allocation size.
BEGIN;
CREATE TEMP TABLE t_probe (id int, k text);
ALTER TABLE t_probe ALTER COLUMN k SET STORAGE EXTERNAL;
INSERT INTO t_probe
  SELECT g, repeat(md5(g::text), 200)
  FROM generate_series(1, 50) g;

CREATE TEMP TABLE t_outer (id int, key text);
INSERT INTO t_outer
  SELECT g, repeat(md5((g % 50)::text), 200)
  FROM generate_series(1, 50000) g;

SET LOCAL max_parallel_workers_per_gather = 0;

SELECT count(*) FROM t_outer o
 WHERE (o.id < 0) OR (o.key IN (SELECT k FROM t_probe));
ROLLBACK;
```

Expected output: single row `50000` (all outer rows match, since
`(g % 50)` cycles through 1..50 exactly, and t_probe holds md5 hashes
of `g::text` for g in 1..50 — every outer key IS present in the inner
IN-set).

**Correction:** on second look, `md5(g::text)` for `g in 1..50` and
`md5((g % 50)::text)` for `g in 1..50000` — the outer key range is
`md5(0::text), md5(1::text), …, md5(49::text)` (since `g % 50` for
g=50 is 0, g=100 is 0, etc.), whereas inner keys are `md5(1::text)
… md5(50::text)`. So `md5(0::text)` outer keys don't match; expected
count is `50000 - 1000` = `49000`. The plan will confirm via a real
run before committing the expected file.

**Phase-end check scope (R13 executor tier):**

```
meson test --no-rebuild --suite regress --suite isolation --suite pg_stat_statements
```

**Exit condition:**
1. Same test suites green including the new regress row.
2. Canary from §0 still flat.
3. `git grep -n 'tempcxt' dev/src/include/executor/executor.h
    dev/src/backend/executor/execGrouping.c` shows the new documentation.

---

## §9 Test plan

Per-phase phase-end checks (R13) as above. End-of-implementation gate
(R12) runs full `meson test --no-rebuild`.

**Own-test-suite (R14) coverage:**

The comprehensive suite ships as ONE regress row in phase 3 (the
hashed-SubPlan-with-TOAST canary). Additional coverage:

- **Edge case: `hashnulls` path.** Add a variant where the inner
  subquery produces NULL rows, so `node->hashnulls` gets populated and
  `findPartialMatch` runs (leak site #4). Uses:
  ```sql
  SELECT count(*) FROM t_outer o
   WHERE (o.id < 0) OR (o.key IN (SELECT nullif(k, 'x') FROM t_probe));
  ```
  (Won't actually produce nulls given the data, but exercises the
  code path if the planner leaves the null-check active.)

- **Edge case: cross-type comparison.**
  ```sql
  SELECT count(*) FROM t_outer o
   WHERE o.id::bigint IN (SELECT id::bigint FROM t_probe);
  ```
  Cross-type triggers `cur_eq_comp` distinct from tab_eq_func. Verifies
  the fix works across the cross-type path too.

- **Rescan case:** put the hashed subplan inside a nested loop that
  causes multiple `buildSubPlanHash` invocations. Ensures the reset
  fires correctly on rescan, not just on first build. Uses a small
  outer relation and forces `enable_hashjoin = off`.

None of these need dedicated TAP tests; all fit as regress rows.

---

## §10 Documentation impact

- `src/backend/executor/execGrouping.c` header comments: contract
  documented (see Phase 3).
- No SGML documentation change. This is an internal executor
  contract; user-facing docs don't mention `TupleHashTable`.

---

## §11 Backport

Upstream back-patched through PG13 per triage. Our blind plan targets
`master` at parent pin `9016fa7e3bc`; the fix should apply cleanly to
older branches modulo minor context drift in `execGrouping.c` (some
header comments may sit at slightly different line numbers). Not our
concern for the calibration.

---

## §12 Cross-references

- `knowledge/idioms/memory-contexts.md` — the "dedicated tempcxt +
  per-work-unit reset" pattern this fix realigns to.
- `knowledge/idioms/memory-context-allocset-internals.md` —
  confirms `MemoryContextReset` on an AllocSet is O(1) after the
  first keeper block, so per-lookup resets are cheap.
- (No existing `knowledge/idioms/tuple-hash-table.md` yet — worth
  creating post-Phase 4 as a corpus win.)
- `planning/nodesubplan_leak/triage.md`, `baseline.md`,
  `brainstorm.md`.

---

## §13 High-severity unknowns

1. **Is `hashtempcxt` also used by `findPartialMatch` (via
   `execTuplesUnequal`)?** Yes — see `nodeSubplan.c:761`
   `execTuplesUnequal(..., hashtable->tempcxt)`. The routine resets
   `evalContext` at entry (line 687) already. But that's a
   SEPARATE `MemoryContextReset` inside `execTuplesUnequal`, not tied
   to our probe-loop reset. Our fix at the `ExecHashSubPlan` entry
   still helps because per-outer-tuple `findPartialMatch` may execute
   many `execTuplesUnequal` calls (one per hashtable entry it scans);
   the intra-loop reset at line 687 keeps THAT bounded. Our reset
   handles residue LEFT BY hash / eq function calls inside
   `FindTupleHashEntry` line 160. No conflict. **Risk: LOW.**

2. **Does anyone allocate into `hashtempcxt` and expect the data to
   persist across a probe?** Grep says no (see brainstorm §8 Q5). But
   the risk of a subtle contract violation exists if a hash function
   memoizes state via a fmgr `flinfo->fn_extra` mechanism that points
   into `hashtempcxt`. Standard PG hash functions don't do this;
   custom user hash functions (via extensions) MIGHT. **Risk: LOW —
   documenting the contract in phase 3 mitigates.**

3. **Rescan / `chgParam != NULL` path.** `ExecHashSubPlan` line 117
   rebuilds the hash table when `chgParam != NULL`. On rebuild,
   `buildSubPlanHash` runs (with per-inner-tuple reset from phase 2)
   and then falls through to our phase-1 probe reset. Works. **Risk:
   LOW.**

4. **Empty-subquery early exit at line 126.** If `!node->havehashrows
   && !node->havenullrows`, `ExecHashSubPlan` returns before the
   probe. The phase-1 reset FIRES first (correct — it just resets an
   empty context, O(1)). But if a caller invokes `ExecHashSubPlan`
   thousands of times on an empty subquery, we're doing thousands of
   no-op resets. **Risk: NEGLIGIBLE — reset of an already-empty
   AllocSet is a single field-check.**

5. **Test flakiness.** The regress canary uses `SET LOCAL
   max_parallel_workers_per_gather = 0` and small-scale data. Should
   be deterministic. `md5()` output is stable across PG versions. **Risk:
   LOW.**

---

## §14 Citation chain + Phase-4 comparison hook

### Citation chain

```
plan.md (this file)
  └── §3 file table cites → nodeSubplan.c (parent pin 9016fa7e3bc)
        └── lines 100-217 (ExecHashSubPlan), 495-657 (buildSubPlanHash)
        └── which cite → execGrouping.c
              └── lines 150 (BuildTupleHashTable), 279-403 (Lookup* et al.)
        └── which cite → executor.h:133-159 (API declarations)
        └── which cite → execnodes.h:1022-1023 (hashtempcxt / hashtablecxt fields)
  └── §7 F30 grep cites → nodeAgg.c:1527, 2542; nodeSetOp.c:98, 454, 491;
        nodeRecursiveunion.c:45, 105, 159 (all parent pin)
  └── knowledge/idioms/memory-contexts.md, memory-context-allocset-internals.md
```

Every executable-code cite in this plan is anchored at parent pin
`9016fa7e3bc` in the worktree
`postgresql-dev-feature-nodesubplan-leak/`. When Phase 3 implementation
commits land, each phase's commit message will carry a `Plan:` trailer
pointing back to `planning/nodesubplan_leak/plan.md` (phase N).

### Phase-4 comparison hook (pre-declared)

In Phase 4, run:

```
git -C dev show abdeacdb0920d94dec7500d09f6f29fbb2f6310d -- \
    src/backend/executor/nodeSubplan.c \
    src/backend/executor/execGrouping.c
```

and diff against our Phase 3 branch tip. Expected axes of comparison:

| Axis                             | Blind plan (this document)                            | Upstream `abdeacdb092`                    |
|----------------------------------|--------------------------------------------------------|-------------------------------------------|
| Reset site: probe path            | Entry of `ExecHashSubPlan` after `buildSubPlanHash`   | ? — could be entry, exit, or per-lookup   |
| Reset site: build path            | End of per-inner-tuple loop in `buildSubPlanHash`     | ? — could be per-loop or per-build        |
| Reset call form                   | `MemoryContextReset(node->hashtempcxt)`               | ? — could be same or `ResetExprContext(...)`-style |
| execGrouping.c changes            | Doc-only (5 comment blocks + tempcxt param comment)   | Triage says +6 lines — could be doc-only or a real code change |
| nodeSubplan.c net line delta      | ~+6 executable lines, ~+15 comment lines              | Triage says +27 / −43 (NET −16 lines) — SUGGESTS the upstream ALSO removed some now-obsolete code we haven't spotted |
| Number of reset call sites in nodeSubplan.c | 2 (entry of ExecHashSubPlan, end of buildSubPlanHash inner loop) | ? |
| Regress test added                | 1 row in subselect.sql                                | ? — may or may not have added a regress row |

**Prediction confidence:** medium-high on the SHAPE (a caller-side
reset in the two functions plus doc updates); medium on the SITES
(entry vs. exit could go either way). The `+27 / −43` net negative diff
in the upstream fix hints that the upstream ALSO removed 40+ lines of
code — which we did NOT identify in blind mode. Candidates:
- Perhaps `execTuplesUnequal` at nodeSubplan.c:673-729 got deleted
  because its "reset evalContext" pattern is now covered by the
  caller-side reset in the hashtempcxt.
- Perhaps the `findPartialMatch` helper got refactored.
- Perhaps `hashtempcxt` itself was eliminated (unlikely given the
  data structure has `tempcxt` as a field).

We'll harvest whatever we missed as F31/F32 Phase-4 findings.

### Phase-4 lessons harvest (pre-declared)

Regardless of whether the shape matches, Phase 4 will produce:
- A row in `progress/files-examined.md` for
  `nodeSubplan.c` and `execGrouping.c` at commit `abdeacdb092`.
- A F-finding if the blind approach missed the −43 line removal.
- Comparison table in `planning/nodesubplan_leak/comparison.md`
  (analogous to sesvars `comparison.md`).

---

## Plan exit condition

- §0 canary named.
- §3 file table with parent-pin line ranges.
- §7 F30 grep-verified ownership claim.
- §8 phases with explicit R13 phase-end check scopes.
- §13 unknowns enumerated.
- §14 Phase-4 comparison hook pre-declared.
- Blind constraint respected.
