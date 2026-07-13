# Comparison — our blind fix vs Sawada's `b46efe90482`

**Date:** 2026-07-13
**Our chain (`feature_pgoutput_uaf`):**
- `00db6795dbd` "Free pgoutput RelationSyncCache on cachectx reset"

**Upstream fix:** `b46efe90482` (Vignesh C author, Sawada
co-author + committer, 2025-10-09, back-patched-through PG15).

Both branches start from parent `71540dcdcb2`.

## L6+L7 verdict — approach category correct, L7 details mixed

**This was the L7 stress test — the target's fix pattern is
documented (in the commit message) to use
`MemoryContextRegisterResetCallback`. The blind trilogy MUST
enumerate approach E and name the 3 L7 detail choices.**

- **Approach category (L6)**: BOTH fixes are approach E (register
  a reset callback that hash_destroys + NULLs
  `RelationSyncCache`). ✓
- **L7 detail #1 — callback storage location**: Sawada chose
  **separate palloc** on the current memory context (not embed
  in `PGOutputData`). We chose F34 embed in `PGOutputData`. **We
  differed** — F34 is not universally right (see F38 below).
- **L7 detail #2 — callback function shape**: BOTH wrote a
  wrapper because the 2-op cleanup (hash_destroy + NULL) can't
  be expressed via a direct cast. ✓
- **L7 detail #3 — ownership semantics**: Sawada **refactored
  `pgoutput_shutdown` to call the callback function** (single
  source of truth). We kept `pgoutput_shutdown`'s original code
  path separate (belt-and-suspenders). **We differed** — Sawada's
  is cleaner (F39 below).
- **Registration context**: Sawada registered on **`ctx->context`**;
  we registered on **`data->cachectx`** (child of ctx->context).
  Both work; Sawada's is one level higher. Semantically
  equivalent for this bug because both die on error unwinding.

## Diff size

| author    | files | insertions | deletions | net LOC change |
|-----------|------:|-----------:|----------:|---------------:|
| Sawada    |     1 |         24 |         5 |            +19 |
| Ours      |     2 |         45 |         0 |            +45 |

Ours is +26 lines heavier — most of that is:
- Comments on the new field in the header (F34 embed motivation)
- Comment on the reset-callback armed on cachectx
- The `pgoutput_shutdown` code is still there (Sawada replaced it
  with the callback call, so his `-5` corresponds to that; our
  `-0` reflects the belt-and-suspenders choice)

## Leak outcome

Both fixes NULL `RelationSyncCache` during context teardown. Both
prevent the UAF. Verified on our side by:
- Build clean, regress + isolation green (230 + 122 subtests).
- Reproducer (fail-then-retry SQL sequence) works semantically
  by inspection of the code path; empirical crash reproduction
  on macOS deferred per baseline.md caveat.

## Detailed structural comparison

### F34 revisit — embed vs separate palloc

**Sawada's choice:**
```c
MemoryContextCallback *mcallback;
mcallback = palloc0(sizeof(MemoryContextCallback));
mcallback->func = pgoutput_memory_context_reset;
MemoryContextRegisterResetCallback(ctx->context, mcallback);
```
Separate `palloc0` on the caller's `CurrentMemoryContext` (which
inside `pgoutput_startup` is the surrounding logical decoding
context). Doesn't touch `PGOutputData`.

**Our choice:**
```c
data->sync_cache_cb.func = pgoutput_relsync_reset_callback;
data->sync_cache_cb.arg = NULL;
MemoryContextRegisterResetCallback(data->cachectx,
                                   &data->sync_cache_cb);
```
Embed `MemoryContextCallback sync_cache_cb` as a field of
`PGOutputData` (added to `src/include/replication/pgoutput.h`
so it's shared between .c and any header consumer).

**Sawada's is preferable in this specific case.**

Reason: `PGOutputData` is in a public header
(`src/include/replication/pgoutput.h`). Adding a field is an ABI
change for anyone who reads that header — potentially other
loadable plugins that mirror the struct layout for interop.
Sawada's separate `palloc` sidesteps that.

Our F34 codification (from `fdw_directmodify_leak/comparison.md`)
recommended embedding based on the observation that the callback
struct in Tom's postgres_fdw fix was field-of-state. **The
recommendation was RIGHT for private state structs, but WRONG for
public-header state structs.** F38 codifies this caveat.

Postgres_fdw's `PgFdwDirectModifyState` is file-local (defined
inside `postgres_fdw.c`), so embed was free. pgoutput's
`PGOutputData` is public, so embed carries ABI risk.

### F35 — wrapper vs direct cast — aligned

Both fixes wrote a wrapper (`pgoutput_memory_context_reset` for
Sawada, `pgoutput_relsync_reset_callback` for us). The 2-op
cleanup (hash_destroy + NULL) genuinely needs a wrapper — F35
guidance held.

**Score: aligned.**

### F36 revisit — single owner via callback — mixed

**Sawada's shape:**
```c
static void
pgoutput_shutdown(LogicalDecodingContext *ctx)
{
    pgoutput_memory_context_reset(NULL);
}
```
`pgoutput_shutdown` becomes a **thin wrapper around the same
callback function**. Single source of truth for the cleanup;
happy path and error path invoke identical code.

**Our shape:**
```c
static void
pgoutput_shutdown(LogicalDecodingContext *ctx)
{
    if (RelationSyncCache)
    {
        hash_destroy(RelationSyncCache);
        RelationSyncCache = NULL;
    }
}
```
Kept `pgoutput_shutdown` unchanged; the callback duplicates the
same code inside `pgoutput_relsync_reset_callback`. Two copies
of the cleanup, drift risk.

