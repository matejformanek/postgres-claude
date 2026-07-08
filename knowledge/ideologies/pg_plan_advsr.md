# pg_plan_advsr — an adaptive plan-feedback loop built in extension space, parasitic on two sibling extensions and their vendored plan-JSON code

> Ideology note produced by the `pg-extension-anthropologist` cloud routine.
> Repo: `ossc-db/pg_plan_advsr` @ branch `master` (~120★, C). All `file:line`
> cites below point into that repo (not `source/`), since this doc characterizes
> an *external* extension's divergence from core idioms. Files fetched
> 2026-07-08 (see Sources footer). Read alongside
> `[[knowledge/ideologies/index_advisor]]` and
> `[[knowledge/ideologies/plpgsql_check]]` (the parasite-on-a-sibling family)
> and `[[knowledge/ideologies/pg_hint_plan]]` (one of the two hosts).

## Domain & purpose

pg_plan_advsr does **automated execution-plan tuning using a feedback loop**
(`README.md:4`) `[from-README]`. The pitch: for an analytic query with many
joins/aggregates, run `EXPLAIN ANALYZE` repeatedly and let the extension
converge the planner onto an efficient plan by correcting its row-count
estimation errors (`pg_plan_advsr.c:3-5`, `README.md:5,255-256`)
`[verified-by-code]`. Each execution, it reads the **actual** row counts out of
the finished `PlanState` instrumentation tree, diffs them against the planner's
**estimates**, and when they diverge it emits a `pg_hint_plan` hint set —
`Rows(...)` corrections plus scan/join-method and leading hints — which it
stores so the next run picks them up and re-plans. Iterate until the estimation
error vanishes and the plan stops changing (`README.md:40-41,256,273-274`)
`[from-README]`. It is the corpus's **executor-feedback** member of the
"parasite on a sibling extension" family: where `[[index_advisor]]` reads
`EXPLAIN` cost back as an oracle over hypopg's hooks, pg_plan_advsr reads
`Instrumentation.ntuples` back as an oracle and writes corrections into
pg_hint_plan's own table. Explicitly a validation-environment tool, not for
production (`README.md:7`) `[from-README]`.

## How it hooks into PG

`_PG_init` installs **seven** chained hooks (`pg_plan_advsr.c:717-736`)
`[verified-by-code]`, saving each predecessor first:

- `post_parse_analyze_hook` — normalizes/jumbles the query text
  (`pg_plan_advsr.c:717-718,835`).
- `ProcessUtility_hook` — intercepts the `EXPLAIN` utility statement
  (`pg_plan_advsr.c:720-721,932`).
- `ExplainOneQuery_hook` — drives the EXPLAIN path (`pg_plan_advsr.c:723-724`).
- `ExecutorStart/Run/Finish/End_hook` — the executor lifecycle
  (`pg_plan_advsr.c:726-736`). A source comment states the Start/Run/Finish
  bodies "are came from pg_store_plans.c" (`pg_plan_advsr.c:1118`)
  `[from-comment]`.

The load-bearing hook is `ExecutorEnd`. When enabled and the current query
matches the pending EXPLAIN text, it builds a fresh `ExplainState` with
`analyze=true, format=EXPLAIN_FORMAT_JSON` and walks the plan tree itself via
`pg_plan_advsr_ExplainPrintPlan` (`pg_plan_advsr.c:1210-1244`)
`[verified-by-code]`. There is **no `planner_hook`** — pg_plan_advsr never sees
a `PlannerInfo`; it injects its influence entirely through the hint table that
pg_hint_plan reads (below).

**Three GUCs**, all `DefineCustomBoolVariable`: `pg_plan_advsr.enabled`,
`.quieted`, `.widely` (`pg_plan_advsr.c:738-772`) `[verified-by-code]`. The
feedback loop is armed not by a GUC but by two SQL-callable C functions:
`pg_plan_advsr_enable_feedback()` / `_disable_feedback()`
(`pg_plan_advsr.sql:69-77`, `pg_plan_advsr.c:793-833`) `[verified-by-code]`.

