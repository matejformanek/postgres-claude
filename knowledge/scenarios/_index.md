# Scenarios index — pick a playbook

One-line summary per scenario + the decision tree the planner uses to
route from a brainstorm to the right playbook.

See `README.md` for the layer's purpose, template, and refresh rules.

## The full set (sequenced by natural dependency)

### Catalog basics (foundation — most other scenarios depend on these)

| # | Slug | Trigger |
|---|---|---|
| 1 | [bump-catversion](bump-catversion.md) | When/why to bump `CATALOG_VERSION_NO`, initdb invalidation, BKI regen. |
| 2 | [add-new-builtin-function](add-new-builtin-function.md) | New built-in SQL-callable C function: `pg_proc.dat` + `utils/adt` + tests. |
| 3 | [add-new-data-type](add-new-data-type.md) | New built-in scalar type — the 12-14-file sweep (type/funcs/operators/casts/opclass). |
| 4 | [add-new-operator-class](add-new-operator-class.md) | New `pg_opclass` + strategies + support functions for an existing AM (btree/hash/gist/gin/spgist/brin). |
| 5 | [add-new-operator](add-new-operator.md) | New `pg_operator.dat` entry with commutator / negator / restrict / join. |
| 6 | [add-new-cast](add-new-cast.md) | New `pg_cast.dat` entry — implicit vs assignment vs explicit. |
| 7 | [add-new-aggregate-function](add-new-aggregate-function.md) | New `pg_aggregate.dat` + sfunc / finalfunc / serial / deserial / combine. |
| 8 | [add-new-error-code](add-new-error-code.md) | New SQLSTATE in `errcodes.txt` + plpgsql condition + tests. |
| 9 | [add-new-system-catalog-column](add-new-system-catalog-column.md) | Add a column to a system catalog: header `.h` + `.dat` + initdb regen. |
| 10 | [add-new-system-view](add-new-system-view.md) | New view in `system_views.sql` + supporting functions. |

### Parser / grammar

| # | Slug | Trigger |
|---|---|---|
| 11 | [add-new-sql-keyword](add-new-sql-keyword.md) | New keyword: `gram.y` + `kwlist.h` + `parsenodes.h` + `analyze.c` + `psqlscan.l` sync + ecpg `pgc.l` sync. |
| 12 | [add-new-node-type](add-new-node-type.md) | New Node: `parsenodes.h`/`primnodes.h`/`plannodes.h` + `gen_node_support.pl` regen + copy/equal/out/read + walker/mutator. |
| 13 | [add-new-utility-statement](add-new-utility-statement.md) | New `XxxStmt` + `standard_ProcessUtility` dispatch + tab-completion. |

### Executor / planner

| # | Slug | Trigger |
|---|---|---|
| 14 | [add-new-plan-node](add-new-plan-node.md) | New Path + Plan + PlanState + `nodeXxx.c` + `createplan.c` + EXPLAIN + parallel-aware DSM. |
| 15 | [add-new-expression-eval-step](add-new-expression-eval-step.md) | New `execExpr.c` step kind + `ExecInterpExpr` + LLVM JIT mirror. |
| 16 | [add-new-cost-model-knob](add-new-cost-model-knob.md) | New cost constant in `cost.h` + use in `cost_*.c` + GUC if user-tunable. |

### Storage / access methods

| # | Slug | Trigger |
|---|---|---|
| 17 | [add-new-index-am](add-new-index-am.md) | Brand-new index AM: handler + `IndexAmRoutine` + WAL rmgr + opclass + `amapi.h`. |
| 18 | [add-new-table-am](add-new-table-am.md) | Brand-new table AM: handler + `TableAmRoutine` + VM + `tableam.h`. |
| 19 | [add-new-wal-record](add-new-wal-record.md) | New WAL record type or info byte in an existing rmgr + redo + rmgrdesc + `XLOG_PAGE_MAGIC`. |
| 20 | [add-new-buffer-strategy](add-new-buffer-strategy.md) | New `BufferAccessStrategy` ring class + freelist policy. |

### Infrastructure / runtime

| # | Slug | Trigger |
|---|---|---|
| 21 | [add-new-guc](add-new-guc.md) | New GUC: `DefineCustom*Variable` (or built-in `static struct config_*`) + check/assign/show + sample.conf + tests. |
| 22 | [add-startup-hook](add-startup-hook.md) | Hook point in PostmasterMain / PostgresMain / InitPostgres lifecycle (the "main ring" question). |
| 23 | [add-new-bgworker](add-new-bgworker.md) | Background worker: `Register{Static,Dynamic}BackgroundWorker` + worker main + preload. |
| 24 | [add-new-hook](add-new-hook.md) | New extension hook in `ProcessUtility_hook` / `planner_hook` / `ExecutorStart_hook` style. |
| 25 | [add-new-lwlock-tranche](add-new-lwlock-tranche.md) | New LWLock tranche: `lwlocklist.h` (built-in) or `RequestNamedLWLockTranche` (extension) + `wait_event_names.txt`. |
| 26 | [add-new-shared-memory-region](add-new-shared-memory-region.md) | New shmem area: `RequestAddinShmemSpace` + `shmem_request_hook` + `shmem_startup_hook`. |
| 27 | [add-new-pg-stat-view](add-new-pg-stat-view.md) | New `pg_stat_*` view: `pgstat_*.c` + `system_views.sql` + `pg_proc.dat`. |

