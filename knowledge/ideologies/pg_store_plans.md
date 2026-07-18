# pg_store_plans — pg_stat_statements' architecture, retargeted at a heavier payload (whole execution plans)

> Ideology note produced by the `pg-extension-anthropologist` cloud routine.
> Repo: `ossc-db/pg_store_plans` @ branch `master`. All `file:line` cites below
> point into that repo (not `source/`), since this doc characterizes an
> *external* extension's divergence from core idioms. Cites verified against the
> files fetched on 2026-07-17 (see Sources footer). The corpus already carries a
> sibling doc for the thing pg_store_plans is modeled on:
> `[[knowledge/issues/pg_stat_statements]]`.

## Domain & purpose

pg_stat_statements stores a normalized query **text** plus per-query execution
counters, keyed by `(userid, dbid, queryid)`. pg_store_plans is its
**plan-shaped analogue**: it captures the *actual execution plan* a statement
ran (harvested from the `ExecutorEnd` hook as `EXPLAIN (FORMAT JSON)` output),
normalizes and shortens that plan, hashes the normalized form into a `planid`,
and stores it in a bounded shared hash keyed by
`(userid, dbid, queryid, planid)` (`pg_store_plans.c:129-135`)
`[verified-by-code]`. Each entry accumulates the same family of counters
pg_stat_statements keeps — calls, total/min/max/mean time, Welford variance,
shared/local/temp block counters, I/O timings (`pg_store_plans.c:140-172`)
`[verified-by-code]`. The header comment states the intent directly: "Execution
costs are totaled for each distinct plan for each query, and plan and queryid
are kept in a shared hashtable, each record in which is associated with a record
in pg_stat_statements, if any, by the queryid" (`pg_store_plans.c:6-9`)
`[from-comment]`. So a single `queryid` fans out into one entry per *distinct
plan shape* the planner ever chose for it — the feature exists to answer "which
plans is this query getting, and which one is slow?".

The whole extension is a near-verbatim structural clone of
`contrib/pg_stat_statements` — same shmem-hash-plus-external-text-file
architecture, same usage-decay eviction, same dump/reload-on-restart machinery.
The copyright header even retains "Copyright (c) 2008-2025, PostgreSQL Global
Development Group" beside NTT's (`pg_store_plans.c:25-26`) `[from-comment]`. The
interesting reading is therefore not *what it shares* with core
pg_stat_statements but *what it had to add* to fit a fundamentally larger and
variable-sized payload — an entire plan — into the same fixed-shmem model. That
addition is the bespoke plan-JSON normalizer/shortener (`pgsp_json*`), and it is
the central divergence.

## How it hooks into PG

`PG_MODULE_MAGIC` at `pg_store_plans.c:73`. Everything installs from `_PG_init`
(`pg_store_plans.c:410-600`), and only if preloaded — `_PG_init` returns early
unless `process_shared_preload_libraries_in_progress`
(`pg_store_plans.c:421-422`) `[verified-by-code]`, so the extension is
`shared_preload_libraries`-only for its active path.

**Executor + utility hook chain.** It chains all four executor hooks plus
`ProcessUtility`, saving each previous pointer for the ADVANCE-via-prev-hook
idiom (`pg_store_plans.c:220-225` for the saved slots, `:590-599` for the
installs) `[verified-by-code]`:

- `ExecutorStart_hook` → `pgsp_ExecutorStart` (`pg_store_plans.c:591`)
- `ExecutorRun_hook` → `pgsp_ExecutorRun` (`pg_store_plans.c:593`)
- `ExecutorFinish_hook` → `pgsp_ExecutorFinish` (`pg_store_plans.c:595`)
- `ExecutorEnd_hook` → `pgsp_ExecutorEnd` (`pg_store_plans.c:597`)
- `ProcessUtility_hook` → `pgsp_ProcessUtility` (`pg_store_plans.c:599`)

