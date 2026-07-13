# Phase 2 brainstorm — gin_parallel_merge_leak (blind)

## §0 Usage surface

Grep pass in parent-pin `src/backend/access/gin/gininsert.c` for
`ginEntryInsert` callers + relevant memory-context patterns.

**Existing GinBuildState machinery** (parent-pin lines 138-175):

- `MemoryContext tmpCtx;` (line 144) — per-tuple temporary context
  used by the SERIAL build path.
- `MemoryContext funcCtx;` (line 145) — per-batch context used by
  the RETAIL insert-and-build path.

Both live in `GinBuildState`, which is what `_gin_parallel_merge`
receives as `state`.

**ginEntryInsert() callers:**

| Site (parent-pin line) | Function                    | Memory-context pattern              |
|-----------------------:|-----------------------------|-------------------------------------|
|                    468 | `ginBuildCallback`          | switch to `tmpCtx` at 447, reset at 472 (per-batch) |
|                    734 | serial `ginbuild`           | switch to `funcCtx` at 425 (implicitly per-tuple in `ginHeapTupleBulkInsert`) |
|                    819 | serial `ginInsertBAEntries` | no reset (short-lived caller)       |
|                   1688 | **`_gin_parallel_merge`**   | **NONE — this is the leak site**    |
|                   1714 | **`_gin_parallel_merge`**   | **NONE — this is the leak site**    |
|                   1738 | **`_gin_parallel_merge`**   | **NONE — this is the leak site**    |

Three leak sites, all inside the same `while` / `if` blocks of
`_gin_parallel_merge` at lines 1670-1748.

**Load-bearing site (R15a):** any single leak site will do — the
same fix pattern applies to all three. Pick line 1688 (the
GinBufferCanAddKey flush path) as the canonical anchor since it's
the most frequently taken.

## §0.5 Existing-mechanism survey

Grep `MemoryContextReset` in `src/backend/access/gin/`:

| Site | Purpose |
|------|---------|
| `gininsert.c:436` | ginHeapTupleBulkInsert: reset funcCtx after batch |
| `gininsert.c:472` | ginBuildCallback: reset tmpCtx after batch |
| `gininsert.c:516` | ginFlushBuildState: reset tmpCtx after flush |
| `ginfast.c` (multiple) | fastupdate insertion paths |

The **per-batch context-switch-then-reset idiom** is well
established in this file. `_gin_parallel_merge` is the outlier.

## §1 Problem statement

`_gin_parallel_merge` calls `ginEntryInsert` three times per
merge iteration (or once per iteration in some paths). Each call
may allocate a new leaf tuple + split-page metadata in whatever
context is current on entry. `_gin_parallel_merge` doesn't
switch contexts, so allocations land in `CurrentMemoryContext` at
entry — which for a `CREATE INDEX` portal is `PortalContext`.
PortalContext lives for the entire index build; allocations
accumulate.

For normal opclasses the leak is small (bytes per tuple). For
custom opclasses with **large keys** (e.g. text arrays with
long strings, jsonb path expressions), the per-insert allocation
scales with key size and OOMs on large builds.

## §2 Scope contract

**IN scope:**
- Add per-insert context-reset around the 3 `ginEntryInsert`
  sites in `_gin_parallel_merge`.

**OUT of scope:**
- Reset frequency change in the serial build path.
- New context creation in a nested loop (reuse existing state
  fields if possible).
- Similar leaks in other places (e.g. `_gin_parallel_scan_and_build`).

## §5 Candidate approaches

### Approach A — Reset tmpCtx after each ginEntryInsert

Switch to `state->tmpCtx` before each `ginEntryInsert`, then
`MemoryContextReset(state->tmpCtx)` after. Reuses the existing
field; no allocation of a new context. Aligns with the
`ginBuildCallback` pattern at line 447-472.

**Pros:**
- Uses existing state field (no struct change).
- Aligns with the sibling serial-build pattern.
- Minimal diff (~10 lines).

**Cons:**
- If tmpCtx has residue from a prior phase (`_gin_parallel_heapscan`
  or the earlier setup in `_gin_parallel_merge` itself), reset
  discards it. Need to verify `tmpCtx` is safe to reset here.

**R14 test implications:** parallel GIN build with wide keys — see
baseline.md canary.

### Approach B — Create a new sub-context per invocation

Create a fresh `AllocSetContextCreate(CurrentMemoryContext,
"gin merge inserts", …)` at the top of `_gin_parallel_merge`,
switch to it around each `ginEntryInsert`, delete at the end.

**Pros:**
- Doesn't touch `tmpCtx` (avoids the "safe to reset here?" question).
- Explicit lifetime scope.

**Cons:**
- Extra context creation cost.
- One extra field-equivalent local vs. reusing `state->tmpCtx`.

### Approach C — Reset frequency: once per iteration vs once per insert

Sub-question: reset AFTER each `ginEntryInsert` (per commit
message's "reset after each insert") or ONCE at the end of the
`while` loop iteration? The commit message says "after each
insert" — fine-grained, three resets per iteration.
Coarse-grained would reset once at the end of the outer loop
body.

Fine-grained is more aggressive (bounds each insert's
transient); coarse-grained is simpler but leaves 2-3 inserts of
residue between resets.

Commit message aligns with fine-grained: "More frequent resets
don't seem to hurt performance, it may even help it a bit."

### Approach D — Switch context ONCE at function entry, reset at end

Switch to `tmpCtx` once at function entry, do all iterations of
the loop, `MemoryContextReset(tmpCtx)` before returning.
Doesn't bound per-iteration accumulation — same shape as the
bug just delayed by one function call. Rejected.

### Approach E — Not applicable

L6 approach-E ("restructure control flow to match new invariant")
does not fire on this target because:
- `_gin_parallel_merge` has 1 return path (line 1755, after
  cleanup).
- The invariant "reset tmpCtx after each insert" doesn't require
  restructuring; a switch/reset pair inline at each of the 3
  sites is sufficient.

L7 sub-block (callback-based approach detail) also does not fire
— the fix is not callback-based.

## §6 Recommended approach

**Approach A + fine-grained resets (per-insert).** Reuse
`state->tmpCtx`. Switch before each `ginEntryInsert`, switch
back + reset after. Three switch/insert/reset triples inside the
`while` loop body.

Rationale:
- Aligns with the sibling serial-build pattern (`ginBuildCallback`
  at line 447).
- Commit message explicitly recommends "after each insert."
- `state->tmpCtx` is available and its residue at this call site
  is not relied upon (the merge phase runs after
  `_gin_parallel_heapscan` completes and `tuplesort_performsort`
  has been called; no live pointers into tmpCtx from earlier
  work).

## §7 Load-bearing test

The 1M-row × 3KB-key `CREATE INDEX ... USING gin` from
baseline.md. Backend RSS during merge phase flat on post-fix,
climbing on parent.

## §8 Open questions

1. Is `state->tmpCtx` initialized at this point? Check
   `_gin_begin_parallel` or `_gin_leader_participate_as_worker`
   for tmpCtx setup.
2. Do we need a switch-back between iterations, or is
   `MemoryContextSwitchTo(tmpCtx)` once at function entry
   sufficient? Prefer explicit switch/reset per site — matches
   the serial-build pattern which does per-batch switch/reset.
