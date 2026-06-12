# pg_graphql — a GraphQL server that is one SQL function over catalog reflection

> Ideology note produced by the `pg-extension-anthropologist` cloud routine.
> Repo: `supabase/pg_graphql` @ branch `master`. All `file:line` cites below
> point into that repo (not `source/`), since this doc characterizes an
> *external* extension's divergence from core idioms. pg_graphql is Rust on
> **pgrx**, so cites land in `.rs` files. Cites verified against the files
> fetched on 2026-06-11 (see Sources footer). The bulk of `transpile.rs`
> (2062 lines of per-node SQL emission) and `sql_types.rs` (1055 lines of
> reflection passes) were sampled at the load-bearing functions, not read
> end-to-end.

## Domain & purpose

pg_graphql "adds GraphQL support to your PostgreSQL database [by reflecting] a
GraphQL schema from the existing SQL schema" (`README.md:18, 26`)
`[from-README]`. The defining claim is architectural: "The extension keeps schema
translation and query resolution neatly contained on your database server. This
enables any programming language that can connect to PostgreSQL to query the
database via GraphQL with no additional servers, processes, or libraries"
(`README.md:28`) `[from-README]`. Every table gets a top-level `Query`
collection entrypoint with foreign-key relationships, and `Mutation` entrypoints
for insert/update/delete (`README.md:71`). Where most GraphQL stacks are a
separate Node/Go service that issues many SQL queries per request, pg_graphql is
**a single SQL function**: you hand it a GraphQL string and it returns the JSON
response, having introspected the catalog and run exactly one transpiled SQL
statement. It is the corpus's purest "embed a whole foreign query language as a
stored function over catalog reflection" case — adjacent to
`[[knowledge/ideologies/apache-age]]` (Cypher) and `[[knowledge/ideologies/pg_duckdb]]`
(SQL→DuckDB), but with no engine, no node, no worker: just fmgr + SPI.

## How it hooks into PG

The control file is minimal — `default_version = '1.5.11'`, `relocatable = false`,
`schema = 'graphql'` (`pg_graphql.control`) `[verified-by-code]`. There is **no
`_PG_init`, no hook, no background worker, no GUC**. `lib.rs` declares
`pg_module_magic!()` and then a handful of `extension_sql_file!` blocks that
install the SQL wrapper objects (`schema_version.sql`, `directives.sql`,
`raise_exception.sql`, `resolve.sql`) (`src/lib.rs:20-25`) `[verified-by-code]`.
The entire C-side surface is one `#[pg_extern(name = "_internal_resolve")]`
function (`src/lib.rs:27-74`) `[verified-by-code]`:

```rust
fn resolve(query: &str, variables: Option<JsonB>,
           operationName: Option<String>, extensions: Option<JsonB>) -> pgrx::JsonB {
    let query_ast = parse_query::<&str>(query) ...;
    let sql_config  = sql_types::load_sql_config();      // reflect config
    let context     = sql_types::load_sql_context(&cfg); // reflect schema (cached)
    let graphql_schema = __Schema { context };
    resolve_inner(query_ast, &variables, &operationName, &graphql_schema)
}
```

So pg_graphql is *lazy-loaded* (no preload), exposes itself as ordinary SQL
(`graphql.resolve(...)`), and does all its work inside one function call per
GraphQL request. Cross-ref `[[knowledge/idioms/fmgr]]` (the pg_extern +
SPI calling convention it lives entirely inside), `[[knowledge/ideologies/pgrx]]`
(the framework providing `pg_extern`/`JsonB`/`Spi`), and the
`extension-development` skill (a SQL-function-only, no-hook extension).

## Where it diverges from core idioms

### 1. The "GraphQL schema" is a single SQL introspection query, deserialized and memoized

There is no in-memory schema object maintained by a server. `load_sql_context`
runs `include_str!("../sql/load_sql_context.sql")` — one big read-only catalog
query — through `get_one_readonly`, which returns a *single `JsonB`* describing
every table, column, foreign key, enum, and function, then
`serde_json::from_value`s it into a `Context` struct and runs cross-reference
passes (`type_details`, `column_types`, `populate_table_functions`)
(`src/sql_types.rs:861-890, 893+`) `[verified-by-code]`. The result is wrapped in
`#[cached(type = "SizedCache<u64, ...Arc<Context>>", ... convert = "calculate_hash(_config)")]`
(`src/sql_types.rs:878-883`) `[verified-by-code]` — an LRU of 250 entries keyed
by a hash of the reflected config, so the expensive introspection runs once per
distinct schema version and is reused across resolve calls in the backend.
Reflecting the entire schema as JSON via one query and memoizing it is the
inverse of how a typical GraphQL server builds its schema (code-first or
SDL-first, in the app process). Cross-ref
`[[knowledge/idioms/catalog-conventions]]` (the `pg_class`/`pg_attribute`/`pg_constraint`
the introspection SQL reads), `catalog-conventions` skill.

