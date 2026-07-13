# Phase 2 plan — gin_parallel_merge_leak (blind)

## §1 Problem statement

`_gin_parallel_merge` calls `ginEntryInsert` three times per
outer-loop iteration (canonical + tail sites). Under the parent
pin, `ginEntryInsert`'s allocations land in
`CurrentMemoryContext` at entry to `_gin_parallel_merge`, which
for `ginbuild`'s caller is `PortalContext`. Allocations accumulate
for the whole index-build lifetime and OOM on wide-key custom
opclasses.

## §2 Design

Wrap each `ginEntryInsert` call inside `_gin_parallel_merge`
with a `MemoryContextSwitchTo(state->tmpCtx)` /
`MemoryContextSwitchTo(oldCtx)` / `MemoryContextReset(state->tmpCtx)`
triple. Reuses the existing `tmpCtx` field of `GinBuildState`
(created at `gininsert.c:634`, before this function is called).

This is Approach A from brainstorm §5, chosen over B (new
context) because A reuses existing state field with no struct
change.

**L6 approach-E does NOT fire on this target.** The function
has 1 exit path and the fix is inline switch/reset around each
call, no control-flow restructure.

**L7 sub-block does NOT fire on this target.** The fix is not
callback-based.

## §3 Files that change — at parent pin `e83a8ae4472`

| File                                          | Change  | Size          | Summary                                        |
|-----------------------------------------------|---------|--------------|------------------------------------------------|
| `src/backend/access/gin/gininsert.c`          | modify  | small (~15L)  | Add 3 switch/reset triples inside `_gin_parallel_merge` at parent-pin lines 1688, 1714, 1738. |

**Estimated diff size:** ~12-18 lines inserted, 0 removed. Well
within the target commit's `+12/-0` shape mentioned in triage.

## §4 Catalog + on-disk impact

None.

## §5 WAL impact

None.

## §6 Locking + concurrency

None — leader phase runs after all workers have completed and
before their tuplesorts are freed. Purely single-threaded within
`_gin_parallel_merge`.

## §7 Memory + resource management — F30 grep-verified ownership

**Ownership claim under test:**
> Allocations made by `ginEntryInsert()` during
> `_gin_parallel_merge` are transient — needed only to construct
> and flush one leaf tuple (or its overflow) into the index
> pages. They are NOT referenced after the `ginEntryInsert()`
> call returns.

**F30 grep verification:**

```
grep -RnE 'ginEntryInsert\(' \
    src/backend/access/gin/gininsert.c
```

Result — 5 call sites:

| Site                                  | Reset cadence (parent pin)                  |
|---------------------------------------|---------------------------------------------|
| gininsert.c:468 `ginBuildCallback`    | switch to tmpCtx at 447, reset at 472 (per-batch) |
| gininsert.c:734 (retail insert loop)  | funcCtx switched at 425, deleted at 741     |
| gininsert.c:819 (BAEntries loop)      | outer per-tuple context implicitly bounds it |
| gininsert.c:1688 `_gin_parallel_merge`| **NONE (fix target)**                        |
| gininsert.c:1714 `_gin_parallel_merge`| **NONE (fix target)**                        |
| gininsert.c:1738 `_gin_parallel_merge`| **NONE (fix target)**                        |

The invariant "callers of `ginEntryInsert` bound its transient
allocations via a context reset" is followed by 3/6 callers.
`_gin_parallel_merge`'s 3 sites are the outliers.

**Verified: no double-reset risk.** `state->tmpCtx` at the entry
to `_gin_parallel_merge` has been quiescent since the last
worker-join in `_gin_begin_parallel` / `_gin_parallel_heapscan`
(which don't touch it). Any residue at this point is safe to
discard.

## §8 Phased implementation

Single phase.

### Phase 1 — Add per-insert switch/reset around all 3 sites

**Files:** `src/backend/access/gin/gininsert.c`.

**Concrete edits:** at each of the 3 `ginEntryInsert` sites in
`_gin_parallel_merge` (parent-pin lines 1688, 1714, 1738),
replace:

```c
ginEntryInsert(&state->ginstate,
               buffer->attnum, buffer->key, buffer->category,
               buffer->items, buffer->nitems, &state->buildStats);
```

with:

```c
oldCtx = MemoryContextSwitchTo(state->tmpCtx);
ginEntryInsert(&state->ginstate,
               buffer->attnum, buffer->key, buffer->category,
               buffer->items, buffer->nitems, &state->buildStats);
MemoryContextSwitchTo(oldCtx);
MemoryContextReset(state->tmpCtx);
```

Add `MemoryContext oldCtx;` local at the top of
`_gin_parallel_merge`.

**Phase-end check** (R13 scope — regress + isolation + RSS canary):

```
meson test --no-rebuild --suite regress --suite isolation
```

Plus the manual proxy from baseline.md — 1M-row × 3KB-key
`CREATE INDEX` shows flat RSS on post-fix, climbing on parent.

**Exit condition:**
1. Regress + isolation green.
2. `regress/sql/gin.sql` still exercises the parallel path
   (via `SET max_parallel_maintenance_workers` in the test).
3. RSS canary shows expected reduction.

## §9 Test surface

No dedicated regress row needed — the existing
`src/test/regress/sql/gin.sql` exercises index build paths and
would catch a functional regression. The specific "custom
opclass with large keys" reproducer is too big for regress
(~seconds+ per row) — flag for follow-up TAP if we ever
upstream.

## §10 Docs impact

None.

## §11 Backport

Upstream (per commit message, back-patched to 17 or so). Our
worktree targets master at `e83a8ae4472`.

## §12 Cross-references

- Idiom: `knowledge/idioms/memory-contexts.md` (short-lived
  context reset pattern — established in ginBuildCallback).
- Scenario: `knowledge/scenarios/fix-memory-leak.md` §Step 0.4
  reproducer verification.
- Retro: `sessions/2026-07-13-five-trilogy-runs-retro.md`
  (recommended next runs — this target picked per those
  criteria).

## §13 High-severity unknowns

1. Is `state->tmpCtx` reset elsewhere between
   `_gin_parallel_heapscan` return and `_gin_parallel_merge`
   entry? Grep confirms NO — tmpCtx is untouched between these
   two functions.
2. Does `ginEntryInsert` retain pointers to allocations across
   its return? Grep for stateful callbacks: no — `ginEntryInsert`
   writes to disk buffers and returns; nothing retained.
3. Is there parallelism inside `_gin_parallel_merge` beyond
   worker-side? No — this is leader-only merge.

## §14 Phase-4 comparison hook

Pre-declared axes for comparison against `1681a70df3d68`:

1. **Which context did upstream reuse?** We chose `state->tmpCtx`.
   Alternatives: create a fresh one, use `state->funcCtx`.
2. **Reset frequency: per-insert or per-outer-iteration?** We
   chose per-insert (3 resets per iteration). Alternatives: once
   per while-iteration.
3. **Switch-inside-braces vs switch-once-at-top?** We chose
   switch/insert/switch-back per call (matches ginBuildCallback
   pattern). Alternatives: switch once at function entry, reset
   in inner loop, restore at exit.
4. **Diff size.** We estimated +12-18 lines. Upstream is +12/-0
   per the triage's earlier reading.

This run's primary calibration criterion is **not** L6/L7 firing
(they shouldn't) — it's whether the trilogy correctly handles a
non-callback, non-restructure fix without over-firing the L6/L7
adversarial passes.