### Replication / wire / extensions

| # | Slug | Trigger |
|---|---|---|
| 28 | [add-new-protocol-message](add-new-protocol-message.md) | New libpq protocol message type: frontend libpq + backend postmaster/auth + `protocol.sgml`. |
| 29 | [add-new-replication-message](add-new-replication-message.md) | New logical-decoding `output_plugin` callback OR walsender command. |
| 30 | [add-new-extension](add-new-extension.md) | New `contrib/<name>/`: `.control` + `--1.0.sql` + `_PG_init` + Makefile/meson + tests. |
| 31 | [add-new-test-module](add-new-test-module.md) | New `src/test/modules/<name>/`: Makefile + meson + `.c` + `.sql` + expected/ + Cluster.pm TAP. |

## Decision tree — "which scenario do I want?"

Walk the tree top-down. Stop at the first match.

```
Are you adding code that runs in postgres -- the backend?
├─ No → you're either writing user SQL (no scenario) or a client app
│       (no scenario) or a tool in src/bin (no scenario yet).
└─ Yes ↓

What kind of thing are you adding?

├─ A new SQL surface (something a user writes in a SQL statement)
│   ├─ New keyword / grammar production       → #11 add-new-sql-keyword
│   ├─ New utility statement (CREATE / DROP / ALTER something)
│   │                                          → #13 add-new-utility-statement
│   ├─ New built-in function (callable as SQL fn)
│   │                                          → #2  add-new-builtin-function
│   ├─ New aggregate function                  → #7  add-new-aggregate-function
│   ├─ New operator                            → #5  add-new-operator
│   ├─ New cast                                → #6  add-new-cast
│   ├─ New built-in scalar data type           → #3  add-new-data-type
│   ├─ New SQLSTATE / error condition          → #8  add-new-error-code
│   └─ New system view (pg_stat_xxx is its own scenario, #27)
│                                              → #10 add-new-system-view
│
├─ Storage / access path
│   ├─ Brand-new index method                  → #17 add-new-index-am
│   ├─ New opclass for an existing index AM    → #4  add-new-operator-class
│   ├─ Brand-new table AM                      → #18 add-new-table-am
│   ├─ New WAL record kind                     → #19 add-new-wal-record
│   └─ New buffer ring policy                  → #20 add-new-buffer-strategy
│
├─ Planner / executor internals
│   ├─ New plan node (custom scan, etc.)       → #14 add-new-plan-node
│   ├─ New expression-eval step kind           → #15 add-new-expression-eval-step
│   └─ New cost constant                       → #16 add-new-cost-model-knob
│
├─ Runtime / observability
│   ├─ New GUC                                 → #21 add-new-guc
│   ├─ Hook in startup lifecycle               → #22 add-startup-hook
│   ├─ New extension hook (planner_hook etc.)  → #24 add-new-hook
│   ├─ New background worker                   → #23 add-new-bgworker
│   ├─ New LWLock tranche                      → #25 add-new-lwlock-tranche
│   ├─ New shared-memory region                → #26 add-new-shared-memory-region
│   └─ New pg_stat_* view                      → #27 add-new-pg-stat-view
│
├─ Replication / wire
│   ├─ New libpq wire message                  → #28 add-new-protocol-message
│   └─ New logical-decoding message            → #29 add-new-replication-message
│
├─ Catalog plumbing
│   ├─ New column on an existing catalog       → #9  add-new-system-catalog-column
│   └─ Just need to bump CATALOG_VERSION_NO    → #1  bump-catversion
│
└─ Packaging / tests
    ├─ New contrib/ extension                  → #30 add-new-extension
    └─ New src/test/modules/<name>             → #31 add-new-test-module
```

## Composite features

A real-world feature often spans 2-3 scenarios. The planner unions
the checklists; you don't have to pick one. Common compositions:

- **"Add a fully-functional new data type with btree + hash indexing"**
  = #3 (data type) ∪ #4 (op class, btree) ∪ #4 (op class, hash) ∪ #5
  (comparison ops) ∪ #6 (text→type cast).
- **"Add a new index method that's user-pluggable like a contrib"**
  = #17 (index AM) ∪ #19 (WAL record) ∪ #30 (extension) ∪ #25 (LWLock
  tranche if shared-memory bookkeeping is needed).
- **"Add a hook that lets an extension intercept query rewrite"**
  = #24 (hook) ∪ #30 (extension to demo it) ∪ #21 (GUC if the hook is
  togglable).
- **"Add MERGE-WHEN-NOT-MATCHED-BY-SOURCE support"**
  = #11 (keyword) ∪ #13 (utility statement extension) ∪ #14 (plan
  node if new) ∪ #19 (WAL if a new sub-record).

## Gaps register

When `pg-feature-plan` encounters a change-class with NO matching
scenario, it MUST flag the gap. The gap register lives in
`progress/scenarios-coverage.md` under "Gaps surfaced by planner
runs". Future-us fills the gap by writing a new scenario.
