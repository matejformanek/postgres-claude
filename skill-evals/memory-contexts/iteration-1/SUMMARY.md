# Iteration 1 — memory-contexts SKILL.md eval

## Pass rates

|              | passed | total | rate  |
|--------------|--------|-------|-------|
| with_skill   | 22     | 22    | 100%  |
| baseline     | 16     | 22    | 72.7% |
| **delta**    | **+6** |       | **+27.3 pp** |

## Per-eval

| Eval | Question                              | with_skill | baseline |
|------|---------------------------------------|------------|----------|
| 1    | SRF tuple corruption between calls    | 7/7        | 4/7      |
| 2    | Relcache build-callback scoping       | 7/7        | 5/7      |
| 3    | 2 GB alloc / MaxAllocSize / context   | 8/8        | 7/8      |

## Top failure modes (in baseline)

1. **Missing per-tuple-context reset timing** — baseline knew the context
   is short-lived but didn't pin down "reset at the *start* of the cycle"
   (matters for understanding why returning per-tuple-context memory works
   the way it does).
2. **No file:line cites** — baseline never cited a source file or knowledge
   doc. Honest call: this is the cite-or-tag discipline that the skill
   enforces but baseline knowledge can't conjure.
3. **`MemoryContextDelete` recursion not mentioned** — baseline gave the
   right pattern but didn't explain WHY a child context works (because
   delete cascades).

## What the skill genuinely adds beyond baseline

- Cite-or-tag discipline (every assertion #6 / #7 about cites).
- Exact constant names (`MaxAllocSize`, `MaxAllocHugeSize = SIZE_MAX/2`).
- Tuple-context reset *timing* (start, not end).

## What baseline already knew well (skill doesn't add lift)

- The `MCXT_ALLOC_HUGE` / `palloc_extended` API surface.
- That Slab/Bump have allocation-pattern restrictions.
- The general "child-of-CacheMemoryContext + store-on-cache-entry" pattern.
- SRF helpers (`SRF_FIRSTCALL_INIT`, `multi_call_memory_ctx`).

## Top SKILL.md improvement proposed (see proposed-edits.md)

**Extend the "Picking the right context" lifetime table with 3 rows for
the actually-common new-code cases**: SRF value-per-call
(`multi_call_memory_ctx`), SRF materialize (`ecxt_per_query_memory`), and
aggregate transition state (`AggCheckCallContext` aggcontext). The skill
currently lists generic xact/portal/cache lifetimes but skips the two
function-shaped APIs every new contributor first writes. Also tighten the
huge-allocation bullet by quoting the exact error string and listing
which context types support it.
