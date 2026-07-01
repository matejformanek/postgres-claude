# Brainstorm — fix transient memory leakage in jsonpath evaluation

**Slug:** `jsonpath_leak`
**Phase:** brainstorm (Phase 1 of the planner)
**Status:** blind — written without consulting Tom Lane's actual fix
(`5a2043bf713`); to be compared against it post-implement.

> **Blind constraint.** This brainstorm is part of the memory-hunt
> calibration. The fix already exists upstream at `5a2043bf713`. We
> derive a fix from scratch and compare designs at Phase 4. Do NOT
> read `5a2043bf713` source until then.

## Context

The reproducer (Tom Lane, validated 2026-06-22 in
`planning/memory-hunt/triage.md`):

```sql
SELECT jsonb_path_query(
  (SELECT jsonb_agg(i) FROM generate_series(1, 10000) i),
  '$[*] ? (@ < $)');
```

Pre-fix: backend RSS peaks at **5.7 GB** at t=49s on parent commit
`7724cb9935a`. Quadratic memory growth in array length N (10K
elements × 10K iterations × ~64 bytes/cell). Memory is reclaimed when
the SQL function exits, but during evaluation a single query OOMs the
backend.

## Root cause (verified by reading the source at parent)

`src/backend/utils/adt/jsonpath_exec.c:2026 executePredicate()`:

```c
JsonValueList lseq = {0};
JsonValueList rseq = {0};

res = executeItemOptUnwrapResultNoThrow(cxt, larg, jb, true,  &lseq);
res = executeItemOptUnwrapResultNoThrow(cxt, rarg, jb, unwrapRightArg, &rseq);
JsonValueListInitIterator(&lseq, &lseqit);
while (...) { /* iterate */ }
/* lseq, rseq fall out of scope but their palloc'd cells stay
   allocated in the surrounding MemoryContext */
```

`JsonValueList` (jsonpath_exec.c:147-151) wraps either a `JsonbValue*`
singleton or a PG `List*`. For multi-value sequences, the List grows
N cons cells in the active MemoryContext. `executePredicate` never
frees them. Same pattern in `executeBinaryArithmExpr:2106`,
`executeStartsWithLeftArg`, and any other site that allocates
transient `JsonValueList`s.

For `$[*] ? (@ < $)`:
- Outer `[*]` iterates 10000 array elements.
- For each iteration, the filter `(@ < $)` calls `executePredicate`.
- `rseq` for `$` is unwrapped to a 10000-element list.
- That list leaks 10000 cells × 10000 iterations = 100M cells worth.
- ~6 GB ≈ 100M × ~60 B/cell (palloc overhead included).

## §0 Concrete usage surface (what must NOT leak)

These are the SQL patterns whose memory footprint must become bounded
(or at worst linear in N, never quadratic):

### Filter predicates referring to root

- `SELECT jsonb_path_query(j, '$[*] ? (@ < $)')` — Tom's reproducer
- `SELECT jsonb_path_query(j, '$[*] ? (@.x > $.threshold)')`
- `SELECT jsonb_path_query(j, '$[*] ? (@ != $)')`
- `SELECT jsonb_path_exists(j, '$[*] ? (@ in $[*])')` — pathological

### Filter predicates with .**/.* recursion

- `SELECT jsonb_path_query(j, '$.** ? (@.k == $.target)')`
- `SELECT jsonb_path_query_array(j, '$.* ? (@ > $)')`

### Arithmetic inside filters

- `SELECT jsonb_path_query(j, '$[*] ? (@ + $.k > 10)')`
- `SELECT jsonb_path_query(j, '$[*] ? (sum(@) < $.budget)')` (sum over array)

### EXISTS predicates

- `SELECT jsonb_path_exists(j, '$[*] ? (exists(@.children ? (@ < $)))')`

### LIKE_REGEX inside filter

- `SELECT jsonb_path_query(j, '$.tags[*] ? (@ like_regex $.pattern)')`

### JSON_TABLE column expressions (`SQL/JSON` standard)

- `SELECT * FROM JSON_TABLE(j, '$' COLUMNS (v int PATH '$.items[*] ? (@ < $.cap)'))`

### Edge / boundary

- Empty array `[]` — predicate evaluation should still terminate cleanly.
- Single-element array (singleton-path) — must not leak even one cell.
- Deeply-nested object `'$.**'` — list grows per recursion depth.
- N=1 (singleton): list never materializes; verify no fix-introduced regression.

### Load-bearing test row (R15a)

**TC-LB-1:**
`SELECT jsonb_path_query((SELECT jsonb_agg(i) FROM generate_series(1,10000) i), '$[*] ? (@ < $)')`
→ peak backend RSS < 100 MB, runtime < 5 s.

This is the row the architecture exists to fix. Every phase plan
must reference it; the phase that lands the fix is the architectural
centerpiece; the comprehensive test suite ships a TC for it; the
end-gate canary exercises it.

## Candidate approaches

### Approach A — local explicit free (smallest patch)

Add `JsonValueListClear()` (already exists, but renamed/extended to
also `pfree()` cells) at the end of every transient-list site:

```c
static void JsonValueListReset(JsonValueList *jvl) {
    if (jvl->list) {
        list_free_deep(jvl->list);  // or list_free if cells aren't pfree-safe
        jvl->list = NIL;
    }
    jvl->singleton = NULL;
}

/* in executePredicate */
res_pred = ... /* save before free */;
JsonValueListReset(&lseq);
JsonValueListReset(&rseq);
return res_pred;
```

**Pros:** minimal diff (~10-20 LOC), no struct redesign, no API change.
**Cons:** every site that uses a transient JsonValueList must be
audited and the free added. Easy to miss a site. `list_free_deep`
may not be safe if any JsonbValue is shared.