`ExecutorRun`/`ExecutorFinish` do nothing but bump `nested_level` inside a
`PG_TRY`/`PG_CATCH` so nesting depth stays correct on error unwinding
(`pg_store_plans.c:1015-1078`) `[verified-by-code]` — this drives the
top-level-only tracking decision (`nested_level == 0` in `pgsp_enabled`,
`pg_store_plans.c:307-317`). `ExecutorStart` allocates `queryDesc->totaltime` in
the per-query context so total elapsed time is measured
(`pg_store_plans.c:996-1008`), and, when `log_analyze` is on, OR-s
instrumentation flags into `queryDesc->instrument_options`
(`pg_store_plans.c:978-985`) — the same instrumentation-forcing trick
`[[knowledge/ideologies/pg_qualstats]]` uses.

**The capture point is `ExecutorEnd`** (`pgsp_ExecutorEnd`,
`pg_store_plans.c:1083-1155`). It calls `InstrEndLoop`, then, if enabled and the
statement ran at least `min_duration`, builds a fresh `ExplainState`, sets
`es->format = EXPLAIN_FORMAT_JSON`, and calls the core
`ExplainBeginOutput`/`ExplainPrintPlan`/`ExplainEndOutput`
(`pg_store_plans.c:1103-1116`) `[verified-by-code]`. It then rewrites the
outermost `[`…`]` array brackets that `ExplainPrintPlan` emits into `{`…`}`
object braces (`pg_store_plans.c:1122-1124`) — a hack so the plan is a single
JSON object rather than a one-element array — and hands the JSON text to
`pgsp_store` (`pg_store_plans.c:1142-1147`). It reuses the core executor's
EXPLAIN machinery wholesale rather than walking the plan tree itself; see
`.claude/skills/executor-and-planner` for the `ExplainPrintPlan` path.

**shmem request/startup.** `shmem_request_hook` → `pgsp_shmem_request`
(PG ≥ 15; called directly from `_PG_init` on older) which does
`RequestAddinShmemSpace(shared_mem_size())` +
`RequestNamedLWLockTranche("pg_store_plans", 1)`
(`pg_store_plans.c:621-631`). `shmem_startup_hook` → `pgsp_shmem_startup`
allocates the `pgspSharedState` struct and the fixed-size `HTAB`
(`pg_store_plans.c:664-694`) `[verified-by-code]`. The hash is a classic core
`ShmemInitHash` with `HASH_BLOBS` over the `pgspHashKey`, sized to `store_size`
for both initial and max entries (`pg_store_plans.c:691-694`) — not dshash,
not dynahash-in-DSA; the same plain fixed shmem `HTAB` pg_stat_statements uses.
The single tranche LWLock `shared_state->lock` guards hashtable
search/modification (`pg_store_plans.c:203, 671`), and a per-entry `slock_t
mutex` guards only the counters (`pg_store_plans.c:195, 1355-1427`)
`[verified-by-code]`.

**SQL-callable SRF.** `pg_store_plans()` (and versioned `_1_6/_1_7/_1_9/_1_10`
entry points, `pg_store_plans.c:339-343`) is a `SETOF record`
materialize-mode SRF that seq-scans the hash and emits one row per entry
(`pg_store_plans_internal`, `pg_store_plans.c:1502-1777`) `[verified-by-code]`.
On the way out it re-expands the stored short-JSON into the user's chosen
`plan_format` (text/json/yaml/xml) via `pgsp_json_textize`/`_inflate`/`_yamlize`/
`_xmlize` (`pg_store_plans.c:1665-1682`). The SQL wrapper defines the 30-column
view `pg_store_plans`, plus `pg_store_plans_info` (dealloc count + reset time),
`pg_store_plans_reset()`, and standalone conversion functions
(`pg_store_plans--1.10.sql:60-101`, `:7-59`) `[verified-by-code]`.

