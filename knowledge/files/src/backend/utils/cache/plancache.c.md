# plancache.c

- **Source path:** `source/src/backend/utils/cache/plancache.c`
- **Lines:** 2386
- **Last verified commit:** `ef6a95c7c64`
- **Companion files:** `plancache.h` (public `CachedPlanSource`, `CachedPlan`, `CachedExpression`), `inval.c` (delivers the invalidation callbacks this file registers), `parser/analyze.c` + `rewrite/rewriteHandler.h` + `optimizer/optimizer.h` (replan path), `tcop/postgres.c` + `commands/prepare.c` (chief callers).

## Purpose

Backs PREPARE/EXECUTE, SPI prepared queries, and `CachedExpression` (cached scalar exprs in plpgsql etc.). Two responsibilities: (1) **generic-vs-custom plan policy** (`choose_custom_plan`), (2) **invalidation tracking** for plans whose dependent catalog objects have changed. [from-comment, plancache.c:6-13]

## Top-of-file comment (verbatim — key paragraphs)

> "The plan cache manager has two principal responsibilities: deciding when to use a generic plan versus a custom (parameter-value-specific) plan, and tracking whether cached plans need to be invalidated because of schema changes in the objects they depend on." [plancache.c:6-9]

> "Cache invalidation is driven off sinval events. Any CachedPlanSource that matches the event is marked invalid, as is its generic CachedPlan if it has one. When (and if) the next demand for a cached plan occurs, parse analysis and/or rewrite is repeated to build a new valid query tree, and then planning is performed as normal. We also force re-analysis and re-planning if the active search_path is different from the previous time or, if RLS is involved, if the user changes or the RLS environment changes." [plancache.c:14-21]

> "Currently, we track exactly the dependencies of plans on relations, user-defined functions, and domains. On relcache invalidation events or pg_proc or pg_type syscache invalidation events, we invalidate just those plans that depend on the particular object being modified. … We also watch for inval events on certain other system catalogs, such as pg_namespace; but for them, our response is just to invalidate all plans." [plancache.c:30-39]

## Public surface

- **Init**: `InitPlanCache` (148) — registers four callbacks (relcache; PROCOID; TYPEOID; NAMESPACEOID/OPEROID/AMOPOPID/FOREIGNSERVEROID/FOREIGNDATAWRAPPEROID).
- **Create / complete / save / drop**: `CreateCachedPlan` (185), `CreateCachedPlanForQuery` (265), `CreateOneShotCachedPlan` (300), `CompleteCachedPlan` (393), `SaveCachedPlan` (547), `DropCachedPlan` (591).
- **Execute path**: `GetCachedPlan` (1297), `ReleaseCachedPlan` (1428), `CachedPlanIsValid` (1766), `CachedPlanSetParentContext` (1635), `CopyCachedPlan` (1673).
- **Cached expressions**: `GetCachedExpression` (1816), `FreeCachedExpression` (1873).
- **Global reset**: `ResetPlanCache` (2328).
- **Callbacks** (static but the heart of the invalidation logic): `PlanCacheRelCallback` (2126), `PlanCacheObjectCallback` (2210), `PlanCacheSysCallback` (2319).

## Key types / structs

- `CachedPlanSource` (in plancache.h) — long-lived; holds raw parse tree, querytree (rewritten), dependency Oid list (`relationOids`), `invalItems` (PROCOID/TYPEOID hashes), `gplan` (generic CachedPlan if any), `is_valid`, `is_oneshot`, `is_saved`, `magic == CACHEDPLANSOURCE_MAGIC`, `generation`, `num_custom_plans`, `total_custom_cost`, `generic_cost`, `cursor_options`.
- `CachedPlan` (in plancache.h) — one specific generation of plans; `stmt_list` of PlannedStmts, `is_valid`, `refcount`, `saved_xmin` (used for "transient" plans depending on data visible only under a given xmin).
- `CachedExpression` — bare-bones invalidation tracking for one Node.
- `PlanInvalItem` — `{int cacheId; uint32 hashValue;}`: dependency on one syscache row.
- Two backend-global dlists: `saved_plan_list` (84) for plans subject to inval, and `cached_expression_list` (89).

## Key invariants and locking

