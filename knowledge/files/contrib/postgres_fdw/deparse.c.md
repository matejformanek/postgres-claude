# deparse.c

## One-line summary

The "what we ship to the remote" surface of postgres_fdw: a pushdown-classifier (`foreign_expr_walker` → `is_foreign_expr`) that decides which expressions are safe to evaluate remotely, plus the SQL generators that turn local Plan trees back into remote-side SELECT / INSERT / UPDATE / DELETE / TRUNCATE / ANALYZE text — every identifier goes through `quote_identifier`, every literal through `deparseStringLiteral`, every non-built-in type/function/operator is schema-qualified with `FORMAT_TYPE_FORCE_QUALIFY` against the remote-side `search_path=pg_catalog`.

## Public API / entry points

Pushdown gating (the WALKER):
- `void classifyConditions(root, baserel, input_conds, remote_conds, local_conds)` (line 217) — partitions a RestrictInfo list by remote-safety.
- `bool is_foreign_expr(root, baserel, expr)` (line 243) — top-level "is this whole expr remote-safe?". Layers three checks: structural (`foreign_expr_walker`), collation (FDW_COLLATE_UNSAFE), mutability (`contain_mutable_functions`).
- `bool is_foreign_param(root, baserel, expr)` (declared in header; implementation below) — is an expression a remote-side Param?
- `bool is_foreign_pathkey(root, baserel, pathkey)` — can sort by this pathkey on remote?

SQL emitters:
- `deparseSelectStmtForRel` (line 1266) — top-level SELECT builder (used for scan, join, upper).
- `deparseInsertSql` (line 2114), `rebuildInsertSql` (line 2187) — INSERT (+ batch rebuild).
- `deparseUpdateSql` (line 2247) (ctid-based one-row), `deparseDirectUpdateSql` (line 2307) (where-pushdown).
- `deparseDeleteSql` (line 2393), `deparseDirectDeleteSql` (line 2422).
- `deparseAnalyzeSql` (line 2592), `deparseAnalyzeSizeSql` (line 2530), `deparseAnalyzeInfoSql` (line 2552).
- `deparseTruncateSql` (line 2677).
- `deparseStringLiteral(buf, val)` (line 2880) — escape-quote a string literal for the remote (handles `E'...'` when backslashes present).

Helpers:
- `build_tlist_to_deparse(foreignrel)` (line 1208).
- `find_em_for_rel(root, ec, rel)` / `find_em_for_rel_target(root, ec, rel)` — in postgres_fdw.c actually; mentioned in header.
- `get_jointype_name(jointype)`.
- `deparse_type_name(type_oid, typemod)` (line 1190) — wraps `format_type_extended` with `FORMAT_TYPE_FORCE_QUALIFY` for non-builtins.

## Key invariants