**GUCs** (`pg_store_plans.c:434-574`) `[verified-by-code]`:
`pg_store_plans.max` (entry cap, default 1000, `PGC_POSTMASTER`, `:434-445`);
`pg_store_plans.max_plan_length` (default 5000, `:447-458`);
`pg_store_plans.plan_storage` (`shmem`/`file`, default **file**, `:460-470`);
`pg_store_plans.track` (`none`/`top`/`all`/`verbose`, default `top`, `:472-482`);
`pg_store_plans.plan_format` (`raw`/`text`/`json`/`yaml`/`xml`, default text,
`:484-494`); `pg_store_plans.min_duration` (`:496-507`);
`pg_store_plans.save` (dump across restart, default true, `:509-518`);
`pg_store_plans.log_analyze`/`log_buffers`/`log_timing`/`log_triggers`/
`log_verbose` (the EXPLAIN-option analogues, `:520-573`). `log_timing` defaults
**true** (`:546`).

## Where it diverges from core idioms

### 1. The payload is a whole plan, not a query string — so it ships a bespoke plan-JSON normalizer + shortener

This is the load-bearing divergence. pg_stat_statements normalizes a *query
string* (jumble the parse tree, replace constants with `$n`) and stores that one
short string. pg_store_plans has to make the same fixed-size-shmem-hash model
swallow an entire `EXPLAIN (FORMAT JSON)` document — kilobytes of nested
objects — per entry, and it has to derive a stable identity from it. It does so
with a hand-written JSON stream transformer, `pgsp_json.c`, that runs the plan
JSON through the core JSON SAX parser (`run_pg_parse_json`) with custom
semantic-action callbacks (`pgsp_json.c:1360-1390`) `[verified-by-code]`. Two
transforms matter:

- **Shorten** (`pgsp_json_shorten`, `pgsp_json.c:1361-1374`): rewrites every
  long EXPLAIN key to a 1–2 character token via a static `word_table` dictionary
  — `"Node Type"`→`"t"`, `"Relation Name"`→`"n"`, `"Hash Cond"`→`"7"`,
  `"Async Capable"`→`"ac"`, and dozens more (`pgsp_json.c:84-192`)
  `[verified-by-code]`. Node-type names are likewise shrunk (`"Result"`→`"a"`,
  `"ModifyTable"`→`"b"`, `pgsp_json.c:194-198`). This is the mechanism that lets
  a full plan fit under `max_plan_length` (default 5000 bytes,
  `pg_store_plans.c:88, 447-458`): the *stored* form is the shortened JSON
  (`plan_len = strlen(shorten_plan)`, `pg_store_plans.c:1279`), and the SRF
  inflates it back on read (`pg_store_plans.c:1665-1682`). Core has no analogue
  — it never needs to compress its payload because a query string is already
  minimal.

- **Normalize** (`pgsp_json_normalize`, `pgsp_json.c:1376-1390`): produces the
  *identity* form used for hashing. The `word_table` rows carry a boolean flag
  (5th field) marking which properties survive normalization; everything after
  the `/* Values of these properties are ignored on normalization */` divider —
  costs, row estimates, widths, actual times, actual rows, loops, buffer counts,
  hash batches, sort space — is set `false` and dropped
  (`pgsp_json.c:131-192`) `[verified-by-code]`. The header comment states the
  policy: plans are fingerprinted "with constants and unstable values such as
  rows, width, loops ignored" (`pg_store_plans.c:19-22`) `[from-comment]`. So
  two runs of the same query that produced the *same plan shape* but different
  actual-row counts collapse to one `planid`, while a genuinely different plan
  (different join order, different index) gets a new one.

Expression fields inside the plan (`Output`, `Filter`, `Hash Cond`, `Index
Cond`, `Sort Key`, …) route through `conv_expression`, which calls the
extension's own SQL scanner-based `normalize_expr` to mask constants and upcase
keywords using the real core lexer (`normalize_expr`, `pgsp_json.c:504-613`;
`OPCHARS`/`IS_CONST` machinery, `:436-489`) `[verified-by-code]`. That is a
second, expression-level normalizer nested inside the plan-level one — a
scanner-driven query-text normalizer re-implemented because the extension must
normalize the SQL fragments *embedded in* an EXPLAIN plan, which core's jumble
machinery never exposes. Cross-ref `.claude/skills/executor-and-planner`
(EXPLAIN expression deparse) and `[[knowledge/issues/pg_stat_statements]]` (the
constant-masking idea it mirrors).