### 2. A whole GraphQL query becomes exactly ONE SQL statement returning the finished JSON

This is the load-bearing divergence. A GraphQL selection set with nested
relationships does *not* become N queries; the `QueryEntrypoint` /
`MutationEntrypoint` traits build one SQL string via `to_sql_entrypoint` and
execute it once. `QueryEntrypoint::execute` does `Spi::connect(|c|
c.select(sql, Some(1), &param_context.params))` and pulls a single `JsonB`
out of column 1 (`src/transpile.rs:78-108`) `[verified-by-code]`; the mutation
path uses `conn.update(sql, ...)` the same way (`:47-75`). The emitted SQL nests
`jsonb_build_object` / `to_jsonb` / `jsonb_agg` so the database itself assembles
the entire nested GraphQL response shape — e.g. the insert entrypoint wraps the
result in `jsonb_build_object({select_clause})` (`src/transpile.rs:322-330`)
`[verified-by-code]`. Pushing the *response serialization* into a single SQL
statement (rather than fetching rows and assembling JSON in app code) means one
planner pass, one snapshot, one round trip per GraphQL request. Cross-ref
`[[knowledge/subsystems/executor]]`, `[[knowledge/idioms/fmgr]]`.

### 3. User input is bound as real parameters, not interpolated; identifiers quoted via core `quote_ident`

Transpiling a query language to SQL is a classic injection footgun. pg_graphql
threads a `ParamContext { params: vec![] }` through the whole emission: literal
values become bind parameters via `param_context.clause_for(&val, &type_name)`
(`src/transpile.rs:194`) and are passed to SPI as `&param_context.params`
(`:60, :92`) `[verified-by-code]` — never string-concatenated. Identifiers
(table/column names from the catalog) are quoted by calling the *core C function*
`quote_ident` through pgrx's `direct_function_call::<String>(pg_sys::quote_ident,
...)` (`src/transpile.rs:18-20`) `[verified-by-code]`, i.e. it reuses Postgres's
own identifier-quoting rather than reimplementing them. Separating
catalog-derived identifiers (quoted) from user-supplied values (parameterized) is
a disciplined safety posture executed entirely in generated SQL.

### 4. Reflection uses `client.select` (not `update`) so it works on a read replica

A small but telling detail: `get_one_readonly` exists specifically because
`Spi::get_one` internally uses `client.update`, which "generates a new
transaction id so calling `Spi::get_one` is not possible when postgres is in
recovery mode" (`src/sql_types.rs:850-858`) `[verified-by-code]`. By doing schema
reflection through `client.select` only, pg_graphql can resolve read queries on a
hot standby where assigning an XID would fail. Designing the introspection path
to be XID-free so it survives recovery mode is a replica-awareness most
SQL-emitting extensions ignore. Cross-ref
`[[knowledge/subsystems/replication]]`,
`[[knowledge/idioms/fmgr]]` (SPI read-only vs read-write).

### 5. Configuration is carried in catalog COMMENTs as `@graphql({...})` JSON directives

pg_graphql has no GUCs. Instead it reads behavior from `COMMENT ON` directives:
`COMMENT ON SCHEMA public IS e'@graphql({"inflect_names": true})'`
(`README.md:64-67`) `[from-README]`, with the directive grammar installed by
`extension_sql_file!("../sql/directives.sql")` (`src/lib.rs:23`)
`[verified-by-code]`. Inflection (snake_case→PascalCase/camelCase), name
overrides, and per-object visibility all live as JSON inside catalog comments,
which `load_sql_config` / `load_sql_context` pick up during reflection. Storing
extension configuration *in the catalog comments of the objects being exposed*,
rather than in GUCs or an extension table, keeps the GraphQL surface declarative
and travels with `pg_dump`. Cross-ref `[[knowledge/idioms/catalog-conventions]]`.

## Notable design decisions (cited)

- **Cursor pagination encoded in SQL** — the cursor is a base64 of a `jsonb`
  array built and encoded *by the database*:
  `translate(encode(convert_to(jsonb_build_array({clause})::text, 'utf-8'),
  'base64'), E'\n', '')` (`src/transpile.rs:146-148`) `[verified-by-code]`, so
  keyset pagination is consistent with the same snapshot that produced the rows.
- **Permissions respected in the generated SQL** — columns are filtered by
  `x.permissions.is_selectable` when building the select clause
  (`src/transpile.rs:112-118`) `[verified-by-code]`; the reflected `Context`
  carries per-column permission bits, so the transpiled SQL only ever names
  columns the role may read (defense in depth on top of the executor's own RLS/
  privilege checks).
- **Parser errors return a GraphQL error envelope, not a PG ERROR** — a failed
  `parse_query` produces a `GraphQLResponse { data: Omitted, errors: Present }`
  (`src/lib.rs:38-49`) `[verified-by-code]`, i.e. malformed GraphQL yields a
  well-formed GraphQL error JSON rather than aborting the SQL statement.
- **No hooks, no worker, no shmem, no GUC** (`src/lib.rs` whole) — the extension
  is a pure SQL-callable function plus a few SQL wrapper objects; everything
  stateful (the schema) is reflected on demand and cached per backend.

## Links into corpus

- `[[knowledge/idioms/fmgr]]` — pg_graphql lives entirely inside the
  pg_extern + SPI calling convention; the single most important cross-reference
  (one function in, one transpiled SQL statement out via `Spi::connect`).
- `[[knowledge/idioms/catalog-conventions]]` + `catalog-conventions` skill — the
  reflection query reads `pg_class`/`pg_attribute`/`pg_constraint`/`pg_type`/
  `pg_proc`, and configuration rides in catalog COMMENTs.
- `[[knowledge/ideologies/pgrx]]` — the Rust framework supplying `#[pg_extern]`,
  `JsonB`, `Spi`, and `direct_function_call(pg_sys::quote_ident)`; pg_graphql is
  a downstream of pgrx exactly like zombodb and wrappers.
