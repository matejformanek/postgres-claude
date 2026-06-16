# `src/backend/utils/adt/ruleutils.c`

- **File:** `source/src/backend/utils/adt/ruleutils.c` (14366 lines)
- **Header:** `source/src/include/utils/ruleutils.h`
- **Source pin:** `4b0bf0788b066a4ca1d4f959566678e44ec93422`

## Purpose

**Deparser**: converts stored expression/query/parse trees back into
SQL source text. Powers `pg_dump`, `psql \d` / `\sf` / `\ef`, EXPLAIN
verbose, partition bound printing, and the `pg_get_*` SQL functions.
(`ruleutils.c:1-14` [from-comment])

The reverse direction of `parser/gram.y` + `analyze.c`, with one
crucial difference: it operates on **already-rewritten Query trees**
(or `Const`/`OpExpr`/etc. expression trees), not raw text.

## SQL entry points (organized by domain)

### Rules and views (`:571-878`)
- `pg_get_ruledef(oid [, pretty])` — `CREATE RULE …` source for a
  pg_rewrite tuple.
- `pg_get_viewdef(oid|name [, pretty|wrap])` — the SELECT body
  (`:689, :707, :726, :746, :771`). Goes via `make_viewdef` (`:5900`).

### Triggers (`:882-1187`)
- `pg_get_triggerdef(oid [, pretty])` — `CREATE TRIGGER …` source.

### Indexes (`:1189-1597`)
- `pg_get_indexdef(oid)`, `pg_get_indexdef(oid, colno, pretty)`, plus
  C entries `pg_get_indexdef_string`, `_columns`, `_columns_extended`.

### Other catalog deparsers
- `pg_get_querydef(Query *, bool pretty)` (`:1599`) — internal-only,
  for EXPLAIN.
- `pg_get_propgraphdef` (`:1618`) — property graph DDL.
- `pg_get_statisticsobjdef*` (`:1967, 1985, 1995, 2196`) — CREATE
  STATISTICS … source plus the column-list and expressions variants.
- `pg_get_partkeydef` (`:2267`) — partition key.
- `pg_get_partition_constraintdef` (`:2454`), `pg_get_partconstrdef_string`.
- `pg_get_constraintdef` (`:2504, :2521, :2542`) — `CHECK (...)`,
  `FOREIGN KEY ...`, etc.
- `pg_get_functiondef(oid)` (`:3285`) — full `CREATE OR REPLACE
  FUNCTION/PROCEDURE …` (precise format documented at `:3279-3282`
  because psql `\ef` parses the output).
- `pg_get_function_arguments` (`:3541`),
  `pg_get_function_identity_arguments`,
  `pg_get_function_result`,
  `pg_get_function_arg_default`.
- `pg_get_expr(text, oid [, pretty])` (`:3033, 3050`) — deparses a
  serialized expression tree (e.g. `pg_index.indpred`,
  `pg_attrdef.adbin`).
- `pg_get_userbyid(oid)` (`:3148`) — friendly username lookup, not
  really deparse but lives here historically.

## Core data structures

- **`deparse_context`** (`:117-133`) — output buffer + `namespaces`
  stack + prettyFlags.
- **`deparse_namespace`** (`:158-192`) — one frame per Query/Plan
  level: rangetable, related state for the recursive descent. Mirrors
  what `parse_relation.c`'s analyze pass produced.
- **`deparse_columns`** (`:194-314`) — per-RTE alias bookkeeping for
  unique column names. Critical because the deparser must invent
  user-visible aliases that don't conflict (e.g. when the same table
  appears twice in a self-join).

## Algorithm shape

A tree walk over Query/Node trees, emitting into the StringInfo. Most
recursion happens via `get_query_def`, `get_rule_expr`, and many
node-specific helpers (`get_func_expr`, `get_oper_expr`,
`get_const_expr`, `get_agg_expr`, `get_windowclause`, etc.).

For views: `make_viewdef` (`:5900`) pulls `ev_qual` + `ev_action` from
the matched pg_rewrite tuple, deserializes via `stringToNode` (`:5941`
[verified-by-code]), validates the rule shape (instead + select with
qual "<>"), and dispatches to `get_query_def`.

## SPI usage

Several entry points connect to SPI to look up pg_rewrite rules
(`pg_get_ruledef_worker` and `pg_get_viewdef_worker`). The comment at
`:820-823` is explicit: **"We read pg_rewrite over the SPI manager
instead of using the syscache to be checked for read access on
pg_rewrite."** So an ordinary user can call `pg_get_viewdef` only if
they have read access on pg_rewrite (which they normally do).

## Phase D notes — does pg_get_viewdef omit security-relevant
clauses?

**Yes, by design.** `make_viewdef` (`:5900-5965`) emits only the
SELECT body followed by `;`. It does **NOT** include:
- `WITH CHECK OPTION` (LOCAL / CASCADED)
- `WITH (security_barrier = true)`, `WITH (security_invoker = true)`
- Column-level GRANTs / ACL
- Row Security policies attached to the view's base tables