### 2. `planid` — a second hash dimension core's key never has

pg_stat_statements keys on `(userid, dbid, queryid)`. pg_store_plans adds a
fourth key column, `planid`, computed as `hash_any` over the *normalized* plan
JSON (`pg_store_plans.c:1281-1282`, key struct `:129-135`) `[verified-by-code]`.
The `queryid` itself is taken from core (`queryDesc->plannedstmt->queryId`,
`pg_store_plans.c:1126`); on PG ≥ 14 the extension calls `EnableQueryId()` in
`_PG_init` so core computes it (`pg_store_plans.c:423-429`), and asserts it is
present at store time (`pg_store_plans.c:1139`). On pre-14 it falls back to its
*own* `hash_query` — `pstrdup` + `normalize_expr` + `hash_any` over the source
text (`pg_store_plans.c:1224-1239`, called at `:1136-1137`) — precisely because
old cores didn't expose a query id. Note the deliberate choice to keep the
internal id `uint32` even though core widened `queryId` to 64-bit: the comment
argues the *combination* of query-hash and plan-hash restores enough resolution
(`pg_store_plans.c:1211-1223`) `[from-comment]`. Storing multiple plan entries
per query is the whole point, and it is exactly what a query-text store cannot
express.

### 3. Two plan-storage backends selectable at load: external file *or* inline-in-shmem

pg_stat_statements always keeps its variable-length payload (query text) in an
external file (`pgss_query_texts.stat`) referenced by `(query_offset, query_len)`
in each shmem entry — never inline, because query text is unbounded. pg_store_plans
inherits that external-file machinery *verbatim* — `PGSP_TEXT_FILE`
(`pg_store_plans.c:77`), `ptext_store`/`ptext_load_file`/`ptext_fetch`
(`pg_store_plans.c:2000-2194`), `need_gc_ptexts`/`gc_ptexts` in-place compaction
(`pg_store_plans.c:2201-2409`), `plan_offset`/`plan_len` in the entry
(`pg_store_plans.c:192-193`) `[verified-by-code]` — but then adds a *second*
option core doesn't have: `plan_storage = shmem`, which appends `max_plan_len`
bytes directly to each hash entry and stores the plan inline
(`SHMEM_PLAN_PTR(ent)`, `pg_store_plans.c:319`; entrysize grows by
`max_plan_len` at `:689-690` and `:1833-1834`; inline copy at `:1339-1340` and
`:816-817`) `[verified-by-code]`. Because a shortened plan is *bounded* (capped
at `max_plan_length`) in a way a query string is not, inlining becomes feasible
— so the extension offers it as a lock-simpler, GC-free alternative. The default
stays `file` (`pg_store_plans.c:294, 464`). This dual-backend design (chosen at
postmaster start, `PGC_POSTMASTER`) is a direct consequence of the payload being
bounded-after-shortening; it is an option core never needed to invent. Cross-ref
`.claude/skills/pgstat-framework` (shared-stat storage patterns) and
`[[knowledge/issues/pg_stat_statements]]` (the external-text-file original).

### 4. Eviction, dump/reload, and locking are copied from pg_stat_statements almost line-for-line

