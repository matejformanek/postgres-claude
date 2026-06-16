# ri_triggers.c — Referential-integrity trigger functions

## Purpose

Implements the C-level trigger functions that enforce SQL FOREIGN KEY constraints: `RI_FKey_check_ins`, `RI_FKey_check_upd`, `RI_FKey_noaction_del`, `RI_FKey_restrict_del`, `RI_FKey_cascade_del`, `RI_FKey_setnull_del`, `RI_FKey_setdefault_del`, and the matching `_upd` variants — plus the cached query-plan machinery (per-(fk,pk,action) SPI plans) and constraint-info hashtable.

Source: `source/src/backend/utils/adt/ri_triggers.c` (4313 lines). One of the most security-sensitive files in the backend: builds SQL fragments from catalog data on the hot path.

## SQL fragment building — quoting discipline

**Yes, ri_triggers uses proper identifier quoting**. Two helpers do the work:

- `quoteOneName(buffer, name)` at line 2162 — emits a double-quoted name with internal `"` doubled. Standard SQL identifier-quoting algorithm. [verified-by-code]
- `quoteRelationName(buffer, rel)` at line 2181 — schema + `.` + name, both quoted via `quoteOneName`. Uses `get_namespace_name(RelationGetNamespace(rel))` for the schema. [verified-by-code]

`quoteOneName`'s body:
```c
*buffer++ = '"';
while (*name) {
    if (*name == '"') *buffer++ = '"';   // double up embedded quotes
    *buffer++ = *name++;
}
*buffer++ = '"';
```

Every catalog-name → SQL-fragment path uses these. Examples:
- ri_triggers.c:526-547 (RI_FKey_check_ins constructs SELECT...FROM "schema"."pktable" WHERE "schema"."pktable"."col1" = $1 ...).
- ri_triggers.c:697-737 (NOT EXISTS variant).
- ri_triggers.c:913-1014 (range FK with `pg_catalog.range_agg`).
- ri_triggers.c:1098, 1209, 1425 (cascade DELETE/UPDATE).

**Values are NOT concatenated into the SQL string.** They flow as SPI parameters via `SPI_execute_plan(qplan, vals, nulls, ...)`. The plan is built with placeholders `$1, $2, ...` and the parameters are typed Datums (no string conversion).

## Cached SPI plans

`ri_FetchPreparedPlan` (line 294) / `ri_HashPreparedPlan` (295) keep a per-(constraint, action) cache of `SPIPlanPtr` keyed by `RI_QueryKey`. The first hit builds the SQL text and `SPI_prepare`s it; subsequent calls reuse the plan with new parameters.

`ri_PlanCheck` (304) prepares a single SPI plan with argtypes; `ri_PerformCheck` (306) binds parameters and executes.

## Key entry points

- `RI_FKey_check_ins` — INSERT on FK table → SELECT 1 FROM pktable WHERE pkcol = $1 FOR KEY SHARE.
- `RI_FKey_check_upd` — UPDATE on FK table when the FK columns changed.
- `RI_FKey_noaction_del`, `RI_FKey_restrict_del` — verify no FK rows reference the deleted PK row; ereport ERROR if any.
- `RI_FKey_cascade_del` — DELETE matching FK rows.
- `RI_FKey_setnull_del`, `RI_FKey_setdefault_del` — UPDATE FK to NULL or default.
- `RI_FKey_*_upd` — corresponding ON UPDATE actions.

Plus `ri_LoadConstraintInfo` (302) — loads `RI_ConstraintInfo` from `pg_constraint`, with cache invalidation via `InvalidateConstraintCacheCallBack` (292).

## Phase D notes

- **No string concatenation of values into SQL** — values are always SPI parameters. [verified-by-code]
- **All identifiers are quoted via `quoteOneName`** — there's no `appendStringInfo(buf, "%s", colname)` for catalog names anywhere in the SQL-building paths I checked. [verified-by-code spot-checks at 526-1014]
- **Constraint info is cache-invalidated** via syscache callback on `CONSTROID`. Cache poisoning via concurrent constraint changes is handled.
- **Collation included via `ri_GenerateQualCollation`** — comparisons use the FK column's collation so locale-specific FKs work. [verified-by-code:280]
- **`FOR KEY SHARE OF x`** added to lookup queries so a concurrent UPDATE/DELETE on the PK row waits for the trigger to finish. This is the core SSI-correctness mechanism for FKs. [verified-by-code:557, 726, 1014]

## Potential issues

- `[ISSUE-injection: identifier quoting in quoteOneName looks correct (standard double-up algorithm); however if a future ALTER TABLE allowed control characters in column names, the SQL parser may still tokenize oddly. Today PG forbids NUL in names so safe (low)]`.
- `[ISSUE-trust-boundary: ri_triggers builds SQL using catalog names of tables/cols that the FK creator may not own; the SPI plan runs as the FK-owner's effective userid (or system) but reads PK rows even when the current user lacks SELECT on the PK. The standard says FK semantics require this; documented in the user docs (low)]`.
- `[ISSUE-dos: cached SPI plans are keyed by constraint OID + action; a workload that creates and drops constraints in tight loops grows the cache. Cache invalidation via callback should reap, but worth a memory-context check (low)]`.
- `[ISSUE-undocumented-invariant: range-FK code at 913-1014 uses `pg_catalog.range_agg`; if range_agg is hidden via search_path manipulation, the fully-qualified `pg_catalog.` prefix defends. Verified the qualification at line 981 (low; well-handled)]`.
- `[ISSUE-correctness: ri_CompareWithCast at 288 — applies a cast operator to compare FK and PK values when types differ (e.g. int4 FK referencing int8 PK). A buggy cast for a user type could silently break FK enforcement (maybe — would need targeted audit)]`.

Confidence: SQL-building paths `[verified-by-code]` via spot-check; quoteOneName implementation `[verified-by-code]`.

## Cross-references

<!-- issues:auto:begin -->
- [Issue register — `utils-adt`](../../../../../issues/utils-adt.md)
<!-- issues:auto:end -->
