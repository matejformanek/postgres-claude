# index_advisor — a whole "extension" that is one PL/pgSQL function, using EXPLAIN (FORMAT JSON) as a cost oracle and hypopg as its planner hook

> Ideology note produced by the `pg-extension-anthropologist` cloud routine.
> Repo: `supabase/index_advisor` @ branch `main`. All `file:line` cites below
> point into that repo (not `source/`), since this doc characterizes an
> *external* extension's divergence from core idioms. The entire shipped logic
> is one file, `index_advisor--0.2.0.sql` (191 lines); cites verified against the
> files fetched on 2026-06-13 (see Sources footer). Read alongside
> `[[knowledge/ideologies/hypopg]]` (the C extension it parasitizes) and
> `[[knowledge/ideologies/pg_qualstats]]` / `[[knowledge/ideologies/pg_hint_plan]]`
> for the planner-introspection neighborhood.

## Domain & purpose

index_advisor answers "which `CREATE INDEX` statements would make this query
cheaper?" without building any index. "For a given *query*, searches for a set
of SQL DDL `create index` statements that improve the query's execution time"
(`README.md:23-24`) `[from-README]`. The mechanism: enumerate candidate
single-column indexes over every table the query could touch, materialize them
as **hypothetical** indexes via hypopg, re-plan, parse the cost out of the
`EXPLAIN (FORMAT JSON)` output, and report which hypothetical indexes the new
plan actually chose along with before/after cost numbers
(`index_advisor--0.2.0.sql:80-172`) `[verified-by-code]`. It is the corpus's
purest example of an extension that does **real planner-driven analysis with no
C code at all** — no `.so`, no `_PG_init`, no hook. Every other extension in the
corpus owns a shared library; this one owns a function body. That makes it the
sharpest available study of how far you can push core's SQL/PL surface as an
*application platform* rather than as glue around C.

## How it hooks into PG

It doesn't — and that is the whole story. The "extension" is a PGXS package
(`Makefile:1-10`) whose only payload is `DATA = $(wildcard
index_advisor--*.sql)` (`Makefile:2`) — a single install script, no
`MODULE_big`, no `OBJS`, no C source. The control file declares
`relocatable = true` and, crucially, `requires = hypopg`
(`index_advisor.control:3-4`) `[verified-by-code]`: index_advisor delegates the
*entire* "lie to the planner" mechanism to hypopg's hooks
(`get_relation_info_hook` / `build_simple_rel_hook`, see
`[[knowledge/ideologies/hypopg]]`). index_advisor never touches a `RelOptInfo`,
never installs a planner hook, never sees a `PlannerInfo`. It only emits SQL
strings that *drive* hypopg and then reads the planner's verdict back out of
`EXPLAIN` text.

The function is `CREATE OR REPLACE FUNCTION index_advisor(query text) RETURNS
TABLE (...) VOLATILE LANGUAGE plpgsql` (`index_advisor--0.2.0.sql:1-14`)
`[verified-by-code]`. Its tools are entirely the dynamic-SQL surface of PL/pgSQL:
`EXECUTE format(...)`, `PREPARE`/`DEALLOCATE`, `EXECUTE ... INTO`, a `FOR rec
IN ... LOOP`, and `GET STACKED DIAGNOSTICS`. The hypopg calls it generates are
themselves SQL: `hypopg_create_index(...)`, `hypopg()`,
`hypopg_get_indexdef(...)`, `hypopg_reset()`
(`index_advisor--0.2.0.sql:95, 149-151, 160`) `[verified-by-code]`.

Cross-ref `[[knowledge/ideologies/hypopg]]`,
`.claude/skills/executor-and-planner/SKILL.md` (the cost oracle it queries),
`.claude/skills/extension-development/SKILL.md` (the PGXS/control surface it
minimally uses).

## Where it diverges from core idioms

### 1. Zero C surface — an "extension" defined entirely by a PL/pgSQL function body

Every other extension documented in this corpus ships a loadable C library and
hangs behavior off `_PG_init` and/or a hook chain (hypopg, pg_hint_plan,
pg_cron, postgis…). index_advisor ships **none**: `Makefile:1-2` lists only
`EXTENSION` + `DATA`, with no `MODULE_big`/`OBJS`, and the control file's
behavioral contribution is one line — `requires = hypopg`
(`index_advisor.control:4`) `[verified-by-code]`. The extension is therefore
*trusted-adjacent by construction* (no native code to audit), but it inherits
all of hypopg's C risk transitively. This inverts the usual divergence frame:
the interesting thing is not what C invariant it bends, but that it bends none
because it has no C — it is a **macro over hypopg + EXPLAIN written in SQL**.

