# plancache.h

- **Source path:** `source/src/include/utils/plancache.h`
- **Lines:** 256
- **Last verified commit:** `ef6a95c7c64`
- **Companion files:** `plancache.c` (impl), `nodes/params.h` (ParamListInfo), `tcop/cmdtag.h`, `utils/queryenvironment.h`, `utils/resowner.h`.

## Purpose

Public surface for the plan cache: defines `CachedPlanSource`, `CachedPlan`, `CachedExpression`, the `PlanCacheMode` GUC enum, the magic constants, the `PostRewriteHook` callback type, and the entire create/complete/save/get/release lifecycle.

## Top-of-file comment

> "Plan cache definitions. See plancache.c for comments." [plancache.h:3-6]

## Public surface

- **GUC enum**: `PlanCacheMode { AUTO, FORCE_GENERIC_PLAN, FORCE_CUSTOM_PLAN }` (31). Backing GUC `plan_cache_mode` (PGDLLIMPORT, 39).
- **Hook type**: `PostRewriteHook(querytree_list, arg)` (42).
- **Magic constants**: `CACHEDPLANSOURCE_MAGIC = 195726186` (44), `CACHEDPLAN_MAGIC = 953717834` (45), `CACHEDEXPR_MAGIC = 838275847` (46).
- **Types**: `CachedPlanSource` (105), `CachedPlan` (159), `CachedExpression` (187).
- **Lifecycle**: `InitPlanCache`, `ResetPlanCache`, `ReleaseAllPlanCacheRefsInOwner`, `CreateCachedPlan`, `CreateCachedPlanForQuery`, `CreateOneShotCachedPlan`, `CompleteCachedPlan`, `SetPostRewriteHook`, `SaveCachedPlan`, `DropCachedPlan`, `CachedPlanSetParentContext`, `CopyCachedPlan`.
- **Query**: `CachedPlanIsValid`, `CachedPlanGetTargetList`.
- **Execute**: `GetCachedPlan`, `ReleaseCachedPlan`, `CachedPlanAllowsSimpleValidityCheck`, `CachedPlanIsSimplyValid`.
- **Cached exprs**: `GetCachedExpression`, `FreeCachedExpression`.

## Key types

- **`CachedPlanSource`** (105) — has TWO memory contexts: `context` (for the struct + raw text + source parse tree) and `query_context` (for the rewritten querytree and its dependency lists). This split is so cache inval can free just `query_context` and rebuild it. [from-comment, plancache.h:92-95]
- **`CachedPlan`** (159) — `refcount`-managed; includes "the link from the parent CachedPlanSource (if any)" as one count. Goes away exactly when refcount→0. Subsidiary data lives in `context`. `saved_xmin` for transient plans. [from-comment, plancache.h:150-158]
- **`CachedExpression`** (187) — minimal: just `expr` (planned form), `is_valid`, plus the same dependency tracking machinery (`relationOids`, `invalItems`). "the caller must notice the !is_valid status and discard the obsolete expression without reusing it." [from-comment, plancache.h:175-186]

## Key invariants

- **Saved vs unsaved CachedPlanSource.** Unsaved ones can be used for planning but **do not receive sinval events** — they live in transient storage. Calling `SaveCachedPlan` is what wires the source into the global dlist (saved_plan_list in plancache.c) and into the invalidation-callback path. [from-comment, plancache.h:80-83]
- **CachedPlan can outlive its CachedPlanSource.** Refcounting is the contract. [from-comment, plancache.h:76-78]
- **Oneshot plans**: no copying, no invalidation, no separate memory context. Always treated as unsaved. Caller cannot free memory short of clearing the entire surrounding context. [from-comment, plancache.h:96-103]
- **Read-only contract on generic plans**: "If we are using a generic cached plan then it is meant to be re-used across multiple executions, so callers must always treat CachedPlans as read-only." [from-comment, plancache.h:69-72]
- **Two ways to represent source**: `raw_parse_tree` XOR `analyzed_parse_tree`. If both NULL, it's the empty query. The analyzed-tree path skips rewriting-only changes — "we expect that cache invalidation need not affect the parse-analysis results, only the rewriting and planning steps." [from-comment, plancache.h:56-65]

## Confidence tag tally

verified-by-code: 1 — from-comment: 7 — from-readme: 0 — inferred: 0 — unverified: 0

## Synthesized by
<!-- backlinks:auto -->
- [idioms/plan-cache.md](../../../../idioms/plan-cache.md)
- [idioms/prepared-statement-plancache.md](../../../../idioms/prepared-statement-plancache.md)