- `[[knowledge/ideologies/apache-age]]` + `[[knowledge/ideologies/pg_duckdb]]` —
  the other "embed a foreign query language" extensions; AGE adds a planner-hook
  Cypher rewrite, pg_duckdb swaps the plan to DuckDB, pg_graphql instead stays a
  plain function that transpiles to one SQL statement (no hook at all).
- `[[knowledge/subsystems/replication]]` — the `client.select`-only
  reflection path that keeps read resolution working on a hot standby.
- `[[knowledge/subsystems/executor]]` — the single transpiled statement whose
  `jsonb_build_object`/`jsonb_agg` tree the executor evaluates to assemble the
  whole GraphQL response shape.
- `.claude/skills/extension-development/SKILL.md` — a SQL-function-only,
  no-hook, lazy-loaded extension; the contrast with hook/preload modules.

## Sources

Fetched 2026-06-11 (branch `master`):

- `https://api.github.com/repos/supabase/pg_graphql/git/trees/master?recursive=1`
  @ 2026-06-11 → HTTP 200 (tree listing; 314 blobs).
- `https://raw.githubusercontent.com/supabase/pg_graphql/master/README.md`
  @ 2026-06-11 → HTTP 200 (77 lines; overview + reflection claim + directive
  example).
- `https://raw.githubusercontent.com/supabase/pg_graphql/master/pg_graphql.control`
  @ 2026-06-11 → HTTP 200 (6 lines).
- `https://raw.githubusercontent.com/supabase/pg_graphql/master/src/lib.rs`
  @ 2026-06-11 → HTTP 200 (90 lines; the single `_internal_resolve` entrypoint).
- `https://raw.githubusercontent.com/supabase/pg_graphql/master/src/sql_types.rs`
  @ 2026-06-11 → HTTP 200 (1055 lines; `load_sql_config`/`load_sql_context`/
  `get_one_readonly`/`#[cached]` read; the reflection-pass bodies sampled).
- `https://raw.githubusercontent.com/supabase/pg_graphql/master/src/transpile.rs`
  @ 2026-06-11 → HTTP 200 (2062 lines; `QueryEntrypoint`/`MutationEntrypoint`
  execute + `quote_ident` + ParamContext + cursor/permission clauses read; the
  per-node SQL emission sampled).
- `https://raw.githubusercontent.com/supabase/pg_graphql/master/src/resolve.rs`
  @ 2026-06-11 → HTTP 200 (651 lines; `resolve_inner` dispatch skimmed).

All structural cites (single `_internal_resolve` pg_extern, `extension_sql_file!`
wrappers, `load_sql_context` one-query+`#[cached]` reflection, one-SQL-statement
`execute` via SPI returning `JsonB`, `ParamContext` binding, `quote_ident` via
`direct_function_call`, `get_one_readonly`-for-recovery-mode, permission-filtered
select, cursor base64-in-SQL) are `[verified-by-code]` against the fetched
`.rs`/`.control`; the "no additional servers/processes/libraries" framing,
schema-reflection premise, and `@graphql({...})` COMMENT directive example are
`[from-README]` (`README.md:18-71`), cross-checked against `lib.rs`/`sql_types.rs`
where present. The full per-GraphQL-node SQL builders, the reflection SQL files
themselves (`sql/load_sql_context.sql`, `sql/directives.sql`), and `resolve.rs`
field-resolution were not deep-read.
