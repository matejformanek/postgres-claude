# Comparison — our blind fix vs Tom Lane's `5a2043bf713`

**Date:** 2026-06-23
**Our 3-commit chain (`feature_jsonpath_leak`):**
- `74cbe74f713` Phase 1: redesign JsonValueList struct + helpers
- `6510b8a1e2d` Phase 2: per-call MemoryContext at executePredicate + audit-mode Free
- `e92433395ff` Phase 3: regress test rows

**Upstream fix:** `5a2043bf713` (Tom Lane, 2026-03-19, 1 commit).

Both branches start from the same parent `7724cb9935a`.

## TC-LB-1 outcome

| metric             | parent commit | our fix      | Tom Lane's fix |
|--------------------|--------------:|-------------:|---------------:|
| Peak backend RSS   | 5,686,688 KB  | 32,272 KB    | 32,160 KB      |
| Wall clock         | ~60 s         | (n/m)        | 3.07 s         |
| Result correctness | 9999 rows     | 9999 rows    | 9999 rows      |

**Identical envelope.** Our trilogy-derived solution lands in the same
RSS bucket as Tom's (32 MB vs 32 MB).

## Diff size

| author    | files | insertions | deletions | code+tests | commits |
|-----------|------:|-----------:|----------:|----------:|-------:|
| Tom Lane  |     1 |        362 |       233 |       595 |       1 |
| Ours      |     3 |        342 |        80 |       422 |       3 |

Tom Lane's patch is bigger on the C file side because he rewrote the
struct + every helper + every Append/Length/IsEmpty/Head/GetList
call.  Ours is smaller because we kept callers using pointer-based
JsonValueLists and concentrated the leak fix in a single
per-call-context wrap.  Tom shipped no test additions; we shipped 4
microbench rows for N ∈ {10, 100, 1000, 10000}.

## Storage design — fundamentally different

### Tom Lane's design (commit `5a2043bf713`)

```c
typedef struct JsonValueList
{
    int                     nitems;     /* items stored in this chunk */
    int                     maxitems;   /* allocated length of items[] */
    struct JsonValueList   *next;       /* next chunk, if any */
    struct JsonValueList   *last;       /* last chunk (base-chunk only) */
    JsonbValue              items[BASE_JVL_ITEMS];  /* INLINE storage */
} JsonValueList;
```

Linked chunks.  Base chunk lives in a stack-allocated parent (caller
declares `JsonValueList foo;` and calls `JsonValueListInit(&foo)`).
Base holds 2 inline `JsonbValue`s.  Overflow palloc's extra chunks
with `maxitems` doubling per allocation, minimum 16.  Items stored
**by value** (not by pointer) — the JsonbValue lives inside the
chunk's `items[]` array.

`JsonValueListAppend()` always copies the supplied `*jbv` into the
chunk's `items[]`.  This makes ownership trivial: the list owns its
JsonbValues.  `JsonValueListClear()` pfrees the extra chunks → all
JsonbValues released.  The base chunk needs no pfree since it lives
on the stack.

### Our design (Phase 1)

```c
typedef struct JsonValueList
{
    JsonbValue  *singleton;   /* used only if n == 1 */
    JsonbValue **values;      /* expansible array; used if n >= 2 */
    int          n;
    int          capacity;
} JsonValueList;
```

Single-struct, no chunking.  Singleton fast-path keeps n ≤ 1
allocation-free.  At n=2 we palloc a 4-pointer array; doubles
on overflow.  Items stored **by pointer** (`JsonbValue **`).  The
list owns the array but NOT the elements.

`JsonValueListFree()` pfrees the array only.  Elements survive —
they live wherever the caller palloc'd them (typically a fresh
`copyJsonbValue` allocation in `CurrentMemoryContext`).

## Leak fix mechanism — also different

| concern              | Tom Lane                        | Ours                              |
|----------------------|---------------------------------|-----------------------------------|
| Where JsonbValues live | inline in chunks                | scattered in CurrentMemoryContext |
| What Clear/Free releases | extra chunks (+ all values inline) | array of pointers only           |
| Hot-path leak (executePredicate) | `JsonValueListClear()` calls suffice | per-call `AllocSetContext` wrap   |
| Per-call overhead     | ~one extra-chunk palloc           | one AllocSetCreate + Delete (~400 ns) |
| Singleton/2-item path | zero palloc (base chunk inline)  | zero palloc (singleton/values[]==NULL) |