**Dependency wiring.** It requires pg_hint_plan **and** pg_store_plans loaded in
the same `shared_preload_libraries` line
(`README.md:331,410`; `pg_plan_advsr, pg_hint_plan, pg_store_plans`)
`[from-README]`, plus `compute_query_id = on` and (recommended) parallelism
disabled (`README.md:411-413`) `[from-README]`. Storage is its own schema
`plan_repo` with tables `plan_history`, `norm_queries`, `raw_queries` and two
SQL SRFs `plan_repo.get_hint(bigint)` / `plan_repo.get_extstat(bigint)`
(`pg_plan_advsr.sql:6-161`, `README.md:104-106`) `[verified-by-code]`.

**libpq linkage — verified inert.** The Makefile links libpq
(`SHLIB_LINK = $(libpq)`, `Makefile:14`) and the source `#include "libpq-int.h"`
(`pg_plan_advsr.c:42`), which invites the assumption of an autonomous
self-connection. There is none: a grep of `pg_plan_advsr.c` finds **zero**
`PQconnect*`/`PQexec*`/`PGconn` uses `[verified-by-code]`. Every database access
is in-process — direct heap (`table_open`/`CatalogTupleInsert`,
`pg_plan_advsr.c:456-462`) and `DirectFunctionCall1(nextval_oid, ...)`
(`pg_plan_advsr.c:376`). The libpq link and `libpq-int.h` include are
**inherited from the vendored pg_store_plans code**, which links libpq for query
normalization — not evidence of a self-connection. Tag any "opens a connection"
claim `[unverified]`; the code contradicts it.

## Where it diverges from core idioms

**1. An adaptive-query-optimization loop implemented offline, in extension
space.** Core Postgres plans once from static `pg_statistic` and never learns
from the execution it just ran. pg_plan_advsr reconstructs the
"observe-actuals → correct-model → re-plan → repeat" loop entirely outside the
backend's planner, using EXPLAIN-ANALYZE runs as the sampling mechanism and the
hint table as the persisted correction. It is a manual, per-query approximation
of Oracle's SQL Plan Management / cardinality-feedback and the academic AQO
line — but with zero core changes, because it never touches the cost model; it
overrides cardinalities from outside via `Rows()` hints.

**2. Parasite on two siblings at once — and it reaches into one sibling's
private catalog table by name.** Reading actual-vs-estimated is the extension's
own code, but *acting* on it is delegated: the generated `Rows()`/scan/join
hints are written straight into **pg_hint_plan's** own table `hint_plan.hints`
via raw heap access — `selectHints`/`deleteHints`/`insertHints` do
`table_open(get_relname_relid("hints", LookupExplicitNamespace("hint_plan",...)))`
and `systable_beginscan` against pg_hint_plan's index `hints_norm_and_app`
(`pg_plan_advsr.c:549-593,600-645,651-687`) `[verified-by-code]`. It never calls
a pg_hint_plan C API; it mutates the sibling's storage directly. `enable_feedback`
then flips the sibling's own GUCs — `set_config_option("pg_hint_plan.enable_hint_table","ON")`
and `pg_hint_plan.debug_print` (`pg_plan_advsr.c:797-807`) `[verified-by-code]`
— so pg_hint_plan auto-injects those rows into the planner on the next run.
That is a tighter coupling than `[[index_advisor]]` (which only calls hypopg's
public SQL functions): pg_plan_advsr owns table rows inside another extension.

