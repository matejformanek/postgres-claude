# pg_ivm — incremental matview maintenance that vendors and forks three core backend .c files, then drives delta SQL through AFTER-trigger transition tables and SPI

> Ideology note produced by the `pg-extension-anthropologist` cloud routine.
> Repo: `sraoss/pg_ivm` @ branch `main`. All `file:line` cites point into that
> repo (not `source/`). Cites verified against files fetched on 2026-06-12 (see
> Sources footer). Read alongside `[[knowledge/ideologies/pg_squeeze]]` (the
> other corpus extension that copies core static functions),
> `[[knowledge/architecture/query-lifecycle]]`, `[[knowledge/idioms/spi]]`, and
> the core `REFRESH MATERIALIZED VIEW` path (`source/src/backend/commands/matview.c`).

## Domain & purpose

pg_ivm implements **Incremental View Maintenance (IVM)**: instead of fully
recomputing a materialized view with `REFRESH MATERIALIZED VIEW`, it keeps an
"IMMV" (Incrementally Maintained Materialized View) up to date by computing
**deltas** on base-table changes. "IVM can update materialized views more
efficiently than recomputation when only small parts of the view are changed"
(`README.md`) `[from-README]`. An IMMV is just a regular table populated from a
view query, plus auto-installed triggers; on every base-table DML the triggers
fire and apply the row-level change to the IMMV table (`README.md`)
`[from-README]`. Supported constructs: inner/outer joins, DISTINCT, the built-in
aggregates `count/sum/avg/min/max`, simple `FROM`-subqueries, `EXISTS`
subqueries, simple CTEs; **unsupported**: window functions, `HAVING`,
`ORDER BY`, `LIMIT/OFFSET`, set ops, `DISTINCT ON`, user-defined aggregates
(`README.md`) `[from-README]`.

The reason to document it: pg_ivm is the corpus's most aggressive example of an
extension that **reaches inside the backend by copying core source files**
(`createas.c`, `matview.c`, `ruleutils.c`) and patching them, rather than going
through public extension APIs — a deliberate divergence with real
maintenance/ABI consequences.

## How it hooks into PG

`_PG_init` is small and installs **no planner/executor/ProcessUtility hook**. It
registers transaction + subtransaction callbacks and chains the object-access
hook (`pg_ivm.c:86-92`) `[verified-by-code]`:

```c
RegisterXactCallback(IvmXactCallback, NULL);
RegisterSubXactCallback(IvmSubXactCallback, NULL);
PrevObjectAccessHook = object_access_hook;
object_access_hook = PgIvmObjectAccessHook;
```

The object-access hook exists so that `DROP`ping an IMMV cleans up its
bookkeeping row: on relation drop it scans the catalog by `immvrelid` and
`CatalogTupleDelete()`s the entry (`pg_ivm.c:333-369`) `[verified-by-code]`.

**SQL-callable surface** (`PG_FUNCTION_INFO_V1`, `pg_ivm.c:49-52`):
`create_immv(text,text)`, `refresh_immv`, `IVM_prevent_immv_change`,
`get_immv_def` `[verified-by-code]`. The header also exports the trigger
entry points `IVM_immediate_before` and `ivm_visible_in_prestate`
(`pg_ivm.h`) `[verified-by-code]`.

**The bookkeeping catalog** is a real table `pg_ivm_immv` in `pg_catalog`
(the extension is `schema = pg_catalog`, `relocatable = false`,
`pg_ivm.control`) `[verified-by-code]`, with 4 attributes
(`Natts_pg_ivm_immv 4`; `immvrelid`, the view def, an ispopulated flag, and
`lastivmupdate`) (`pg_ivm.h`) `[verified-by-code]`.

**IMMV creation** (`ExecCreateImmv`, `createas.c:296-356`) `[verified-by-code]`:
validates the query (`check_ivm_restriction`), rewrites it
(`rewriteQueryForIMMV`), creates the table with no data (`create_immv_nodata`),
populates via `RefreshImmvByOid` if requested, builds a unique index where
possible (`CreateIndexOnIMMV`), and installs the **change-prevention trigger**
(`CreateChangePreventTrigger`).