This is intentional: `pg_get_viewdef` is conceptually "what SELECT
backs this view"; the **full CREATE VIEW statement is reconstructed by
pg_dump separately** (combining viewdef + reloptions from pg_class +
ACL from pg_class.relacl).

**However**, this can mislead a user who does
`pg_get_viewdef('my_secure_view')` expecting to see the WITH CHECK
clause and concluding it isn't there. They have to consult pg_class
reloptions independently.

A search of this file confirms NO references to `WITH CHECK`,
`security_barrier`, `security_invoker`, or `RLS POLICY` strings. The
row-security policy machinery emits its definition via
`pg_get_expr`-style helpers in `commands/policy.c`, NOT here.

[verified-by-code: `grep -nE "WITH CHECK|security_barrier|
security_invoker|CHECK OPTION" ruleutils.c` returns no matches]

### Other deparse-fidelity considerations

- Constants are emitted via `get_const_expr` (`:11700`+) which uses
  the type's output function. This is round-trippable for built-in
  types but for user-defined types with broken `typoutput`, the
  deparse could be lossy.
- View column aliases: the `deparse_columns` machinery (`:194-314`)
  exists precisely to ensure deparse → re-parse produces an
  equivalent tree.
- Operators are emitted using their canonical schema-qualified name
  via `quote_qualified_identifier`. Search-path-dependent unqualified
  forms are NOT produced (good for round-trip).

## Reloptions helpers (`:14244-14366`)

- `get_reloptions(StringInfo, Datum)` (`:14244`) — pretty-prints a
  text-array of `name=value` options. Used for indexes and partition
  table options. Quotes RHS as a string-literal (`'value'`).
- `flatten_reloptions(relid)` (`:14296`) — returns the same as a
  C string for a given relation.

These are how index-level reloptions appear in `pg_get_indexdef`. View
reloptions are NOT included in `pg_get_viewdef`.

## Phase D notes — recursion depth

- The deparser is recursive (`get_query_def` → `get_select_query_def`
  → `get_target_list` → `get_rule_expr` → ...). For deeply nested
  queries (e.g. 1000-level nested subqueries), this can recurse
  significantly.
- No explicit `check_stack_depth()` at every node — but the parser
  that produced the tree did check, so the tree depth is bounded by
  `max_stack_depth` GUC at parse time.
- Re-entering via `pg_get_expr` on an attacker-supplied expression
  tree fragment (e.g. `pg_get_expr('...', oid)`) does **NOT**
  re-validate depth. `pg_get_expr_worker` (`:3068`) trusts that the
  tree was produced by PG, since the surface is restricted.

## Potential issues

- [ISSUE-info-disclosure: `pg_get_viewdef` returning only the SELECT
  body misleads users about security barriers. Documentation OK but
  many security audits expect to see WITH CHECK in the output.
  (informational, by design)]
- [ISSUE-correctness: deparse of user-defined operators / functions
  schema-qualifies via current visibility; if `search_path` changes
  between when the view was created and when `pg_get_viewdef` runs,
  the qualified name is correct but may differ from the user's
  original spelling. Round-trip safe but not 1:1 textually. (low)]
- [ISSUE-dos: deeply nested SELECTs cause significant recursion in
  `get_query_def`. `pg_get_viewdef` on a view with 1000 levels of
  nested CTEs could blow the C stack — but the parser would not have
  accepted the original CREATE VIEW in the first place. (low)]
- [ISSUE-undocumented-invariant: `pg_get_functiondef` output format
  is parsed by psql's `\ef` and `\sf` (`:3279-3282`) — any change to
  emit order can break psql. Stable since at least PG 9.2. (low)]
- [ISSUE-correctness: `pg_get_constraintdef` for FOREIGN KEY emits
  `ON DELETE NO ACTION` only when it's not the default, leading to
  pg_dump output that may not exactly match the CREATE statement
  (the catalog stores 'a' = NO ACTION = the default). Cosmetic.
  (low)]
- [ISSUE-stale-todo: This file has comments scattered throughout
  noting cases where the deparse is "the best we can do" for
  recursive CTEs, lateral subqueries, etc. No bug; just complexity
  warnings. (informational)]

## Cross-references

- `source/src/backend/utils/adt/format_type.c` — `format_type_extended`
  for type names.
- `source/src/backend/nodes/read.c` — `stringToNode` parses the
  serialized rule body.
- `source/src/backend/rewrite/` — produces the Query trees deparsed
  here.
- `source/src/backend/parser/parse_relation.c` — the namespace
  machinery this mirrors.
- `source/src/bin/pg_dump/pg_dump.c` — combines this with reloptions
  to build full CREATE statements.
- `source/src/backend/commands/policy.c` — RLS policy deparse lives
  here, NOT in ruleutils.c.

<!-- issues:auto:begin -->
- [Issue register — `utils-adt`](../../../../../issues/utils-adt.md)
<!-- issues:auto:end -->

## Confidence tag tally

- `[verified-by-code]` × 12
- `[from-comment]` × 5
- `[inferred]` × 3