**3. Vendored-internal-code — copied, not linked, from BOTH siblings.** The
plan-JSON serialization (`pgsp_json.c`, `pgsp_json_text.c`, `pgsp_json.h`) is
not in the repo at all: the build instructions tell you to
`cp pgsp_json*.[ch] ../pg_plan_advsr/` out of a pg_store_plans checkout, and
`cp pg_stat_statements.c` + `cp normalize_query.h` out of pg_hint_plan
(`README.md:385-390`) `[from-README]`; the includes name their provenance
(`/* came from pg_hint_plan */`, `/* came from pg_store_plans */`,
`pg_plan_advsr.c:52-56`) `[from-comment]`, and `OBJS` compiles the copied
objects (`Makefile:4`) `[verified-by-code]`. This is the same
"vendor a copy of internal serialization you can't link to" move as
`[[pg_squeeze]]` copying `cluster.c`'s swap logic and `[[pg_bulkload]]`
vendoring `nbtsort` — except pg_plan_advsr does it as a **documented manual
build step across two source trees**, the most brittle version of the pattern.
`create_pgsp_planid` is itself "inspired store_entry() and pgsp_ExecutorEnd() in
pg_store_plans" (`pg_plan_advsr.c:1257-1258`) `[from-comment]`.

**4. Actual rows lifted from the same instrumentation EXPLAIN ANALYZE uses.**
`CreateScanJoinRowsHints` forces `InstrEndLoop(planstate->instrument)` then reads
`rows = planstate->instrument->ntuples / nloops` as the actual row count
(`pg_plan_advsr.c:1944-1951`) `[verified-by-code]` — the exact
`InstrEndLoop`/`ntuples`/`nloops` idiom `explain.c` uses. A source comment even
flags the forced cleanup as "pretty grotty" because ExecutorEnd hasn't run yet
(`pg_plan_advsr.c:1935-1945`) `[from-comment]`. It then compares to the plan
node's `est_rows`, and on divergence appends `ROWS(<rels> #<act>)` to the hint
buffer (`pg_plan_advsr.c:2020-2033`) `[verified-by-code]`.

**Correctness / soundness caveats.** (a) *Convergence is not guaranteed and is
data-dependent* — the README warns a plan "may temporarily [be] worse" mid-tune
and that it "doesn't get converged plan ... if it was updating concurrently"
(`README.md:273-274`) `[from-README]`. (b) *Stale hints accumulate*: each run
reads the previous `hint_plan.hints` row and re-writes it appended with the new
`Rows()` corrections (`pg_plan_advsr.c:1800-1821`) `[verified-by-code]`, so the
hint set is cumulative per normalized query + application_name — changing data
between runs leaves stale corrections behind. (c) *Scope holes*: it explicitly
does not handle InitPlan/SubPlan or Append/MergeAppend, cannot fix base-relation
row errors (a pg_hint_plan limitation), and is untested on parallel query,
partitioned tables, and JIT (`README.md:482-493`) `[from-README]`. (d) Keying on
normalized-query MD5 + `application_name` (`pg_plan_advsr.c:1766-1773`)
`[verified-by-code]` means two clients with different `application_name` get
separate hint lineages.

## Notable design decisions

- **Seven chained hooks, predecessors preserved** — install at
  `pg_plan_advsr.c:717-736`, restored in `_PG_fini` at
  `pg_plan_advsr.c:776-781` `[verified-by-code]`.
- **ExecutorEnd re-runs EXPLAIN in JSON to itself** — `NewExplainState` +
  `EXPLAIN_FORMAT_JSON` + `pg_plan_advsr_ExplainPrintPlan`
  (`pg_plan_advsr.c:1214-1242`) `[verified-by-code]`.
- **Actual rows = `instrument->ntuples / nloops`** after a forced
  `InstrEndLoop` (`pg_plan_advsr.c:1944-1951`) `[verified-by-code]`.
- **Hint generation emits `ROWS(rels #actual)`** into the join branch
  (`pg_plan_advsr.c:2026`) `[verified-by-code]`.
- **Writes into pg_hint_plan's `hint_plan.hints` table directly**, scanning its
  `hints_norm_and_app` index (`pg_plan_advsr.c:549-593,651-687`)
  `[verified-by-code]`.