**Sawada's is preferable.** F36 said "single owner via callback";
Sawada operationalized it as "single implementation shared by
the shutdown and the callback." Our belt-and-suspenders kept two
copies of the same code. F39 codifies this refinement of F36:
when the callback replaces (or shares with) an existing cleanup
path, refactor the old path to call the callback function too.

**Score: Sawada +1.**

### Registration context — `ctx->context` vs `data->cachectx`

**Sawada:** `MemoryContextRegisterResetCallback(ctx->context, mcallback);`

**Ours:** `MemoryContextRegisterResetCallback(data->cachectx, &data->sync_cache_cb);`

Both correct. `data->cachectx` is a child of `ctx->context`;
when `ctx->context` is reset, all children get reset first, then
`ctx->context` itself. Either fires during error unwind.

Sawada's choice is broader (fires whenever `ctx->context` resets,
regardless of cause). Ours is narrower (fires whenever `data->cachectx`
resets — the pgoutput-specific context).

Neither is clearly wrong; Sawada's is one level less coupled to
pgoutput-internal context layout.

## What we got right

1. **L6 approach E fired correctly.** Brainstorm §5 enumerated
   all 5 approaches with cited rejection reasoning for A-D. §6
   recommended E. Aligned with upstream.
2. **L7 sub-block fired in plan §7.** Named all 3 detail choices
   explicitly before Phase 3 — storage / function shape /
   ownership semantics. This is the primary success criterion
   for this run. **L7 delivered its intended value: the details
   were surfaced up front, so we can score them against
   upstream's choices rather than discovering the divergence
   post-hoc.**
3. **F30 grep-pass identified the 4 `RelationSyncCache = …`
   assignment sites** and correctly diagnosed the missing
   error-path NULL as the load-bearing invariant.
4. **F35 wrapper choice aligned with Sawada.** Both chose a
   wrapper because 2-op cleanup can't be expressed via direct
   cast.

## What we got wrong

- **F38 (new): F34's "embed in state struct" rule needs a
  public-header caveat.** Embedding is preferable when the state
  struct is file-local. When the state struct is exported via a
  public header, embedding carries ABI change risk — prefer the
  separate palloc instead. Codify in
  `knowledge/idioms/memory-contexts.md` §"Idioms for
  callback-based ownership."
- **F39 (new): F36's "single owner via callback" should include
  a refactor step for the pre-existing cleanup path.** When the
  callback is added as an error-path safety net for an existing
  cleanup path (like `pgoutput_shutdown`), the pre-existing
  cleanup should be refactored to call the same callback
  function — single source of truth. Belt-and-suspenders is safe
  but carries drift risk. Codify in the same section.

## Methodology validation verdict for the planner suite

**L7 delivered on its first live target.** The plan §7 sub-block
made the 3 implementation-detail choices EXPLICIT before Phase 3
started. That in turn made the Phase 4 comparison score-able at
the detail level — we can now see *exactly* where our design
diverged from Sawada's, and why. Without L7, this run's
comparison would have said "both used a reset callback"
without probing further. With L7, we surface F38+F39 as
codifiable corrections to F34+F36.

**Fifth calibration run summary:**

- **Phase 0 harness** — semi-strong. The UAF's signal shape is
  crash-on-retry, not RSS climb. F31 (reproducer verification)
  applied — took several thinking iterations to design the
  fail-then-retry SQL sequence. F37 (Phase 0.5 target-suite
  health check) applied — no target contrib suite; R13 gate =
  core regress + isolation.
- **Phase 1 triage** — strong.
- **Brainstorm** — strong. All 5 approaches A-E enumerated with
  cited rejection reasoning; approach E correctly recommended.
- **Plan** — strong. L7 sub-block fired with all 3 detail
  choices named explicitly. F30 grep-pass identified all
  `RelationSyncCache` assignment sites.
- **Implement** — strong. Single-phase fix in one commit; all
  R13 gates green. F35 wrapper was the right call (aligned with
  Sawada).
- **Compare** — strong. Detail-level comparison surfaced F38 +
  F39 as new codifications.

**Net assessment:** The planner suite produced a semantically
correct fix using the same approach category as Sawada's
upstream fix. Two implementation-detail choices diverged from
upstream (F38 embed-vs-palloc, F39 share-vs-duplicate cleanup);
both are corrections to F34+F36 that we now have data to
codify. **L7 turned Phase 4 from a "did we get the same
category?" check into a "did we make the same 3 detail choices?"
check — and where we didn't, we now know exactly why.**

## Findings to graduate

- **F38 — F34 needs a public-header caveat.** When the state
  struct is in a public header, prefer separate palloc; when
  file-local, prefer embed. Codify in
  `knowledge/idioms/memory-contexts.md`.
- **F39 — F36 should include "share the implementation".** When
  the callback replaces or duplicates an existing cleanup path,
  refactor the pre-existing path to call the callback function
  — single source of truth, no drift risk. Codify in same file.

No new L-lessons this run — F38 + F39 are refinements of prior
F34 + F36, not new lessons.

## Cross-references

- baseline.md — bug etiology from parent-pin source alone
- triage.md — L7 stress-test target selection
- brainstorm.md — 5 approaches enumerated + L7 detail choices
- plan.md — §7 L7 sub-block + F30 grep-pass
- `.claude/skills/pg-feature-plan/SKILL.md` §7 L7 sub-block
- `knowledge/idioms/memory-contexts.md` §"Idioms for
  callback-based ownership" (F34+F35+F36; F38+F39 to be
  appended)
- upstream `b46efe90482d94dec7500d09f6f29fbb2f6310d` — Sawada's
  actual fix