Tom's mechanism is structurally simpler: because items are inline,
freeing the chunks frees the JsonbValues, period.  Every site that
previously held a `JsonValueList` calls `JsonValueListClear()` and
all transient memory is gone.

Our mechanism requires recognizing that we own the *array* but not
the *elements*, and that the elements are the dominant leak source.
We solved it by inserting an `AllocSetContextCreate` /
`MemoryContextDelete` pair around the hot `executePredicate` body.
That works because anything `copyJsonbValue` palloc's inside the
context's lifetime gets reclaimed when we delete it.  But it
required the R7 tier-1 escalation (plan §7 said `Free` releases
only the array; experiments showed that's not enough).

## Caller-side simplification

Tom Lane's commit message highlights this directly:

> *"In this reimplementation, JsonValueListAppend() always copies the
> supplied JsonbValue struct into the JsonValueList data.  This
> allows simplifying and regularizing many call sites that
> sometimes palloc'd JsonbValues and sometimes passed a local-variable
> JsonbValue.  Always doing the latter is simpler, faster, and less
> bug-prone."*

We did NOT make this simplification.  Our `Append` retains the
mixed copy/borrow semantics from the parent code.  This means our
fix relies on per-call context to absorb the inconsistency, where
Tom's fix removes the inconsistency entirely.

**Score for clarity:** Tom +1.  His refactor makes the underlying
mechanism easier to reason about and to extend.

## API changes

| API                        | Tom Lane                         | Ours                            |
|----------------------------|----------------------------------|---------------------------------|
| `JsonValueListInit`        | NEW — required by every caller   | not added (zero-init suffices) |
| `JsonValueListClear`       | NEW — replaces leaky pattern     | renamed to `Free`               |
| `JsonValueListFree`        | (not present; uses Clear)        | NEW                             |
| `JsonValueListAppend(... const JsonbValue *)` | const param + always copy | unchanged (`JsonbValue *`, optionally copies) |
| `JsonValueListLength`      | REMOVED in favor of `JsonValueListIsEmpty / IsSingleton / IsList` triplet | kept |
| `JsonValueListGetList`     | (would need materialization too) | rewrites to materialize on demand |

Tom's API surface is broader: he added `Init`, removed `Length` in
favor of three predicates, and made `Append` const-correct + always-
copy.  Our API is narrower: we kept the existing surface and only
added `Free`.

**Score for API design:** Tom +1.  His changes make the contract more
obvious at every call site.

## Performance comparison (commit message claims vs measured)

Tom: *"about twice as fast as before on not-very-large inputs"*.
Our TC-LB-1 measurement matches his 3.07s on the 10K case.  At
N=10/100 we did not benchmark explicitly; should be comparable.

Both designs achieve O(log N) palloc per list (log2(10000) ≈ 14
allocations for Tom's `2 → 16 → 32 → 64 → ...` chunk sizes vs
14 for our `4 → 8 → 16 → ...` doubling).

## What we got right

1. **Identified the correct hot site** — both fixes target
   `executePredicate` as the dominant leak driver.
2. **Achieved the same RSS envelope** — 32 MB / 32 MB, within 0.4%.
3. **Conserved the singleton fast-path** — both designs keep the
   common N ≤ 1 case allocation-free.
4. **Same regression test premise** — we shipped explicit
   N-microbench rows; Tom shipped none, betting on the existing
   suite catching subsequent regressions.

## What we got wrong (and what the trilogy missed)

1. **Plan §7 ownership invariant was wrong.**  We wrote "JsonValueListFree
   releases values[] only; JsonbValue elements remain owned by the
   input jsonb."  In fact, `executeAnyItem` calls
   `JsonValueListAppend(found, copyJsonbValue(&v))` which palloc's a
   FRESH JsonbValue per element — they are NOT borrowed from the
   input.  This was a brainstorm-time misread of the data flow,
   surfaced only when Phase 2's harness check showed 4.9 GB still
   leaking.
2. **Didn't see Tom's "always copy" simplification.**  The
   brainstorm enumerated approaches A (Free-at-call-site), B (per-call
   context), C (struct redesign + Free), D (caller-side arena), and
   recommended C+A.  None of these recognized that an "always copy
   on Append + store values inline" design would short-circuit the
   ownership question entirely.  Tom's design is approach E that
   wasn't on the list.
3. **Phase 1 over-promised TC-LB-1.**  Plan §8 claimed Phase 1
   "lands TC-LB-1"; in reality Phase 1's struct redesign reduces
   memory ~7× but the leak persists.  TC-LB-1 lands in Phase 2.
4. **Used a per-call MemoryContext where Tom used inline storage.**
   Both correct.  Tom's is cleaner.  Ours required an R7 escalation
   mid-Phase-2 to apply.

## Methodology validation verdict for the planner suite

- **Phase 0 harness (memory-hunt)** — strong.  Detection toolchain
  built, reproducer pinned at 177× signal, methodology generalizes
  to other leak-fix commits in the corpus.
- **Phase 1 triage** — strong.  Tom Lane's commit message provided
  a gold-standard reproducer; our triage picked it correctly.
- **Brainstorm (Phase 2 of trilogy)** — partial.  4 candidate
  approaches enumerated; missed the "approach E" (inline storage +
  always-copy) that Tom Lane actually used.  This is a brainstorm-
  generation failure: insufficient exploration of the design space
  around the storage representation.  R15a "name the load-bearing
  row" satisfied (TC-LB-1).
- **Plan (Phase 2 of trilogy)** — partial.  Plan §7 ownership
  invariant was wrong; §8 Phase 1 "lands TC-LB-1" claim was wrong;
  both surfaced only at implementation time, both fixable via R7
  tier-1.  Plan was the right TYPE of document (14 sections,
  file:line cites, risks enumerated) — the ERRORS were in
  judgement, not structure.
- **Implement (Phase 3 of trilogy)** — strong.  R4 phase-end checks
  caught both errors; R7 escalation absorbed both without re-plan;
  3 commits with `Plan:` trailers per R5; R13 gate stayed green at
  385 subtests per phase.  Live pre-commit hook fired clean on all
  3 dev commits (no `PG_PRECOMMIT_SCOPE=skip` needed, validating
  meta-repo commit `d89efca` from sesvars_v3).

**Net assessment:** the planner suite produced a working fix with
identical leak-bound outcome to Tom Lane's upstream patch, but via
a different (slightly clunkier) design.  An adversarial-review pass
on the brainstorm would have surfaced "approach E" before Phase 3
started; that's the L-lesson to harvest.

## L-lesson to graduate

**L5 — Adversarial brainstorm pass before locking DECISIONs.**  When
the brainstorm enumerates a design space, the candidate approaches
should be challenged by a "have we considered storing X *inline*
vs. *by reference*?" question — explicitly.  The pointer-vs-value
storage choice is foundational and changes downstream ownership
questions.  Our brainstorm took "JsonValueList stores pointers"
as a given (inherited from the parent code) and didn't ask whether
"JsonValueList stores values inline" was a viable alternative.  Tom
Lane's design proves it was.

Action: extend `pg-feature-brainstorm/SKILL.md` Step "Sketch
candidate approaches" with an explicit
*"Storage representation: by-value, by-pointer, by-reference-to-
shared-pool — which best matches lifetime requirements?"*
sub-question.  Applies to any feature that wraps a collection
type.

## F-finding to graduate

**F30 — Ownership invariants in plan §7 need data-flow verification.**
The plan's §7 (Memory + resource management) section is where
ownership rules live.  Our plan stated an ownership rule
("JsonValueListFree only releases the array") that was contradicted
by an actual call site (`copyJsonbValue(&v)` palloc'ing per
element).  The plan-time grep for `copyJsonbValue` would have
shown 3 sites doing fresh allocations; that would have invalidated
the §7 invariant before Phase 3 started.

Action: `pg-feature-plan/SKILL.md` §7 should require, for any
"X is owned by Y" claim, a grep pass that lists every site
producing X and confirms they hand ownership to Y.  Without that
verification, §7 is asserting an invariant the planner hasn't
checked.