**Two trigger families.** (a) BEFORE statement triggers on the IMMV *table
itself* that call `IVM_prevent_immv_change` to block direct user DML against an
IMMV (`pg_ivm.c:238-275`, `TRIGGER_TYPE_BEFORE`, `row = false`)
`[verified-by-code]`. (b) The actual maintenance triggers: AFTER triggers on
each **base table**, installed by `CreateIvmTriggersOnBaseTables` /
`CreateIvmTrigger` (`createas.c:662-700, 723-829`), which attach **transition
tables** named `__ivm_newtable`/`__ivm_oldtable` for INSERT/UPDATE/DELETE
(`createas.c:777-795`) `[verified-by-code]`:

```c
TriggerTransition *n = makeNode(TriggerTransition);
n->name = "__ivm_newtable"; n->isNew = true; n->isTable = true;
```

The AFTER trigger fires `IVM_immediate_maintenance`; a paired BEFORE trigger
fires `IVM_immediate_before` to grab a pre-state snapshot and lock
(`matview.c:1096-1187, 1195-1472`) `[verified-by-code]`.

Cross-ref `[[knowledge/idioms/spi]]`, `[[knowledge/idioms/node-types-and-lists]]`
(`makeNode`/`lappend` building the transition-rel list),
`.claude/skills/fmgr-and-spi/SKILL.md`,
`.claude/skills/executor-and-planner/SKILL.md`,
`.claude/skills/extension-development/SKILL.md`.

## Where it diverges from core idioms

### 1. It VENDORS AND FORKS core backend `.c` files and patches them

This is the defining ideology. Three files are copies of PostgreSQL backend
sources, lightly renamed and modified:

- `createas.c` — derived from `src/backend/commands/createas.c`; header carries
  "Portions Copyright (c) 1996-2022, PostgreSQL Global Development Group"
  (`createas.c:1-10`) `[verified-by-code]`.
- `matview.c` — derived from `src/backend/commands/matview.c`, same dual
  copyright (`matview.c:1-10`) `[verified-by-code]`.
- `ruleutils.c` — derived from `src/backend/utils/adt/ruleutils.c`
  (`ruleutils.c:1-10`) `[verified-by-code]`; it exists because the deparse
  entry points pg_ivm needs to reconstruct a view's query text are **`static`**
  in core and not exported.

The fragility this creates is real and explicit:

- **Exact-PG-version coupling.** `ruleutils.c` is gated by `PG_VERSION_NUM`:
  PG15+ can use the public `pg_get_querydef()`, but PG13/14 require copying the
  `static get_query_def()` out of core (`ruleutils.c`, version-gating)
  `[verified-by-code]`. The repo even carried `ruleutils_13.c`/`ruleutils_14.c`
  variants in its tree (`tree`) `[verified-by-code]`, though the shipped
  Makefile compiles a single `ruleutils.o` with internal `#if` gating
  (`Makefile`) `[verified-by-code]`. Every new major PG release risks the
  copied static functions drifting — pg_ivm must re-vendor and re-diff.
- **ABI / internal-API coupling.** These files call backend internals
  (`refresh_by_heap_swap`, `table_tuple_fetch_row_version`, `RestrictSearchPath`)
  that are not part of any stability contract; a refactor upstream silently
  breaks the build.

This is the same anti-pattern as `[[knowledge/ideologies/pg_squeeze]]`, which
copies `swap_relation_files` out of `cluster.c`. pg_ivm copies *three whole
files* — a strictly larger surface. `[verified-by-code]` for the copying;
`[inferred]` for the maintenance-burden characterization.

### 2. Trigger-driven delta maintenance instead of core's full REFRESH

Core only offers `REFRESH MATERIALIZED VIEW` — recompute the whole query, swap
heaps. pg_ivm keeps that path (`RefreshImmvByOid` builds a transient heap, runs
the rewritten query, and `refresh_by_heap_swap`s it in, `matview.c:194-298`)
`[verified-by-code]` for `refresh_immv`, but its *normal* operation never calls
it. Instead, AFTER triggers compute and apply only the changed rows
(`apply_delta`, `matview.c:2236-2529`) `[verified-by-code]`. This inverts the
matview cost model: cheap when the change set is small, at the price of standing
triggers on every base table and a per-statement maintenance transaction.