### 2. EXPLAIN (FORMAT JSON) abused as a programmatic cost oracle

Core treats `EXPLAIN` as a human-facing diagnostic. index_advisor treats its
JSON form as a machine API. It builds `set local plan_cache_mode =
force_generic_plan; explain (format json) execute <stmt>(<args>)`
(`index_advisor--0.2.0.sql:65-75`), runs it twice (`:78` before indexes, `:142`
after), captures each result as `jsonb` via `EXECUTE ... INTO plan_initial`, and
then reads scalar costs by JSON path navigation: `plan_initial -> 0 -> 'Plan' ->
'Total Cost'` and `'Startup Cost'` (`:165-169`) `[verified-by-code]`. So the
*planner's own costing* becomes the objective function for an optimization the
planner never knows it is part of. This is a genuinely different contract than
`EXPLAIN`'s designers assume: the JSON shape (`[ { "Plan": { "Total Cost": …
}}]`) is being depended on as a stable interface from SQL. Cross-ref
`.claude/skills/executor-and-planner/SKILL.md` (where `Total Cost`/`Startup
Cost` come from — `cost.h` units surfaced through `explain.c`).

### 3. Combinatorial index enumeration done in SQL, against the live catalog

The candidate set is computed by one big catalog query
(`index_advisor--0.2.0.sql:81-123`) `[verified-by-code]` that joins `pg_class`,
`pg_attribute`, `pg_index`, and `pg_depend`, then for each surviving
(table, column) pair emits a `hypopg_create_index('create index on
schema.table(col)')` string. The filtering encodes a lot of policy in SQL
predicates rather than C:

- only `relkind in ('r','m')` (regular tables + matviews) and
  `relpersistence = 'p'` (permanent, not temp/unlogged) (`:117-118`);
- skip system schemas `pg_catalog`/`pg_toast`/`information_schema` (`:113-115`);
- skip objects **owned by extensions** via a `pg_depend deptype = 'e'`
  anti-join (`:82-89, 116`) — a nice touch: don't recommend indexes on
  extension-managed tables;
- skip columns already covered by a non-expression, non-partial index, by
  matching `indkey` against the single `attnum` (`:107-121`);
- restrict to an allow-list of indexable type OIDs hard-coded as integer
  literals: `pa.atttypid in (20,16,1082,1184,1114,701,23,21,700,1083,2950,1700,
  25,18,1042,1043)` (`:122`) `[verified-by-code]` — int8/bool/date/timestamptz/
  timestamp/float8/int4/int2/float4/time/uuid/numeric/text/char/bpchar/varchar.

Note the **enumeration is single-column only**: it creates one hypothetical
index per eligible column and lets the planner pick (`:90-127`), then reports
back exactly the subset the final plan referenced (`:147-157`). There is no
multi-column or covering-index search — the "combinatorial" search is really
"offer all single columns, let cost decide." `[verified-by-code]`

### 4. Parameter neutralization and query rewriting via string surgery

A real query may carry `$1, $2, …` placeholders the advisor cannot bind. Its
workaround is textual. First it strips comments and collapses whitespace with
three stacked `regexp_replace` calls (`:28-34`) and removes a trailing semicolon
(`:37`), then **forbids** any remaining semicolon — `if query ilike '%;%' then
raise exception 'Query must not contain a semicolon'` (`:41-43`)
`[verified-by-code]` — a crude multi-statement guard. It counts parameters by
`PREPARE`-ing the query and reading `array_length(parameter_types,1)` from
`pg_prepared_statements` (`:49-62`), then synthesizes a `NULL` for each: it
`array_fill('null', array[n_args])` and interpolates `execute stmt(null,null,…)`
(`:69-75`) `[verified-by-code]`. So every parameter is planned as a literal
`NULL` of unknown type, which is why it also forces `plan_cache_mode =
force_generic_plan` (`:66`) — to get a parameter-independent generic plan rather
than one specialized to `NULL`. There is even a hard-coded special case
rewriting PostgREST's `WITH pgrst_payload AS (SELECT $1 AS json_data)` to cast
`$1::json` (`:46`) `[from-comment]` — an application-specific hack living inside
a general-purpose extension.

### 5. Caller-privilege execution + SQL interpolation of the user's query

The function is plain `LANGUAGE plpgsql` with **no `SECURITY DEFINER`** and **no
`SET search_path`** pin (`index_advisor--0.2.0.sql:1-14`) `[verified-by-code]`.
Consequences:

- It runs with the **caller's** privileges and the caller's `search_path`. The
  catalog scan, the hypothetical-index creation, and the `EXPLAIN` all see only
  what the caller can see — appropriate for an advisor, but it means results are
  privilege- and search_path-dependent, not a pure function of the query text.
- The user-supplied `query` is interpolated straight into `prepare %I as %s`
  via `format` with the **`%s`** (raw) specifier (`:50, 139`)
  `[verified-by-code]`. This is *intended* — the advisor must plan arbitrary
  SQL — but it means the function is, definitionally, an arbitrary-SQL executor:
  the `EXECUTE` of `prepare … as <query>` parses and plans whatever is passed,
  and `force_generic_plan` + the `NULL` args do not execute the query, only plan
  it. The semicolon ban (`:41-43`) is the only injection guard, and it is
  textual (an `ilike '%;%'` over an already comment-stripped string), not a
  parser-level one. A function-valued or DDL-bearing payload that survives the
  semicolon check is planned under the caller's rights.
- It does pin hypopg's schema dynamically — `hypopg_schema_name` is resolved
  from `pg_extension`/`extnamespace` and every hypopg call is
  schema-qualified (`%I.hypopg_create_index`, `%I.hypopg()`)
  (`:18, 95, 151`) `[verified-by-code]` — so hypopg cannot be shadowed by a
  malicious search_path entry, even though the advisor's own search_path is
  unpinned.

### 6. Side-effects and cleanup managed by hand inside one big BEGIN/EXCEPTION block

Hypothetical-index creation is a backend-local side effect; prepared statements
are session state. The advisor wraps its whole body in an inner `begin … exception
when others then …` (`:39-187`) and cleans up on **both** paths:

- happy path resets hypopg state with `perform hypopg_reset()` (`:160`) and
  clears prepared statements with `deallocate all` (`:163`)
  `[verified-by-code]`;
- error path catches *everything* (`when others`), pulls the message via
  `get stacked diagnostics error_message = MESSAGE_TEXT` (`:175-176`), and
  returns it in the `errors text[]` output column instead of propagating
  (`:178-185`) `[verified-by-code]`.

The cleanup is **not** in a `finally`-equivalent — PL/pgSQL has none — so the
`hypopg_reset()`/`deallocate all` on the happy path (`:160-163`) is *skipped* if
an error is thrown, and the `exception` handler does **not** itself call
`hypopg_reset()`. That leaves hypothetical indexes registered in the backend on
the error path (relying on hypopg's own session-scoped, ephemeral nature for
eventual cleanup) `[inferred]`. It also does `deallocate all` (`:49`) *before*
preparing — clearing unrelated session prepared statements as a precondition, a
notable bit of session-state stomping for a read-only-looking advisory call.

## Notable design decisions (cited)

- **`force_generic_plan` is essential, not incidental** (`:66`): with every
  parameter replaced by a typeless `NULL`, a custom plan would be costed against
  `NULL` selectivity; the generic plan is what makes the before/after numbers
  meaningful `[inferred from-comment]`.
- **Re-prepare between before and after** because plans are cached: the comment
  is explicit — "The original prepared statement MUST be dropped because its
  plan is cached" — so it `deallocate`s and re-`prepare`s after injecting the
  hypothetical indexes (`:136-139`) `[from-comment]`. Without this the "after"
  EXPLAIN would reuse the pre-index cached plan and show no improvement.
- **Attribution by name-substring match**, not by index OID: it decides which
  hypothetical indexes the new plan used by checking `quote_literal(plan_final)
  ilike '%' || indexname || '%'` against the hypopg catalog
  (`:147-157`) `[verified-by-code]` — a stringly-typed join between the EXPLAIN
  JSON and `hypopg()`'s synthesized index names, because the hypothetical
  indexes have no real OID to match on. Brittle by nature, but it is the only
  bridge available between EXPLAIN text and hypopg's in-memory list.
- **`quote_literal(plan_final)::text` interpolated into dynamic SQL** (`:156`):
  the whole JSON plan is embedded as a string literal inside another `EXECUTE`d
  query, a second layer of code-gen on top of the first.
- **Output is six columns of `jsonb`/`text[]`** including raw cost JSONB scalars
  (`startup_cost_before`, etc.) rather than parsed numerics (`:4-11, 165-169`)
  `[verified-by-code]` — leaving numeric extraction to the caller.

## Links into corpus

- `[[knowledge/ideologies/hypopg]]` — the C extension index_advisor is a
  "parasite" on. hypopg owns the planner hooks; index_advisor only emits
  `hypopg_create_index`/`hypopg()`/`hypopg_get_indexdef`/`hypopg_reset` SQL and
  reads the result out of EXPLAIN. The division of labor is the point: hypopg
  lies to the planner, index_advisor reads the planner's verdict.
- `[[knowledge/ideologies/pg_qualstats]]` / `[[knowledge/ideologies/pg_hint_plan]]`
  — neighbors in the planner-introspection / index-recommendation space; both
  are C extensions with hooks, the contrast that makes index_advisor's
  zero-C posture stand out.
- `.claude/skills/executor-and-planner/SKILL.md` — where `Total Cost` /
  `Startup Cost` originate (`cost.h` units surfaced via `explain.c`); the cost
  oracle index_advisor queries.
- `.claude/skills/extension-development/SKILL.md` — PGXS `DATA`-only packaging,
  `.control` `requires =` dependency, no `MODULE_big`.
- `.claude/skills/fmgr-and-spi/SKILL.md` — by contrast, index_advisor uses
  *none* of the C fmgr/SPI surface; it reaches the same machinery through
  PL/pgSQL `EXECUTE` and `pg_prepared_statements`, which is itself the
  divergence worth noting.

## Anthropology takeaway

index_advisor is the corpus's clearest demonstration that a "PostgreSQL
extension" need contain no compiled code at all: it is a 191-line PL/pgSQL
function plus a `requires = hypopg` line. Its cleverness is *compositional* — it
turns three things core never designed as programmatic APIs (hypopg's hypothetical
indexes, `EXPLAIN (FORMAT JSON)`'s output shape, and `plan_cache_mode =
force_generic_plan`) into the inner loop of an index-recommendation optimizer,
and orchestrates them with dynamic SQL string surgery. The sharpest divergences
for a future `knowledge/issues` note are two: (a) it depends on the *stability of
EXPLAIN's JSON contract* (`-> 0 -> 'Plan' -> 'Total Cost'`) as if it were an API,
which it is not — a plan-shape change upstream silently breaks the advisor; and
(b) it is an **arbitrary-SQL executor running under caller privileges**, guarded
only by a textual semicolon ban over comment-stripped input, with `search_path`
unpinned (only hypopg's schema is qualified). Anyone exposing
`index_advisor(text)` to untrusted callers is exposing "parse and plan this SQL
as me," and the cleanup of hypothetical-index and prepared-statement session
state is hand-rolled and *skipped on the error path*, relying on hypopg's
ephemerality rather than a guaranteed `finally`. The whole thing is a small
masterclass in treating the planner as a queryable cost oracle from pure SQL —
and a reminder that "no C, therefore safe" is exactly wrong when the SQL surface
includes `EXECUTE format('prepare … as %s', user_input)`.

## Sources

Fetched 2026-06-13 (branch `main`):

- `https://raw.githubusercontent.com/supabase/index_advisor/main/README.md`
  @ 2026-06-13 → HTTP 200 (4134 bytes; API signature, usage examples,
  hypopg dependency note read).
- `https://raw.githubusercontent.com/supabase/index_advisor/main/index_advisor--0.2.0.sql`
  @ 2026-06-13 → HTTP 200 (6610 bytes; **the entire extension**, deep-read —
  query normalization, parameter neutralization, catalog enumeration, hypopg
  driving, EXPLAIN cost parsing, attribution, cleanup, error handling).
- `https://raw.githubusercontent.com/supabase/index_advisor/main/index_advisor.control`
  @ 2026-06-13 → HTTP 200 (95 bytes; `relocatable = true`, `requires = hypopg`,
  `default_version = '0.2.0'`).
- `https://raw.githubusercontent.com/supabase/index_advisor/main/Makefile`
  @ 2026-06-13 → HTTP 200 (272 bytes; PGXS `DATA`-only, no `MODULE_big`/`OBJS`;
  REGRESS test wiring).

All cites are `[verified-by-code]` against the fetched
`index_advisor--0.2.0.sql`/`.control`/`Makefile` except the PostgREST special
case and the re-prepare rationale (`[from-comment]`, the file's own comments),
the README-sourced purpose statement (`[from-README]`), and the error-path
cleanup gap + `force_generic_plan` rationale (`[inferred]` from control flow).
hypopg's internals are characterized in `[[knowledge/ideologies/hypopg]]`, not
re-verified here.
