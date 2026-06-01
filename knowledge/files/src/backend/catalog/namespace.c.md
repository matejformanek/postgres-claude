# namespace.c

- **Source path:** `source/src/backend/catalog/namespace.c`
- **Lines:** ~4 700
- **Last verified commit:** `ef6a95c7c64`
- **Companion files:** `catalog/namespace.h`, `catalog/pg_namespace.c` (the pg_namespace row I/O), `parser/parse_relation.c`.

## Purpose

"code to support accessing and searching namespaces." Separate from `pg_namespace.c`. Provides the **search_path** machinery: resolve unqualified names → schema-qualified OIDs, manage the temp namespace lifecycle, and offer "is X visible under current path" predicates used by `\d` and by ruleutils' deparser. [from-comment, namespace.c:3-9]

## Mental model

- **Active search path:** `activeSearchPath` is a List<Oid> of namespaces searched in order. It is *derived* from `baseSearchPath`, which is computed from the `search_path` GUC string and the current `userid`. Recomputation triggers: GUC change, syscache invalidation on pg_namespace or pg_authid, or role change. The recomputed list filters out namespaces the current user can't `USAGE`. [verified-by-code, namespace.c:65-145]
- **Implicit pg_catalog:** if not in the explicit path, pg_catalog is implicitly searched *first* (after temp). This is required by SQL99. [from-comment, namespace.c:73-79]
- **Implicit pg_temp:** the session's temp namespace is searched first if it exists and is not explicit. For non-relation/non-type objects the temp namespace is *security-skipped* even if listed. [from-comment, namespace.c:81-83]
- **activePathGeneration counter** (namespace.c:144) — incremented on every effective-path change, used by relcache to invalidate cached path-dependent state quickly.
- **Search-path cache** (namespace.c:160-185) — `simplehash` of (search_path string, role) → resolved OID list. Materially cuts cost of `SET LOCAL search_path` in functions that fire often.

## Public surface

- `RangeVarGetRelidExtended` (442) — **the principal name-resolution entry.** Takes a RangeVar, a lockmode, flags (RVR_MISSING_OK, RVR_NOWAIT, RVR_SKIP_LOCKED), and an optional callback. The famous **re-check-after-lock loop** lives here: look up OID by name, take heavyweight lock (which AcceptsInvalidationMessages), then re-look-up; if the answer changed, drop the old lock and retry. This is what makes name lookup correct under concurrent DDL. [verified-by-code, namespace.c:442-643]
- `RangeVarGetCreationNamespace` (655) — for CREATE: pick the namespace to create into (first explicit element, or temp).
- `RangeVarGetAndCheckCreationNamespace` (740) — same plus ACL `USAGE`/`CREATE` checks.
- `RangeVarAdjustRelationPersistence` (847) — TEMP-table grammar quirk handler.
- `RelnameGetRelid` (886), `RelationIsVisible` (914) — by-name search and "would this OID be found unqualified" predicate.
- `TypenameGetTypid` (996), `TypeIsVisible` (1041); `FuncnameGetCandidates` (1199), `FunctionIsVisible` (1743); `OpernameGetOprid` (1834), `OpernameGetCandidates` (1947), `OperatorIsVisible` (2118); `OpclassnameGetOpcid` (2190) — the parallel set for type/function/operator/opclass lookups. `FuncnameGetCandidates` is the bulk of function/operator overload resolution.
- `MatchNamedCall` (1618) — supports named-argument calls (`func(a := 1)`).
- `LookupExplicitNamespace`, `LookupNamespaceNoError`, `get_namespace_oid` — explicit "by name" resolvers.
- `GetTempNamespaceProcNumber`, `GetTempNamespaceBackendId`, `isTempNamespace`, `isTempToastNamespace`, `isAnyTempNamespace` — temp namespace predicates used by relcache, vacuum.
- `InitTempTableNamespace` (down-file) — lazy creation of `pg_temp_NNN` schema and matching `pg_toast_temp_NNN`; runs at first temp object creation in a session.
- `RemoveTempRelations` / `RemoveTempRelationsCallback` — backend-exit cleanup of all temp objects via `performDeletion` over the temp namespace.
- `check_search_path` / `assign_search_path` (GUC hooks at end of file) — validate and stage path changes; actual recomputation is deferred to `recomputeNamespacePath`.
- `InvalidationCallback` (registered with syscache) — sets `baseSearchPathValid = false` and clears the path cache when pg_namespace or pg_authid changes.

## Search-path resolution algorithm (load-bearing)

When `RelnameGetRelid("foo")` is called (or any other `*IsVisible` walk):

1. `recomputeNamespacePath()` runs if `baseSearchPathValid == false`. It parses `namespace_search_path`, expands `$user`, expands `pg_temp` to the actual temp namespace OID, filters out un-readable namespaces, and writes `baseSearchPath` + `baseCreationNamespace`.
2. Then `activeSearchPath` is set from `baseSearchPath`, prepending implicit pg_temp / pg_catalog as needed.
3. For each namespace OID in order, the search probes the per-object syscache (RELNAMENSP / TYPENAMENSP / PROCNAMEARGSNSP / OPERNAMENSP …). The first hit wins.
4. `*IsVisible` predicates exit early if the first-found OID for the unqualified name *equals* the object's OID — i.e., "would this object be picked if you used its unqualified name". This drives ruleutils' decisions about whether to schema-qualify.

## Confidence tag tally

`[verified-by-code]=6 [from-comment]=3`