Where core and this extension *don't* diverge is instructive: the usage-decay
eviction (`entry_dealloc`, sort by `usage`, drop `USAGE_DEALLOC_PERCENT` = 5%,
decay survivors by `USAGE_DECREASE_FACTOR` = 0.99, sticky entries by 0.50,
`pg_store_plans.c:95-97, 1912-1982`), the "sticky" pending-entry trick
(`pg_store_plans.c:1358-1363, 1847-1878`), the median-usage tracking
(`cur_median_usage`, `:1955-1957`), Welford variance (`:1375-1391`), the
shared→exclusive lock escalation around text writes
(`pg_store_plans.c:1293-1346`), and the dump-to-`global/pg_store_plans.stat`-on-
shutdown / reload-on-startup cycle (`pgsp_shmem_shutdown` `:876-969`,
loader in `pgsp_shmem_startup` `:738-835`) are all recognizably the
pg_stat_statements code with `query`→`plan` renames `[verified-by-code]`. The
file magic even encodes the PG major version so a version bump silently
invalidates the dump (`PGSP_PG_MAJOR_VERSION`, `pg_store_plans.c:83-84`,
checked at `:763-765`) `[verified-by-code]`. The divergence is not in *this*
machinery — it's that all of it now protects a plan-shaped payload, which is why
the shorten step (§1) is load-bearing: without it the 5000-byte default cap and
the external-file GC heuristics (which assume ~512 bytes/entry,
`pg_store_plans.c:2217-2219`) would be swamped by raw multi-kilobyte plans.

### 5. It suppresses its own recursion during `CREATE/ALTER EXTENSION`

`pgsp_ProcessUtility` sets a `force_disabled` flag around
`T_CreateExtensionStmt`/`T_AlterExtensionStmt` execution so that plans run *by
the extension's own install scripts* aren't captured
(`pg_store_plans.c:1169-1208`) `[verified-by-code]`, restoring it in both the
`PG_TRY` success and `PG_CATCH` paths. A small but pointed self-awareness idiom
that core, having no hooks to recurse through, never needs.

## Notable design decisions (cited)

- **Capture is gated on duration and level, not sampled.** Unlike
  `[[knowledge/ideologies/pg_qualstats]]`'s probabilistic sampling,
  pg_store_plans records every statement that clears `min_duration` and matches
  `track` level; the enable predicate is purely
  `!force_disabled && level && queryid != 0` (`pg_store_plans.c:307-317`,
  duration gate `:1094-1097`) `[verified-by-code]`.
- **`log_analyze` forces EXPLAIN-grade instrumentation from the hook.** When set,
  `ExecutorStart` OR-s `INSTRUMENT_TIMER`/`INSTRUMENT_ROWS`/`INSTRUMENT_BUFFERS`
  into `instrument_options` for non-parallel-worker, non-EXPLAIN-only queries
  (`pg_store_plans.c:978-985`), so stored plans carry actual row/time/buffer
  numbers — at real runtime cost. Same co-opting-the-instrumentation-budget move
  documented for pg_qualstats.
- **Plans can be re-rendered into any EXPLAIN format on read.** The stored form
  is always shortened JSON; `plan_format` chooses text/json/yaml/xml at SRF time
  via the inverse converters (`pg_store_plans.c:1665-1682`,
  `pgsp_json_yamlize`/`_xmlize` `pgsp_json.c:1418-1499`). The dictionary's
  `textname`/`longname` columns drive the text vs JSON re-expansion
  (`converter_core`, `pgsp_json.c:373-405`) `[verified-by-code]`.
- **Trigger stats are optionally appended to the captured plan.** With
  `log_triggers`, `pgspExplainTriggers` walks result/routing/target relations and
  hand-emits `Triggers` JSON groups into the same `ExplainState` buffer
  (`pgsp_explain.c:65-192`, invoked `pg_store_plans.c:1114-1115`) — a chunk of
  core `explain.c` copied out and privately maintained (`pgsp_explain.c:1-11`
  header) `[from-comment]`.
- **Reader privilege model matches core.** Non-privileged callers see their own
  entries; `pg_read_all_stats` members see all; others get NULL ids and
  `<insufficient privilege>` for the plan text (`pg_store_plans.c:1512, 1626-1700`)
  `[verified-by-code]`.
- **`relocatable = true`**, default version `1.10`
  (`pg_store_plans.control:1-5`) `[verified-by-code]`. The C source carries a
  version enum `PGSP_V1_5…PGSP_V1_10` mapping to differing SRF column counts
  (`pg_store_plans.c:111-119, 1451-1457`) so old `CREATE EXTENSION` versions keep
  working against a new `.so`.