**Risk hot-spots:** every `JsonValueList foo = {0};` declaration that
isn't the function's output `*found` parameter.

### Approach B — per-call MemoryContext

Wrap each predicate-eval site in its own short-lived context:

```c
MemoryContext predcxt = AllocSetContextCreate(CurrentMemoryContext,
                                              "jsonpath predicate",
                                              ALLOCSET_DEFAULT_SIZES);
MemoryContext oldcxt = MemoryContextSwitchTo(predcxt);
/* populate lseq, rseq, iterate */
res_pred = ...;
MemoryContextSwitchTo(oldcxt);
MemoryContextDelete(predcxt);
return res_pred;
```

**Pros:** structurally atomic — if you forget to free, the context
delete reclaims everything. Standard PG idiom (executor short-lived
contexts).
**Cons:** AllocSetContextCreate + Delete has per-call overhead (~200ns
each). For 10K predicate calls that's 2 ms × 2 contexts = noticeable.
Predicate evaluation is in a hot loop; constants matter.

### Approach C — redesign JsonValueList as expansible array

Replace `singleton + List*` with `singleton + JsonbValue **array + int n + int cap`:

```c
typedef struct JsonValueList {
    JsonbValue *singleton;
    JsonbValue **values;  /* expansible array */
    int n;
    int cap;
} JsonValueList;
```

Plus a `JsonValueListFree(JsonValueList *jvl)` that frees the array
in one `pfree`.

**Pros:** O(1) free (one pfree of the array, plus zero or one pfrees
of JsonbValue elements depending on ownership rules); no per-cell
palloc overhead → 64-byte cells become 8-byte pointers, 8× smaller.
Closer to a "data structure" fix vs "missing free" fix.
**Cons:** larger diff (every site that uses JsonValueList — Append,
Length, Head, GetList, InitIterator, Next — gets touched). Risk of
introducing subtle iteration / ownership bugs. Iterator state also
changes (no more List+ListCell — index+array).

**Sub-question:** the existing `JsonValueListGetList()` returns a
`List*` for callers that need PG's list API (e.g. JSON_TABLE plan
state at line 196 holds `JsonValueList found` and may transitively
require list APIs). Need to either keep this conversion or audit
callers.

### Approach D — caller-side arena per executeJsonPath call

Add one MemoryContext to `JsonPathExecContext` (the "cxt" struct)
that's created at `executeJsonPath` entry, used for all transient
JsonValueLists, and `MemoryContextReset`-ed (not deleted) between
top-level `executeItem` iterations.

**Pros:** amortizes the context creation cost across thousands of
predicate calls; one Reset call between iterations.
**Cons:** requires distinguishing "transient" vs "result" lists —
the *result* JsonValueList (`*found`) must NOT live in the reset
arena. Lifetime bookkeeping is the new bug surface.

## Recommended approach

**Approach C (redesign struct) + Approach A (explicit free at
call sites).** Rationale:

1. **C alone is structurally correct** but requires every call site
   to invoke `JsonValueListFree`. Same audit burden as A.
2. **A alone is a band-aid** — the underlying inefficiency
   (palloc-per-cell, ~60 B for a ptr-sized payload) remains. A
   linear-but-still-big footprint on huge arrays.
3. **C + explicit free at predicate exit** mirrors how
   `executor/`'s expression evaluation handles ephemeral memory:
   data structure designed for cheap allocation + explicit lifecycle.
4. **Avoid B and D** unless C+A turns out impractical. The MemoryContext
   approach is robust but introduces per-call overhead that may
   show up in pgbench-style microbenches.

If the user vetoes the struct redesign (e.g. ABI concerns,
backport-to-stable concerns), fall back to **Approach A alone** —
the leak goes away even if the struct stays palloc-heavy.

## DECISION questions for the user

**DECISION 1 — Approach.** Pick A (call-site free only),
C (struct redesign + free), or C+A (recommended). Tom Lane's actual
fix is C+A (revealed after Phase 4 compare).

**DECISION 2 — Backport policy.** Should the fix be back-portable
to PG 17 / 16? If yes, Approach A is safer (smaller diff, no struct
ABI churn for any embedded usage). If we're targeting master only,
Approach C is fine.

**DECISION 3 — JSON_TABLE coupling.** `JsonTablePlanState` at line
196 embeds a `JsonValueList found`. If we redesign the struct (C),
this state lives across many rows. Need to confirm: is this `found`
ever populated AND freed? If it's populated-and-leaked, the same fix
applies. If it's populated-and-consumed-progressively, our redesign
needs to keep `Next()` semantics identical.

**DECISION 4 — Test scope.** Should we ship:
(a) only TC-LB-1 (the 10K reproducer) under `src/test/regress`;
(b) TC-LB-1 + array of microbench rows covering N ∈ {10, 100, 1000, 10000};
(c) TC-LB-1 + a TAP test that asserts RSS stays bounded
   (`PostgreSQL::Test::Utils::run_command` + `/proc/$pid/status`)?
The Valgrind harness in `planning/memory-hunt/container/` covers
true-leak detection automatically; RSS is the leak signal here.

**DECISION 5 — Comprehensive scope (R15).** Are we fixing ONLY the
4 leak sites (`executePredicate`, `executeBinaryArithmExpr`,
`executeStartsWith`, `executeLikeRegex`) or auditing ALL ~20
`JsonValueList` declarations in the file and adding the
free/reset where appropriate? The audit-mode is safer (no missed
sites for similar reproducers) but ships a bigger diff.

## Hand-off

Next step: `/pg-plan jsonpath_leak` to produce the heavy plan.
Per the user's "blind trilogy" pick, do not consult `5a2043bf713`
until Phase 4 compare.