- **`InitPlanCache` registration set is fixed.** Plan cache only listens to: relcache invals; PROCOID, TYPEOID syscaches (fine-grained); NAMESPACEOID, OPEROID, AMOPOPID, FOREIGNSERVEROID, FOREIGNDATAWRAPPEROID (coarse — wipes everything). [verified-by-code, plancache.c:148-158]
- **Two-step create**. `CreateCachedPlan` (called after raw_parser, before analyze) sets `magic = CACHEDPLANSOURCE_MAGIC`, copies the raw tree into a fresh memory context that is a child of CurrentMemoryContext (so a partial build dies cleanly on ereport). `CompleteCachedPlan` (after analyze + rewrite) attaches the querytree and dependency info, optionally reparents into long-lived context, and ONLY THEN can `SaveCachedPlan` add it to `saved_plan_list`. [from-comment, plancache.c:161-178]
- **Save-after-complete contract.** A plan only receives sinval events after `SaveCachedPlan` puts it on the dlist. Until then, builders need not worry about callbacks invalidating a half-built plan. [verified-by-code, plancache.c:547-590]
- **Invalidation = mark only.** `PlanCacheRelCallback` and `PlanCacheObjectCallback` only set `is_valid = false` on the source (and on `gplan` if present). The next `GetCachedPlan` triggers `RevalidateCachedQuery` to re-analyze/re-rewrite, then `BuildCachedPlan` to re-plan. Replan can throw an error (e.g. dropped column). [from-comment, plancache.c:14-29; verified-by-code]
- **Dependency match is hash-based for syscache, OID-based for relcache.** `relationOids == NIL` ⇒ no relation deps ⇒ skip even on `relid == InvalidOid` sweep; otherwise either match the specific oid or treat `InvalidOid` as "all". For syscache the test is `cacheId == cacheid && (hashvalue == 0 || stored.hashValue == hashvalue)`. [verified-by-code, plancache.c:2148-2199, 2233-2248]
- **Generic plan deps ⊇ querytree deps.** The comment at 2156-2160 / 2250-2253 explicitly notes "The generic plan, if any, could have more dependencies than the querytree does, so we have to check it too." Both lists must be scanned. [from-comment]
- **`ResetPlanCache` must NOT invalidate transaction-control statements** ("particularly not ROLLBACK, because they may need to be executed in aborted transactions when we can't revalidate them (cf bug #5269)"). Gate is `StmtPlanRequiresRevalidation`. [from-comment, plancache.c:2342-2352]
- **Generic-plan policy** (`choose_custom_plan`, 1175): one-shot ⇒ custom; no params ⇒ generic; planner no-op ⇒ generic; GUC `plan_cache_mode` overrides; cursor flags `CURSOR_OPT_GENERIC_PLAN` / `CURSOR_OPT_CUSTOM_PLAN` override; **the first 5 invocations are always custom** so we can measure custom cost; afterwards generic wins iff `generic_cost < avg_custom_cost` (with planner cost included in custom). [verified-by-code, plancache.c:1175-1222; from-comment, 1202-1216]
- **Transient plans + saved_xmin.** If any `PlannedStmt.transientPlan` is true (e.g. uses a temp index, or depends on a snapshot-only invariant), the CachedPlan's `saved_xmin` is set to `TransactionXmin` and the plan is only reusable while `RecentXmin` hasn't advanced past it (test in `CheckCachedPlan`). [verified-by-code, plancache.c:1143-1154]
- **ResourceOwner integration.** `CachedPlan` refcounts are tracked via the `planref_resowner_desc` (117). Releases happen at `RESOURCE_RELEASE_AFTER_LOCKS` so executor locks are released first. [verified-by-code, plancache.c:117-124]

## Functions of note

1. **`GetCachedPlan`** (1297) — the hot path. Calls `RevalidateCachedQuery` if invalid; calls `choose_custom_plan`; either reuses `gplan` (after `CheckCachedPlan`) or calls `BuildCachedPlan` to make a new custom plan; if custom, accumulates `num_custom_plans` and `total_custom_cost`; pins via ResourceOwner.
2. **`RevalidateCachedQuery`** (684) — re-runs parse analysis + rewrite; updates `relationOids` and `invalItems`. Detects (and may reject) tupdesc changes if caller did not allow them. [from-comment, plancache.c:22-28]
3. **`PlanCacheRelCallback`** (2126) — relcache-driven path. Two-stage check: querytree's `relationOids`, then any not-yet-invalidated `gplan`'s per-stmt `relationOids`. Marks invalid via `is_valid = false`. Same logic also drains `cached_expression_list`.
4. **`PlanCacheObjectCallback`** (2210) — PROCOID/TYPEOID handler. Walks `invalItems` matching `cacheId` + hash. Same source + gplan two-stage logic.
5. **`PlanCacheSysCallback`** (2319) — for NAMESPACEOID/OPEROID/etc. just calls `ResetPlanCache`. Cheap correctness over fine-grained tracking.
6. **`choose_custom_plan`** (1175) — see invariants. The "5 customs then compare averaged cost" heuristic is *the* PREPARE-vs-EXECUTE behavior most users notice.

## Cross-references

- **Called by**: `commands/prepare.c` (PREPARE/EXECUTE), `executor/spi.c` (SPI plans), `tcop/postgres.c` (extended-protocol Parse/Bind/Execute), `pl/plpgsql` (via SPI), `commands/copyfrom.c` (cached-expression).
- **Calls into**: parser (`parse_analyze_fixedparams`, etc.), rewriter (`QueryRewrite`), planner (`pg_plan_query`), inval.c (registers callbacks), `snapmgr.c` (for `saved_xmin`/`TransactionXmin` comparison), lmgr.c (`AcquireExecutorLocks`/`AcquirePlannerLocks`).

## Open questions

- The plan_cache_mode GUC is read at `choose_custom_plan` time (so per-session override works); is it sampled atomically? [verified-by-code: it's a simple int read, no concurrency issues — but worth confirming `plan_cache_mode` storage class.]
- `CachedExpression`'s tracking of invalItems looks identical to plans but without a generic/custom split. Are there cases where a CachedExpression depends on a relation but not on any syscache row? [unverified — would need to inspect `GetCachedExpression`'s dependency-extraction]
- `RevalidateCachedQuery` can change tupdesc; the comment says "it's up to the caller to notice changes and cope". Which callers actually allow tupdesc change? [unverified — guarded by `fixed_result` field per CachedPlanSource]

## Confidence tag tally

verified-by-code: 11 — from-comment: 8 — from-readme: 0 — inferred: 0 — unverified: 3

## Synthesized by
<!-- backlinks:auto -->
- [subsystems/optimizer.md](../../../../../subsystems/optimizer.md)
- [subsystems/utils-cache.md](../../../../../subsystems/utils-cache.md)
- [subsystems/utils-mmgr.md](../../../../../subsystems/utils-mmgr.md)
- [idioms/cached-plan-invalidation.md](../../../../../idioms/cached-plan-invalidation.md)
- [idioms/generic-vs-custom-plan.md](../../../../../idioms/generic-vs-custom-plan.md)
- [idioms/plan-cache.md](../../../../../idioms/plan-cache.md)
- [idioms/prepared-statement-plancache.md](../../../../../idioms/prepared-statement-plancache.md)