- **`OBJS` is four TUs**: `pg_store_plans.o pgsp_json.o pgsp_json_text.o
  pgsp_explain.o` (`Makefile:5`) — the JSON transform layer (`pgsp_json*`, ~2500
  lines across two files) is roughly as large as the core store logic itself,
  quantifying how much of the extension exists just to fit plans into the model.

## Links into corpus

- `[[knowledge/issues/pg_stat_statements]]` — the sibling the whole extension is
  cloned from; read it for the external-text-file, usage-decay eviction, sticky
  entries, and dump/reload machinery that pg_store_plans copies verbatim. The
  divergences above are exactly the delta needed to swap a query string for a
  plan.
- `[[knowledge/ideologies/pg_qualstats]]` — the other executor-hook observer in
  the corpus; shares the `instrument_options`-forcing trick and the
  bounded-shmem-hash-with-eviction shape, but samples probabilistically and keys
  on quals rather than plans.
- `[[knowledge/ideologies/pg_show_plans]]`,
  `[[knowledge/ideologies/pg_stat_monitor]]`,
  `[[knowledge/ideologies/pg_tracing]]` — neighboring plan/statement-observability
  extensions for comparison.
- `.claude/skills/executor-and-planner` — the `ExecutorStart`/`End` hook points,
  `queryDesc->totaltime`/`instrument_options`, and the
  `ExplainBeginOutput`/`ExplainPrintPlan` path pg_store_plans drives to get its
  JSON plan.
- `.claude/skills/pgstat-framework` — shared-memory statistics storage patterns;
  pg_store_plans predates and sidesteps the pgstat DSA framework, using a
  classic fixed `ShmemInitHash` + external stat file instead.

## Sources

Fetched 2026-07-17 (branch `master`). GitHub search/API was blocked; all files
retrieved via `raw.githubusercontent.com`.

- `.../ossc-db/pg_store_plans/master/Makefile` → HTTP 200
  (`OBJS = pg_store_plans.o pgsp_json.o pgsp_json_text.o pgsp_explain.o`;
  `DATA = pg_store_plans--1.10.sql`).
- `.../pg_store_plans.control` → HTTP 200 (4 lines; `default_version = '1.10'`,
  `relocatable = true`).
- `.../pg_store_plans.c` → HTTP 200 (2537 lines). Hook chain, shmem hash,
  `pgsp_store`, eviction, external-text file, SRF — all cites `[verified-by-code]`.
- `.../pgsp_json.c` → HTTP 200 (1499 lines). `word_table` shorten/normalize
  dictionary, `converter_core`, `normalize_expr`, `pgsp_json_shorten/normalize/
  inflate/yamlize/xmlize` — all `[verified-by-code]`.
- `.../pgsp_json.h` → HTTP 200 (22 lines).
- `.../pgsp_json_text.c` → HTTP 200 (1073 lines; `pgsp_json_textize` entry at
  `:1032`, text re-render path — read for entry point, not fully derived).
- `.../pgsp_explain.c` → HTTP 200 (235 lines). `pgspExplainTriggers` +
  copied-from-`explain.c` trigger reporting.
- `.../pgsp_explain.h` → HTTP 200 (19 lines).
- `.../pg_store_plans--1.10.sql` → HTTP 200 (105 lines). SRF signature (30 cols),
  views, GRANT/REVOKE.

404 gaps (probed, not present at repo root on `master`): `README.md`,
`pg_store_plans.h`, `pg_store_plans--1.5.sql`, `--1.6.sql`, `--1.7.sql`,
`--1.8.sql` (the shipped DATA is `--1.10.sql` only; older versions live under
tags/other paths not fetched). `pgsp_json_int.h`, `pgsp_json_text.h`, and
`pgsp_token_types.h` are `#include`d by `pgsp_json.c` but were not separately
fetched; the `word_table`/`SETTER` mechanics they declare are inferred from
usage in `pgsp_json.c` and tagged accordingly. All `pg_store_plans.c` and
`pgsp_json.c` cites are `[verified-by-code]` against the fetched files.