### 3. Transition tables (ephemeral named tuplestores) carry the before/after deltas

The delta source is PG's AFTER-trigger **transition table** feature
(`REFERENCING OLD/NEW TABLE AS …`). `IVM_immediate_maintenance` copies
`trigdata->tg_oldtable`/`tg_newtable` into per-table tuplestore lists keyed by
modified-table OID in an `MV_TriggerTable` hash entry (`matview.c:1267-1283`)
`[verified-by-code]`:

```c
table->old_tuplestores = lappend(table->old_tuplestores, tuplestore_copy(...));
table->new_tuplestores = lappend(table->new_tuplestores, tuplestore_copy(...));
```

Those tuplestores are then **registered as ephemeral named relations (ENRs)**
(`OLD_DELTA_ENRNAME`/`NEW_DELTA_ENRNAME`) so SPI delta queries can reference
them as tables (`matview.c:2299-2361`) `[verified-by-code]`. This is a heavy,
idiomatic-but-rare use of the ENR machinery most extensions never touch.

### 4. The counting algorithm: a hidden `__ivm_count__` column

To make INSERT/DELETE of duplicate rows reversible, `rewriteQueryForIMMV`
appends a hidden `count(*)` target named `__ivm_count__` whenever the view has
`DISTINCT` or aggregates (`createas.c:455-471`, also `matview.c:1920-1939`)
`[verified-by-code]`. For DISTINCT this column holds each tuple's multiplicity;
a view row is deleted iff its multiplicity drops to zero, inserted only if not
already present (`README.md`) `[from-README]`. Aggregates get further hidden
columns: `avg` is maintained via `__ivm_count_avg__` and `__ivm_sum_avg__`
(`README.md`) `[from-README]`, with per-aggregate SET-clause builders
(`append_set_clause_for_count/sum/avg/minmax`, `matview.c:2369-2535`)
`[verified-by-code]`. `min/max` are the hard case: a delete that removes the
current extremum forces a re-scan (`get_null_condition_string` /
`CASE WHEN … THEN NULL` recompute, `matview.c:2510-2535`) `[verified-by-code]`.
README warns `sum`/`avg` over `float4`/`float8` is **unsafe** (non-associative
FP); use `numeric` (`README.md`) `[from-README]`.

### 5. Delta queries run through SPI, with a depth-counter recursion guard

`apply_delta` opens an SPI connection and applies the old-delta and new-delta as
SQL `UPDATE`/`DELETE`/`INSERT` against the IMMV table
(`SPI_connect`/`SPI_register_relation`/`SPI_finish`, `matview.c:2289-2375`)
`[verified-by-code]`. Because those SPI statements themselves modify the IMMV
(and could in principle touch base tables), pg_ivm guards against re-entrant
trigger firing with a static depth counter rather than a hook flag:
`immv_maintenance_depth`, toggled by `OpenImmvIncrementalMaintenance` /
`CloseImmvIncrementalMaintenance`, queried by `ImmvIncrementalMaintenanceIsEnabled`
(`matview.c:90-91, 1365-1373`) `[verified-by-code]`.

A second SPI subtlety: computing deltas for joins/aggregates requires re-scanning
base tables **as of the pre-modification snapshot**. pg_ivm registers
`ivm_visible_in_prestate(tableoid, ctid, matviewOid)`, which fetches the row
version against the snapshot saved in `IVM_immediate_before` via
`table_tuple_fetch_row_version(..., entry->snapshot, ...)`
(`matview.c:1354-1376`) `[verified-by-code]` — i.e. it threads a *custom
visibility predicate* into delta SQL, which core's snapshot model does not
expose to extensions.

### 6. Concurrency / locking caveats the README admits

