# Proposed SKILL.md edits — iteration 1

The skill scores 100% with-skill vs 73% baseline. The lift is real (~27 pp)
but concentrated on cite-discipline assertions. The skill should add
content that the baseline model genuinely does NOT know, not just better
citations. Three concrete gaps to close:

---

## Edit 1 — Add SRF + aggregate-trans patterns (biggest gap)

The lifetime table covers tuple / statement / xact / cache / forever,
but the two MOST common "where do I put this?" cases for new code —
SRFs and aggregates — are missing. They have specific helper APIs the
baseline already half-knows; the skill should pin them down.

**old_string:**
```
| You need data to live until... | Allocate in / switch to |
|---|---|
| End of one tuple cycle | the executor's per-tuple ExprContext (usually already `CurrentMemoryContext` in expression eval) |
| End of one statement | per-query context (executor sets this up; `estate->es_query_cxt`) or `MessageContext` |
| End of current (sub)transaction | `CurTransactionContext` |
| End of top-level transaction | `TopTransactionContext` |
| Lifetime of one portal | the portal's private context (`PortalContext` when active) |
| Lifetime of a cache entry | a child of `CacheMemoryContext` you control |
| Backend lifetime / forever | `TopMemoryContext` — but only if truly forever |
```

**new_string:**
```
| You need data to live until... | Allocate in / switch to |
|---|---|
| End of one tuple cycle | the executor's per-tuple ExprContext (usually already `CurrentMemoryContext` in expression eval); reset at the *start* of the next cycle |
| End of one statement | per-query context (executor sets this up; `estate->es_query_cxt` or `econtext->ecxt_per_query_memory`) or `MessageContext` |
| Across SRF calls (value-per-call) | `funcctx->multi_call_memory_ctx` from `SRF_FIRSTCALL_INIT()` |
| Across SRF calls (materialize) | `rsinfo->econtext->ecxt_per_query_memory` for the tuplestore |
| Across aggregate transitions (per group) | the aggcontext from `AggCheckCallContext(fcinfo, &aggcontext)` |
| End of current (sub)transaction | `CurTransactionContext` |
| End of top-level transaction | `TopTransactionContext` |
| Lifetime of one portal | the portal's private context (`PortalContext` when active) |
| Lifetime of a cache entry | a child of `CacheMemoryContext` you control (delete the child on invalidation; delete is recursive) |
| Backend lifetime / forever | `TopMemoryContext` — but only if truly forever |
```

**rationale:** Eval 1 baseline already knew about `multi_call_memory_ctx`
and `ecxt_per_query_memory` — the skill should at minimum match that,
because SRF/aggregate trans-state are the #1 and #2 cases where new
hackers ask "what context?". Adding them costs 3 rows and removes any
ambiguity. Also makes the "reset at start" point explicit (assertion 1.2
that baseline missed).

---

## Edit 2 — Add huge-alloc cap call-out box

The `MCXT_ALLOC_HUGE` bullet is one line and easy to miss. The 1 GB
error message ("invalid memory alloc request size") is the most-googled
PG-internals symptom and deserves named recognition.

**old_string:**
```
- **Single-allocation cap is `MaxAllocSize` (1 GB - 1)** for regular palloc.
```

**new_string:**
```
- **Single-allocation cap is `MaxAllocSize` (1 GB - 1)** for regular palloc.
  Exceeding it raises `errmsg("invalid memory alloc request size %zu")` —
  switch to `MemoryContextAllocHuge` / `palloc_extended(..., MCXT_ALLOC_HUGE)`,
  capped at `MaxAllocHugeSize = SIZE_MAX/2`. Use `repalloc_huge` to grow.
  Slab is fixed-size so N/A; Bump cannot be repalloc'd; AllocSet and
  Generation both support huge chunks (AllocSet routes any chunk ≥ 8 KB
  straight to malloc).
```

**rationale:** Eval 3 showed baseline already knows most of this from
general PG knowledge; the skill adds value only by making the error
message string and the context-type matrix explicit so the reader doesn't
have to assemble it themselves.

---

## Edit 3 — Add a concrete relcache pattern under "Creating a context"

**old_string:**
```
```c
MemoryContext cxt = AllocSetContextCreate(parent,
                                          "my purpose",          /* MUST be a literal */
                                          ALLOCSET_DEFAULT_SIZES);
MemoryContextSetIdentifier(cxt, dynamic_name);  /* if you need a runtime label */
```
```

**new_string:**
```
```c
MemoryContext cxt = AllocSetContextCreate(parent,
                                          "my purpose",          /* MUST be a literal */
                                          ALLOCSET_DEFAULT_SIZES);
MemoryContextSetIdentifier(cxt, dynamic_name);  /* if you need a runtime label */
```

Cache-entry pattern (per-relation child of `CacheMemoryContext`, blown
away as a unit on invalidation — `MemoryContextDelete` is recursive):

```c
MemoryContext rulescxt = AllocSetContextCreate(CacheMemoryContext,
                                               "relation rules",
                                               ALLOCSET_SMALL_SIZES);
MemoryContextCopyAndSetIdentifier(rulescxt, RelationGetRelationName(rel));
oldcxt = MemoryContextSwitchTo(rulescxt);
/* build cache contents; everything lands in rulescxt */
MemoryContextSwitchTo(oldcxt);
rel->rd_rulescxt = rulescxt;            /* invalidation: MemoryContextDelete */
```
See `source/src/backend/utils/cache/relcache.c` for the real precedent
(`rd_rulescxt`, `rd_indexcxt`, `rd_pdcxt`, …).
```

**rationale:** Eval 2 baseline knew the pattern abstractly but didn't
mention recursion of Delete; making the worked example concrete catches
that and reinforces the "literal name + identifier" rule.

---

## Not changing

- The "Common mistakes" list is already strong — every assertion that
  with_skill answers got right traced back to it.
- The Bump-context restriction text is well-placed; no changes needed.
- The PG_TRY volatile rule is correctly scoped (eval set didn't test it,
  but it's not bloating the skill).