- **Own tables written via raw heap**, not SPI/libpq —
  `heap_form_tuple`+`CatalogTupleInsert`+`CommandCounterIncrement`
  (`pg_plan_advsr.c:456-462`) `[verified-by-code]`.
- **`nextval` under an identity switch to the extension owner** —
  `GetUserIdAndSecContext`/`SetUserIdAndSecContext(extensionOwner(), SECURITY_LOCAL_USERID_CHANGE)`
  around `DirectFunctionCall1(nextval_oid,...)` (`pg_plan_advsr.c:373-378`)
  `[verified-by-code]`.
- **`enable_feedback` mutates a sibling's GUCs** —
  `pg_hint_plan.enable_hint_table` / `.debug_print`
  (`pg_plan_advsr.c:797-807`) `[verified-by-code]`.
- **Extended-stats suggestion** (`plan_repo.get_extstat`) is a pure-SQL SRF
  gated on PG14+ and pg_qualstats (`pg_plan_advsr.sql:110-161`,
  `README.md:310-337`) `[verified-by-code]`.

## Links into corpus

- `[[knowledge/ideologies/index_advisor]]`, `[[knowledge/ideologies/plpgsql_check]]`
  — the parasite-on-a-sibling family; pg_plan_advsr is the executor-feedback
  member (index_advisor = planner-cost oracle over hypopg; plpgsql_check =
  runtime resolution of another module's internals).
- `[[knowledge/ideologies/pg_hint_plan]]` — host #1; pg_plan_advsr writes its
  `hint_plan.hints` table and flips its GUCs.
- `[[knowledge/ideologies/pg_qualstats]]` — optional dependency behind the
  extended-statistics suggestion path. (No `pg_store_plans` corpus doc exists as
  of 2026-07-08 — host #2 is un-doc'd.)
- `[[knowledge/ideologies/pg_squeeze]]`, `[[knowledge/ideologies/pg_bulkload]]`
  — the vendored-internal-code pattern (copy code you can't link to);
  pg_plan_advsr does it as a manual two-repo build step.
- `.claude/skills/executor-and-planner/SKILL.md` +
  `[[knowledge/subsystems/executor]]` — the `PlanState`/`Instrumentation` tree
  it reads actuals from.
- `[[knowledge/subsystems/optimizer]]` + `[[knowledge/idioms/cost-units-gucs]]`
  — the cardinality inputs it overrides from outside via `Rows()` hints.
- `[[knowledge/idioms/process-utility-hook-chain]]` — the hook-chaining
  discipline (save-predecessor / call-through) it follows across seven hooks.

## Sources

- `https://raw.githubusercontent.com/ossc-db/pg_plan_advsr/master/README.md`
  @ 2026-07-08 → 200 OK (546 lines).
- `https://raw.githubusercontent.com/ossc-db/pg_plan_advsr/master/pg_plan_advsr.c`
  @ 2026-07-08 → 200 OK (2213 lines).
- `https://raw.githubusercontent.com/ossc-db/pg_plan_advsr/master/pg_plan_advsr--0.1.sql`
  @ 2026-07-08 → 200 OK (168 lines).
- `https://raw.githubusercontent.com/ossc-db/pg_plan_advsr/master/Makefile`
  @ 2026-07-08 → 200 OK (26 lines).
- `https://raw.githubusercontent.com/ossc-db/pg_plan_advsr/master/pg_plan_advsr.control`
  @ 2026-07-08 → 200 OK (4 lines).
- `.../master/pgsp_json.c`, `.../pgsp_json_text.c`, `.../pgsp_json.h`
  @ 2026-07-08 → **404 (expected gap)**: these files are NOT committed to the
  repo; `README.md:388-390` instructs copying them from a pg_store_plans
  checkout at build time. Their divergence significance (vendored-internal-code)
  is established from the README + Makefile `OBJS` + the include comments, not
  from their contents.
- `.../master/.gitmodules` @ 2026-07-08 → 429 (rate-limited; not retried — not
  load-bearing, the copy-at-build model is confirmed by README:388-390).