`IVM_immediate_before` takes `ExclusiveLock` on the IMMV when the view is
multi-table (or uses DISTINCT/GROUP BY), else `RowExclusiveLock`
(`matview.c:1131-1142`, README's single-table-INSERT exception)
`[verified-by-code]` / `[from-README]`. Under `REPEATABLE READ`/`SERIALIZABLE`
it takes the lock *conditionally* and `ereport(ERROR, ERRCODE_LOCK_NOT_AVAILABLE)`
on failure (`matview.c:1131-1142`) `[verified-by-code]`. It also detects a
concurrent committed incremental update by checking the IMMV's last-update xid
against the snapshot and raising `ERRCODE_T_R_SERIALIZATION_FAILURE`
(`getLastUpdateXid` + `XidInMVCCSnapshot`, `matview.c:1159-1170`)
`[verified-by-code]`. README is candid: under REPEATABLE READ/SERIALIZABLE this
"could lead to an inconsistent state of the view … an error is raised to prevent
anomalies" (`README.md`) `[from-README]`.

## Notable design decisions (cited)

- **PG17+ `search_path` hardening.** During maintenance, pg_ivm calls
  `RestrictSearchPath()` (PG17+) before running SPI/deparse so function
  resolution is confined to `pg_catalog, pg_temp`
  (`matview.c:243-246, 1201-1204`) `[verified-by-code]`; README confirms the
  temporary `search_path` change (`README.md`) `[from-README]`. A direct
  response to the search-path-injection class of CVEs in
  SECURITY DEFINER-ish contexts. `[inferred]` for the CVE motivation.
- **Extension installs into `pg_catalog`, non-relocatable** (`pg_ivm.control`)
  `[verified-by-code]` — so its functions and the `pg_ivm_immv` catalog look and
  resolve like built-ins; reinforces the "we are pretending to be core" stance.
- **DISTINCT is rewritten to GROUP BY, EXISTS to lateral subqueries** inside
  `rewriteQueryForIMMV` (`createas.c:388, 418`) `[verified-by-code]` so a single
  counting/aggregate maintenance path covers both.
- **Base tables must be plain tables** — no views, matviews, partitioned tables,
  partitions, inheritance parents, or foreign tables (`README.md`)
  `[from-README]`, because the trigger+transition-table mechanism needs simple,
  directly-triggerable relations.
- **Wide major-version support (PG13–18)** is purchased entirely with
  `#if PG_VERSION_NUM` gating and the per-version vendored deparse code
  (`ruleutils.c`, `Makefile`) `[verified-by-code]`.

## Links into corpus

- `[[knowledge/ideologies/pg_squeeze]]` — closest parallel: copies the `static`
  `swap_relation_files` out of `cluster.c`. pg_ivm does the same move at file
  scale (three whole forked files), so both share the "core-internal symbol I
  can't reach, so I'll re-vendor it" fragility.
- `[[knowledge/ideologies/timescaledb]]` — continuous aggregates are a *different*
  take on incremental matview maintenance (background materialization +
  invalidation watermarks, not synchronous AFTER-trigger deltas). Compare:
  pg_ivm is immediate/synchronous and per-statement; TimescaleDB is deferred and
  bucketed.
- `[[knowledge/idioms/spi]]` — delta application via `SPI_connect`/
  `SPI_register_relation`/`SPI_finish`, plus the ENR registration of transition
  tuplestores.
- `[[knowledge/idioms/node-types-and-lists]]` — `makeNode(TriggerTransition)`,
  `makeTargetEntry`, `lappend` building the rewritten query and trigger spec.
- `[[knowledge/architecture/query-lifecycle]]` — pg_ivm forks the
  CREATE-TABLE-AS and REFRESH-MATVIEW slices of that lifecycle and bolts a delta
  path onto the trigger phase.
- `.claude/skills/fmgr-and-spi/SKILL.md`,
  `.claude/skills/executor-and-planner/SKILL.md`,
  `.claude/skills/extension-development/SKILL.md`.

## Anthropology takeaway

pg_ivm is the corpus's strongest case of an extension that **declines the
extension contract and copies the backend instead**. Where uuidv47 reuses core
via clean fmgr composition (`DirectFunctionCall1`), and most extensions chain a
hook, pg_ivm vendors `createas.c`, `matview.c`, and `ruleutils.c` because the
functions it needs (matview heap-swap plumbing, query deparse) are `static` and
unexported. The payoff is a genuinely sophisticated feature — synchronous
incremental maintenance with a counting algorithm, transition-table ENRs, and a
pre-state visibility predicate — that core itself has never shipped. The cost is
a permanent maintenance tax: every major PG release can break the copied static
code, hence the dense `#if PG_VERSION_NUM` lattice and per-version deparse files.
For a `knowledge/issues` note, pg_ivm is the textbook argument for *why core
should export more stable internal APIs* (matview swap, ruleutils deparse): the
absence of those exports is exactly what forces the fork. Its concurrency story
is also a useful cautionary tag — incremental maintenance is only consistent
under READ COMMITTED with an ExclusiveLock; under REPEATABLE READ/SERIALIZABLE
it must *refuse* (serialization error) rather than risk an anomalous view, which
is an honest but sharp limitation worth surfacing to anyone evaluating IVM for
high-concurrency write paths.

## Sources

Fetched 2026-06-12 (branch `main`). The GitHub git-trees API returned HTTP 403
to WebFetch and the GitHub MCP was scoped to a different repo, so the tree was
recovered from the rendered `tree/main` HTML page and from raw file fetches.

- `https://api.github.com/repos/sraoss/pg_ivm/git/trees/main?recursive=1`
  @ 2026-06-12 → HTTP 403 (Forbidden; substituted by the HTML tree page below).
- `https://github.com/sraoss/pg_ivm/tree/main`
  @ 2026-06-12 → HTTP 200 (root file listing: `createas.c`, `matview.c`,
  `pg_ivm.c`, `pg_ivm.h`, `ruleutils.c`, `ruleutils_13.c`, `ruleutils_14.c`,
  `subselect.c`, `pg_ivm.control`, `Makefile`, `meson.build`, 16 `*.sql`,
  `README.md`).
- `https://raw.githubusercontent.com/sraoss/pg_ivm/main/README.md`
  @ 2026-06-12 → HTTP 200 (features, maintenance model, `__ivm_count__`,
  aggregate/DISTINCT rules, locking/isolation caveats — read for `[from-README]`).
- `.../main/pg_ivm.c` @ 2026-06-12 → HTTP 200 (deep-read: `_PG_init`, hooks,
  SQL functions, change-prevention triggers, `pg_ivm_immv` access).
- `.../main/pg_ivm.h` @ 2026-06-12 → HTTP 200 (catalog attr macros, prototypes,
  version-coupling note — skimmed).
- `.../main/createas.c` @ 2026-06-12 → HTTP 200 (deep-read: `ExecCreateImmv`,
  `rewriteQueryForIMMV`, `CreateIvmTrigger` transition-table install).
- `.../main/matview.c` @ 2026-06-12 → HTTP 200 (deep-read across two fetches:
  trigger fns, `apply_delta` + SPI, counting/aggregate SET-clause builders,
  locking/isolation, recursion guard, `RestrictSearchPath`,
  `ivm_visible_in_prestate`, `RefreshImmvByOid`).
- `.../main/ruleutils.c` @ 2026-06-12 → HTTP 200 (header + version-gating only;
  the deparse body was not line-audited — `[verified-by-code]` cites for this
  file cover the header comment and the `#if PG_VERSION_NUM` structure, not the
  reproduced deparse logic).
- `.../main/pg_ivm.control` @ 2026-06-12 → HTTP 200 (full verbatim).
- `.../main/Makefile` @ 2026-06-12 → HTTP 200 (OBJS list, DATA/version files,
  isolation-test gating).

Line numbers come from WebFetch's reading of each raw file and were not
re-confirmed against a local cat-numbered copy; treat ranges as approximate
(±a few lines) but the function names and quoted lines as `[verified-by-code]`.
README-only claims are tagged `[from-README]`; maintenance-burden and CVE-motive
characterizations are `[inferred]`.