- INV-SEARCH-PATH-CATALOG: deparse ASSUMES the remote session has `search_path=pg_catalog`. `configure_remote_session` (`connection.c:816`) enforces this. **If a malicious view definition on the remote does `set_config('search_path', ...)`, deparse output ceases to be unambiguous.** [from-comment lines 14-16]
- INV-COLLATE-CONSERVATIVE: COLLATE expressions are NEVER shipped (lines 17-25 comment). An expression is collation-safe only if all input collations are traceable to Vars of the foreign table itself. `FDW_COLLATE_UNSAFE` short-circuits `is_foreign_expr` (line 277). The reasoning: the remote might disagree about collation names. [from-comment + verified-by-code]
- INV-MUTABLE-NEVER-SHIPS: `contain_mutable_functions((Node *) expr)` short-circuits `is_foreign_expr` (line 287). Volatile or stable functions stay local. Reasoning: `now()`, `random()` would give different answers across clock skew. [verified-by-code]
- INV-SHIPPABLE-RESULT-TYPE: every walked node has its `exprType` rechecked via `is_shippable(..., TypeRelationId, ...)` (line 1050). Even if the function/operator is shippable, the RESULT TYPE must also be remote-known.
- INV-SYSCOLS-NO-SHIP: in the `T_Var` branch (lines 358-360), system columns OTHER THAN ctid are refused — `tableoid`, `xmin` etc. would not match the remote's idea of the row. ctid is special because postgres_fdw uses it as the row identity for UPDATE/DELETE.
- INV-MULTIEXPR-PARAM-NO-SHIP: PARAM_MULTIEXPR params bail early (line 499) — they reference sublinks that may contain remote Vars; too hard to handle today.
- INV-AGGREF-UPPER-ONLY: an Aggref node is only pushdown-candidate when `IS_UPPER_REL(glob_cxt->foreignrel)` is true (lines 943-945). Outside an upper-rel context, no agg pushdown.
- INV-AGGSPLIT-SIMPLE-ONLY: only `agg->aggsplit == AGGSPLIT_SIMPLE` is pushdown-candidate (line 948). Partial aggregates (for parallel query at remote) are NOT pushed down.
- INV-IDENTIFIERS-QUOTED: every identifier emitted goes through `quote_identifier` — column name (`deparseColumnRef` line 2830, line 2632), relation name (`deparseRelation` line 2873), function/operator name (`appendFunctionName` and `deparseOperatorName`).
- INV-LITERALS-DOUBLE-ESCAPED: `deparseStringLiteral` (line 2880) doubles every `'` (`SQL_STR_DOUBLE`) and emits `E'...'` prefix when backslashes are present, so the remote's `standard_conforming_strings` setting is irrelevant.

## Notable internals

### The pushdown decision tree (`foreign_expr_walker`, lines 311-1101)

Switch on `nodeTag(node)`:

- **T_Var**: foreign Var → ok, save collation. Non-foreign Var → ok iff collation is invalid or default, else `FDW_COLLATE_UNSAFE`. System cols other than ctid → false.
- **T_Const**: typed-OID constants (REGPROC, REGOPER, REGCLASS, REGTYPE, REGCOLLATION, REGCONFIG, REGDICTIONARY, REGNAMESPACE, REGROLE, REGDATABASE) get a per-class `is_shippable` check (lines 401-465). REGCONFIG/REGDICTIONARY get a weaker cutoff (`FirstNormalObjectId`, line 439) — so initdb-installed TS configs are shippable. Other consts → ok modulo collation.
- **T_Param**: PARAM_MULTIEXPR → false; otherwise collation rules same as Var.
- **T_SubscriptingRef**: refassgnexpr→false (no array-element assignment). Walks upper/lower/refexpr. Container result collation handled.
- **T_FuncExpr**: `is_shippable(funcid, ProcedureRelationId)` else false; walks args; ensures `inputcollid` derives from foreign Var if non-invalid.
- **T_OpExpr / T_DistinctExpr**: `is_shippable(opno, OperatorRelationId)`; walks args; same input-collation rule.
- **T_ScalarArrayOpExpr**: ditto operator; output always bool/noncollatable.
- **T_RelabelType, T_ArrayCoerceExpr**: walk arg; resultcollid rule.
- **T_BoolExpr, T_NullTest**: walk subexprs; bool output.
- **T_CaseExpr**: walk arg, then each CaseWhen (special handling — CASE-with-arg must have `OpExpr` WHEN clauses with CaseTestExpr on left, else bail; comment lines 793-816 explains this is to handle expressions that survive the optimizer's expansion).
- **T_CaseTestExpr**: only valid inside CASE arg context (line 865).
- **T_ArrayExpr**: walk elements; array_collid rule.
- **T_List**: bubble collation from elements.
- **T_Aggref**: only in UPPER_REL context; AGGSPLIT_SIMPLE only; `is_shippable(aggfnoid)`; walk args; walk aggorder (check sortop shippability); walk aggfilter; collation rule.
- **default**: unsafe.

After the switch, two post-checks: (a) result type must be shippable (line 1050), (b) merge collation state into parent (lines 1056-1096) — non-default collation always beats default, conflicting non-default → UNSAFE.

### Identifier emission

- `deparseRelation` (line 2840): respects `schema_name` / `table_name` foreign-table options for remote name (lines 2853-2861). If options not present, uses local namespace name and relname. Both go through `quote_identifier`.
- `deparseColumnRef` (line 2712):
  - `ctid` → emits `ctid` (qualified with rel alias if join).
  - Other system cols → CASE WHEN (rel.*)::text IS NOT NULL THEN <tableoid-or-0> END (lines 2735-2742) — outer-join NULL-safety.
  - varattno==0 (whole-row) → ROW(col1, col2, ...) since local table's whole-row composite may not exist on remote (lines 2767-2786). Outer-join wrapped in CASE WHEN.
  - Normal → respects `column_name` foreign-column option, else local attname; `quote_identifier`.
- `deparseAnalyzeSql` (line 2632) — same `column_name` rule applied for ANALYZE column list.

### `deparseConst` (line 3053) — literal emission

- NULL → `NULL::<type>` (showtype controls suppression).
- INT2/4/8, OID, FLOAT4/8, NUMERIC: numeric extval, parenthesized if signed, emitted unquoted UNLESS contains non-`0-9+-eE.` chars (NaN/Infinity) in which case `'NaN'::numeric` form.
- BIT/VARBIT → `B'...'`.
- BOOL → `true`/`false`.
- Otherwise → `deparseStringLiteral(extval)` + optional `::typename`.

### `set_transmission_modes` (defined in postgres_fdw.c:4108, called at deparse.c:1610 and :2339)

Before emitting a Const or a direct-modify SET clause, `set_transmission_modes()` pushes a GUC nestlevel forcing `datestyle=ISO`, `intervalstyle=postgres`, `extra_float_digits=3`, `search_path=pg_catalog`. The Const's `OidOutputFunctionCall` then runs under these settings. `reset_transmission_modes(nestlevel)` undoes via `AtEOXact_GUC(true, nestlevel)`. Comment at lines 4097-4106 acknowledges this is expensive but necessary.

### `deparseLockingClause` (line 1512)

Emits `FOR UPDATE` if the relation is the UPDATE/DELETE target (line 1545), or `FOR UPDATE`/`FOR SHARE` if the local query has a corresponding RowMarkClause (lines 1554-1579). DECLARE CURSOR + FOR UPDATE is NOT supported by the remote, so this can fail on the remote side — comment at 1530-1540 notes the limitation.

### Join / upper-rel SELECT generation

`deparseSelectStmtForRel` (line 1266) drives the whole shape:
- SELECT-clause via `deparseSelectSql` → `deparseSubqueryTargetList` / `deparseExplicitTargetList` / `deparseTargetList`.
- FROM via `deparseFromExprForRel` (line 1792) — recursively emits relation, alias, JOIN syntax.
- WHERE via `appendWhereClause`.
- GROUP BY / HAVING for upper-rels.
- ORDER BY via `appendOrderByClause`.
- LIMIT via `appendLimitClause`.
- FOR UPDATE / SHARE via `deparseLockingClause`.

### `deparseTruncateSql` (line 2677)

Emits `TRUNCATE rel1, rel2, ... RESTART|CONTINUE IDENTITY [RESTRICT|CASCADE]`. The `restart_seqs` flag and the `behavior` enum come straight from local TRUNCATE.

### `deparseAnalyzeSql` (line 2592)

Emits `SELECT col1, col2 FROM remote_rel [WHERE pg_catalog.random() < <frac>]` or `... TABLESAMPLE SYSTEM(<pct>)` / `BERNOULLI(<pct>)`. The fraction `sample_frac` is computed from local `targrows` / remote `reltuples`.

## Trust boundary / Phase D surface

### SQL-injection surface

Identifiers: every emit goes through `quote_identifier` (lines 2632, 2830, 2873). `quote_identifier` is the canonical PG-side quoter — handles embedded `"` correctly. **A `column_name` FDW option value of `foo"; DROP TABLE bar; --` would be quoted as `"foo""; DROP TABLE bar; --"` and the remote would look up a literal column with that exact name (returning "column not found"), not execute the injection.**

Literals: `deparseStringLiteral` doubles `'` via `SQL_STR_DOUBLE` and emits `E'...'` when backslashes are present. **Type-cast text** (`deparse_type_name` output) is NOT subject to `quote_identifier` — it's interpolated as a `::typename` suffix. But `format_type_extended` ITSELF emits a quote_identifier'd schema-qualified name. So a type with name `int4"; DROP TABLE ...` would still be quoted. Verified by `format_type` behavior, but worth a regression test.

### `column_name` / `schema_name` / `table_name` foreign options as injection vectors

These come from `CREATE FOREIGN TABLE ... OPTIONS (column_name '...')`. The validator (`option.c`) only checks the option NAME, not VALUE. So the value is whatever the local DBA put there. Trust here = trust the local DBA who created the foreign table — usually superuser. Not a privilege-escalation surface in the standard threat model. But: **a non-superuser who is granted ability to create foreign tables on a server (via FDW USAGE)** can put any string in `column_name`. Quoted at emit time → safe.

### `deparse_type_name` and `FORMAT_TYPE_FORCE_QUALIFY`

Non-built-in types (`is_builtin` returns false, i.e. OID ≥ `FirstGenbkiObjectId`) are emitted with `FORMAT_TYPE_FORCE_QUALIFY` (line 1195) — `pg_catalog.foo` or `myschema.bar`. Built-in types skip qualification (assumes remote knows them under same names). **A built-in type renamed on the remote** (impossible without superuser + catalog corruption) would mismatch. Not a real attack.

### CASE-WHEN restriction (lines 793-816)

The comment explains a subtle pre-deparser optimization-stage issue: `CASE col WHEN val THEN ...` is parsed as `CASE col WHEN (CaseTestExpr = val) THEN ...`. The optimizer can expand the `=` operator inline, producing arbitrary expressions for the WHEN clause. If so, `deparseCaseExpr` cannot emit valid SQL — bail. This is correctness, not security, but it's the kind of test-coverage gap that has historically hidden SQL-deparse bugs.

### Aggregate pushdown safety: function-by-name resolution at remote

`appendFunctionName` (used in `deparseFuncExpr` and `deparseAggref`) emits the aggregate's name (schema-qualified for non-builtins). The REMOTE then resolves by name. **If the remote has a same-named aggregate with different finalfn, transitionfn, or `volatility`**, the result silently differs. `is_shippable` only checked LOCAL volatility. **No version compatibility check across cluster.** Documented Phase D issue.

### JOIN pushdown collation safety

`is_foreign_expr` checks that all inputs in a JOIN clause's expr have collations traceable to foreign Vars (FDW_COLLATE_SAFE rule). Implicitly assumes the foreign Var's `varcollid` is the SAME as the remote column's collation. If the foreign table was declared with `COLLATE "en_US"` but the remote column is `"de_DE"`, **the JOIN result silently uses the remote's collation, not the local declared one**. Local conds re-applied after fetch may filter out rows the remote would have included (or vice-versa). Not a security issue, but a silent correctness pitfall.

### EXPLAIN VERBOSE remote-SQL leakage

`postgresExplainForeignScan` / `Modify` / `DirectModify` emit the deparsed SQL string to the EXPLAIN output. The SQL contains:
- Schema-qualified relation names — leaks remote topology.
- Column names with `column_name` option applied — leaks remote schema mapping.
- Literal Const values from local WHERE clause that were pushed down (`deparseConst` → `deparseStringLiteral` → echoed) — **echoes user query literals into EXPLAIN**. If a non-superuser ran an EXPLAIN VERBOSE on someone else's foreign table after a `prepare ... using (sensitive_value)` ... actually no, EXPLAIN shows the plan generated for the current invocation. Mostly cosmetic, but: **EXPLAIN VERBOSE on a query touching a foreign table can be saved/logged and contains query literals**. Standard behavior.
- Does NOT contain conninfo, password, or remote auth.

### `pg_catalog.random()` in TABLESAMPLE-via-ANALYZE

`deparseAnalyzeSql` emits `pg_catalog.random()` (line 2655) for ANALYZE_SAMPLE_RANDOM. The remote's random() output is not seeded by local; subsequent ANALYZE runs sample different rows. Not a security issue.

### `whole-row reference` deparses as `ROW(col1, col2, ...)`

Lines 2783-2785. This is mandatory because the foreign table's local composite type name doesn't exist on the remote. **A query that does `SELECT row_to_json(ft.*) FROM ft` is rewritten to ship `SELECT ROW(c1, c2, ...) AS wholerow FROM remote_t`** — the order is determined by the local foreign-table column order. If remote has extra columns, they're not fetched. If remote has reordered columns, local re-assembly aligns to local order.

## Cross-references

- `source/contrib/postgres_fdw/postgres_fdw.c:4108` — `set_transmission_modes` / `reset_transmission_modes`.
- `source/contrib/postgres_fdw/shippable.c` — `is_builtin`, `is_shippable`.
- `source/contrib/postgres_fdw/connection.c:811` — `configure_remote_session` (the SEARCH_PATH guarantee).
- `source/src/backend/utils/adt/format_type.c` — `format_type_extended` and `FORMAT_TYPE_FORCE_QUALIFY`.
- `source/src/backend/utils/adt/ruleutils.c` — the OTHER deparser (rewrite-rule / function-body / view dumps); comment at line 9 admits this file is "annoyingly duplicative".
- `source/src/backend/optimizer/util/clauses.c` — `contain_mutable_functions`.

<!-- issues:auto:begin -->
- [Issue register — `postgres_fdw`](../../../issues/postgres_fdw.md)
<!-- issues:auto:end -->

## Issues spotted

- [ISSUE-correctness: `T_CaseExpr` pushdown bails when the WHEN clause isn't a plain `OpExpr` w/ CaseTestExpr on left (lines 805-815). After certain optimizer passes (constant folding of the equality operator), legitimate CASE expressions silently stop being pushable, possibly causing performance regression after an unrelated optimizer change. (likely)] — `source/contrib/postgres_fdw/deparse.c:793-816`.
- [ISSUE-correctness: shippable result-type check (line 1050) uses `exprType(node)`. For a SubLink/SubQuery node that was somehow walked, `exprType` may be RECORDOID — `is_shippable(RECORDOID, ...)` returns true because RECORDOID < FirstGenbkiObjectId. A whole RECORD pushdown would currently never reach here because the top-level switch rejects unknown node types, but it's a fragile rule. (nit)] — `source/contrib/postgres_fdw/deparse.c:1050`.
- [ISSUE-security: cross-cluster aggregate-pushdown semantics mismatch. `is_shippable(aggfnoid, ProcedureRelationId)` checks local OID against local shippable-extension list. If a shippable extension declares `myext.weighted_mean(numeric)` and the remote has a same-named-but-different-semantics aggregate, results differ silently. **No mitigation in code, no warning at planning.** (likely — Phase D class)] — `source/contrib/postgres_fdw/deparse.c:952`.
- [ISSUE-correctness: JOIN-clause collation pushdown assumes foreign Var `varcollid` equals remote column collation. No catalog-level verification. A `CREATE FOREIGN TABLE ... col text COLLATE "en_US"` on a remote column with `COLLATE "de_DE"` gives silently-wrong sort/equality results when JOIN pushed down. (likely)] — `source/contrib/postgres_fdw/deparse.c:347-388`.
- [ISSUE-correctness: T_Aggref pushdown only fires inside UPPER_REL context (line 944). Aggregate inside a JOIN's HAVING-equivalent on the REMOTE side (e.g. a remote view containing an aggregate referenced via WHERE filter) doesn't go through this path — it's the remote's job. But if the local optimizer pushed an Aggref into a join-rel during some future change, this check would silently downgrade to local execution. (nit)] — `source/contrib/postgres_fdw/deparse.c:943`.
- [ISSUE-defense-in-depth: `deparse_type_name` qualifies non-builtins with their LOCAL schema name (line 1195). If local has `myschema.mytype` and remote has `myschema.mytype` with different internal length / typoutput / typinput, the emit looks right but semantics differ. No verification. (likely)] — `source/contrib/postgres_fdw/deparse.c:1190-1198`.
- [ISSUE-correctness: `deparseLockingClause` emits `FOR UPDATE` / `FOR SHARE` for a remote DECLARE CURSOR (since `deparseSelectStmtForRel` is wrapped in `DECLARE c%u CURSOR FOR ...` at `postgres_fdw.c:3976`). Comment at lines 1530-1540 warns DECLARE CURSOR ... FOR UPDATE is unsupported by old remote servers. Modern PG supports it but with caveats; outer-join behavior at remote may differ. (documented limitation)] — `source/contrib/postgres_fdw/deparse.c:1530-1540`.
- [ISSUE-correctness: `deparseTruncateSql` emits `TRUNCATE` with `behavior`. **The `truncatable=false` FOREIGN TABLE option is checked in `postgres_fdw.c:3252-3269` — but only at TRUNCATE statement, not at the remote-cascade path.** If a remote TRUNCATE CASCADE drops dependent foreign-table-related rows on the remote, the local `truncatable=false` is bypassed. (likely — Phase D class)] — `source/contrib/postgres_fdw/deparse.c:2677`, `source/contrib/postgres_fdw/postgres_fdw.c:3265`.
- [ISSUE-correctness: `deparseConst` line 3092 uses `strspn(extval, "0123456789+-eE.")` to decide if a numeric is bare-emittable. A locale-specific numeric output (none today by default, but `lc_numeric` aware functions could produce comma decimals) would mis-trigger the quoted path. PG numeric output is locale-insensitive in pg_catalog mode (set_transmission_modes forces this). (nit)] — `source/contrib/postgres_fdw/deparse.c:3092`.
- [ISSUE-correctness: `deparseStringLiteral` uses `SQL_STR_DOUBLE(ch, true)` — the `true` is `escape_backslash`. The function emits `E'...'` prefix when any backslash present (line 2890). Comment at lines 2884-2889 says "always use E'foo' syntax if there are any backslashes". This makes the literal `standard_conforming_strings`-agnostic. Verified-correct. (resolved)] — `source/contrib/postgres_fdw/deparse.c:2880-2901`.
- [ISSUE-correctness: PARAM_MULTIEXPR bailout (line 499) is correct but tied to a specific optimizer-stage detail (PARAM_MULTIEXPR not reduced to PARAM_EXEC until end-of-planning). A change in planning-stage ordering could break this defensively-defended invariant. (nit — defensive)] — `source/contrib/postgres_fdw/deparse.c:486-500`.
- [ISSUE-audit-gap: no hook for "deparsed SQL" — extensions wishing to LOG every cross-cluster SQL sent for compliance have to monkey-patch. `pgaudit`-style logging would benefit from a `Deparse_hook`. (likely — defense-in-depth)] — entire file.
- [ISSUE-documentation: line 1051 says "exprType(node) shippable" but exprType for List nodes returns InvalidOid, and is_shippable(InvalidOid, ...) returns... let's see: `is_builtin(InvalidOid)` → `0 < FirstGenbkiObjectId` → true → shippable. The `check_type = false` for T_List (line 935) prevents this path. Fragile coupling. (nit)] — `source/contrib/postgres_fdw/deparse.c:935,1050`.
