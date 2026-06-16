export const meta = {
  name: 'scenarios-content',
  description: 'Write all 31 scenario playbooks in parallel using the shared template',
  phases: [
    { title: 'Write scenarios' },
  ],
}

const REPO = '/Users/matej/Work/postgres/postgres-claude/.claude/worktrees/ft_pg_scenarios_web_of_context'
const ANCHOR = 'e18b0cb7344'

const SCENARIOS = [
  // Catalog basics
  { slug: 'bump-catversion', title: 'Bump CATALOG_VERSION_NO',
    trigger: 'When and why to bump CATALOG_VERSION_NO; the initdb-invalidation cycle.',
    skills: ['catalog-conventions'],
    related: ['add-new-builtin-function', 'add-new-data-type', 'add-new-system-catalog-column'],
    seeds: [
      'src/include/catalog/catversion.h',
      'src/backend/access/transam/xlog.c (ReadControlFile)',
      'src/include/catalog/pg_control.h',
      'src/bin/initdb/initdb.c',
    ],
    notes: 'Trigger: editing any src/include/catalog/*.h or *.dat that changes tuple format or seeded contents, changing tuple-header layout, or changing pg_node_tree serialization (parsenodes.h/primnodes.h almost-always counts because parsetrees appear in stored rules and new-style SQL fn bodies). genbki.pl runs at build but the data dir is invalidated until initdb. NO regression test; the verification is "initdb succeeds after the bump".'
  },
  { slug: 'add-new-builtin-function', title: 'Add a new built-in SQL function',
    trigger: 'A new pg_proc.dat entry pointing at a C function — the cheapest catalog-touching change-class.',
    skills: ['catalog-conventions', 'fmgr-and-spi'],
    related: ['add-new-operator', 'add-new-data-type', 'add-new-aggregate-function', 'bump-catversion'],
    seeds: [
      'src/include/catalog/pg_proc.dat',
      'src/backend/utils/adt/*.c',
      'src/include/utils/fmgrprotos.h (auto-generated)',
      'src/include/catalog/catversion.h',
      'doc/src/sgml/func.sgml',
    ],
    notes: 'pg_proc.dat row fields: oid, proname, prorettype, proargtypes, provolatile (i/s/v), prosrc. New PG_FUNCTION_INFO_V1(name) + Datum name(PG_FUNCTION_ARGS). Tests: src/test/regress/sql/<name>.sql + expected/<name>.out. Often also a parallel_tests group entry in src/test/regress/parallel_schedule.'
  },
  { slug: 'add-new-data-type', title: 'Add a new built-in scalar data type',
    trigger: 'New built-in scalar type (NOT user CREATE TYPE extension). The classic 12-14-file sweep that proves the corpus has scenarios.',
    skills: ['catalog-conventions', 'fmgr-and-spi'],
    related: ['add-new-operator', 'add-new-operator-class', 'add-new-cast', 'add-new-builtin-function'],
    seeds: [
      'src/include/catalog/pg_type.dat',
      'src/include/catalog/pg_proc.dat',
      'src/include/catalog/pg_operator.dat',
      'src/include/catalog/pg_cast.dat',
      'src/include/catalog/pg_opclass.dat',
      'src/include/catalog/pg_amop.dat',
      'src/include/catalog/pg_amproc.dat',
      'src/backend/utils/adt/numutils.c (look at similar type impls)',
      'src/include/catalog/catversion.h',
      'src/test/regress/sql/ (existing type tests for shape)',
      'doc/src/sgml/datatype.sgml',
    ],
    notes: 'For a complete usable type you typically need: pg_type.dat (the type itself), pg_proc.dat (foo_in/foo_out/foo_recv/foo_send plus comparison and helper fns), utils/adt/<name>.c (C impl, NEW file), pg_operator.dat (the operators), pg_amop.dat + pg_amproc.dat (so it works with btree/hash indexes), pg_opclass.dat (default opclass), pg_cast.dat (text↔type), catversion.h bump, src/test/regress/sql/<name>.sql + expected, doc/src/sgml/datatype.sgml. That is the 12-14 files. typmod functions are an additional axis (foo_typmod_in/out) — flag if the type needs them.'
  },
  { slug: 'add-new-operator-class',
    title: 'Add a new operator class for an existing index AM',
    trigger: 'Make a type work with an existing index AM (btree, hash, gist, gin, spgist, brin).',
    skills: ['catalog-conventions', 'access-method-apis'],
    related: ['add-new-data-type', 'add-new-index-am', 'add-new-operator'],
    seeds: [
      'src/include/catalog/pg_opclass.dat',
      'src/include/catalog/pg_opfamily.dat',
      'src/include/catalog/pg_amop.dat',
      'src/include/catalog/pg_amproc.dat',
      'src/include/access/amapi.h',
      'src/include/access/{nbtree.h,hash.h,gist.h,gin.h,spgist.h,brin.h}',
    ],
    notes: 'Strategy numbers + support-function numbers differ per AM (btree=5 strategies, hash=1, gist/spgist/gin/brin custom). For btree: < <= = >= > strategies and one cmp support fn. For hash: = strategy + hash support fn. For gist: consistent + union + compress + decompress + penalty + picksplit + equal etc. Tests typically in src/test/regress/sql/<type>.sql.'
  },
  { slug: 'add-new-operator', title: 'Add a new built-in operator',
    trigger: 'A new entry in pg_operator.dat with commutator/negator/restrict/join estimators.',
    skills: ['catalog-conventions', 'fmgr-and-spi'],
    related: ['add-new-builtin-function', 'add-new-data-type', 'add-new-operator-class'],
    seeds: [
      'src/include/catalog/pg_operator.dat',
      'src/include/catalog/pg_proc.dat',
      'src/backend/utils/adt/selfuncs.c',
    ],
    notes: 'pg_operator.dat fields: oprname, oprleft, oprright, oprresult, oprcom (commutator), oprnegate (negator), oprrest (restriction selectivity proc), oprjoin (join selectivity proc), oprcanmerge, oprcanhash. Procedure must exist in pg_proc.dat already. If the operator is hashable/mergeable, the planner uses it for hash/merge joins — easy correctness landmine.'
  },
  { slug: 'add-new-cast', title: 'Add a new built-in type cast',
    trigger: 'A new pg_cast.dat entry — implicit, assignment, or explicit.',
    skills: ['catalog-conventions'],
    related: ['add-new-data-type', 'add-new-builtin-function'],
    seeds: [
      'src/include/catalog/pg_cast.dat',
      'src/include/catalog/pg_proc.dat',
      'src/backend/parser/parse_coerce.c',
    ],
    notes: 'pg_cast.dat fields: castsource, casttarget, castfunc (0 = binary-coercible), castcontext (e=explicit/a=assignment/i=implicit), castmethod (f=function/b=binary/i=I/O). Implicit casts are dangerous — they expand the resolution lattice and can create ambiguous-cast errors elsewhere; prefer assignment unless community consensus says implicit.'
  },
  { slug: 'add-new-aggregate-function', title: 'Add a new built-in aggregate',
    trigger: 'New aggregate: pg_aggregate.dat + sfunc / finalfunc / serialize / deserialize / combine.',
    skills: ['catalog-conventions', 'fmgr-and-spi'],
    related: ['add-new-builtin-function', 'add-new-data-type'],
    seeds: [
      'src/include/catalog/pg_aggregate.dat',
      'src/include/catalog/pg_proc.dat',
      'src/backend/executor/nodeAgg.c',
      'src/backend/utils/adt/aggregates.c (if it exists; otherwise sibling files)',
    ],
    notes: 'aggtransfn (sfunc) + aggfinalfn (finalfunc, optional). For parallel-aware aggs also aggcombinefn + aggserialfn + aggdeserialfn. transtype matters for memory: if transtype is INTERNAL the state can be a pointer to a palloc-ed struct, otherwise it must be a flat Datum. proparallel = s or u flag matters.'
  },
  { slug: 'add-new-error-code', title: 'Add a new SQLSTATE / error code',
    trigger: 'New errcode in errcodes.txt — plpgsql condition + SGML doc.',
    skills: ['error-handling'],
    related: [],
    seeds: [
      'src/backend/utils/errcodes.txt',
      'src/pl/plpgsql/src/plerrcodes.h (generated)',
      'doc/src/sgml/errcodes.sgml (generated lookup table)',
    ],
    notes: 'errcodes.txt drives multiple generated files (errcodes.h, plerrcodes.h, errcodes-appendix.sgml). After editing, the build regenerates them; the SGML appendix updates automatically. Pick a 5-character SQLSTATE: 2 chars class (existing) + 3 chars subclass (new digits not yet used).'
  },
  { slug: 'add-new-system-catalog-column', title: 'Add a column to an existing system catalog',
    trigger: 'New column on an existing pg_xxx catalog — both the .h declaration and the .dat seed.',
    skills: ['catalog-conventions'],
    related: ['bump-catversion', 'add-new-system-view'],
    seeds: [
      'src/include/catalog/pg_*.h (whichever catalog)',
      'src/include/catalog/pg_*.dat',
      'src/include/catalog/catversion.h',
      'doc/src/sgml/catalogs.sgml',
    ],
    notes: 'CATALOG() declaration in the .h file: BKI_DEFAULT() or NameData / Oid type. Many catalogs have a "boot strap fields" rule (no varlena before fixed-width fields, no NULLable fields without BKI_FORCE_NOT_NULL). If column is part of a unique index, add to src/include/catalog/indexing.h or affected DECLARE_UNIQUE_INDEX. catversion bump is mandatory.'
  },
  { slug: 'add-new-system-view', title: 'Add a new system view',
    trigger: 'New view in system_views.sql + supporting functions in pg_proc.dat.',
    skills: ['catalog-conventions'],
    related: ['add-new-pg-stat-view', 'add-new-builtin-function', 'add-new-system-catalog-column'],
    seeds: [
      'src/backend/catalog/system_views.sql',
      'src/include/catalog/pg_proc.dat',
      'doc/src/sgml/system-views.sgml',
    ],
    notes: 'system_views.sql runs during initdb. Set-returning support functions (PG_RETURN_*) live in src/backend/utils/adt or src/backend/access/. Pure SQL views (no support fn needed) are the simplest. Grant convention: REVOKE ALL ... GRANT SELECT to pg_read_all_stats or similar role if sensitive.'
  },

  // Parser / grammar
  { slug: 'add-new-sql-keyword', title: 'Add a new SQL keyword',
    trigger: 'New keyword in the SQL grammar — gram.y + kwlist.h + parsenodes.h + analyze + the psqlscan/ecpg sync trap.',
    skills: ['parser-and-nodes'],
    related: ['add-new-utility-statement', 'add-new-node-type'],
    seeds: [
      'src/include/parser/kwlist.h',
      'src/backend/parser/gram.y',
      'src/include/nodes/parsenodes.h',
      'src/backend/parser/analyze.c',
      'src/fe_utils/psqlscan.l (the classic sync trap)',
      'src/interfaces/ecpg/preproc/pgc.l (second sync trap)',
      'src/interfaces/ecpg/preproc/c_kwlist.h',
      'src/interfaces/ecpg/preproc/ecpg_kwlist.h',
      'src/bin/psql/tab-complete.in.c',
      'src/test/regress/expected/keywords.out',
    ],
    notes: 'Keyword categories in kwlist.h: UNRESERVED_KEYWORD, COL_NAME_KEYWORD, TYPE_FUNC_NAME_KEYWORD, RESERVED_KEYWORD. New reserved keywords break user code — prefer unreserved if at all possible. The kwlist.h list MUST be sorted alphabetically (build will reject otherwise). The psqlscan.l + pgc.l sync trap is the #1 sin against this change-class: psql line-continuation logic and ecpg preprocessor both have their own keyword scanners that must agree with kwlist.h. Always check src/test/regress/expected/keywords.out — the kwlist length is exposed there.'
  },
  { slug: 'add-new-node-type', title: 'Add a new Node type',
    trigger: 'New Node in parsenodes.h / primnodes.h / plannodes.h — gen_node_support.pl regen + copy/equal/out/read + walker/mutator.',
    skills: ['parser-and-nodes'],
    related: ['add-new-plan-node', 'add-new-utility-statement'],
    seeds: [
      'src/include/nodes/parsenodes.h',
      'src/include/nodes/primnodes.h',
      'src/include/nodes/plannodes.h',
      'src/include/nodes/nodes.h',
      'src/backend/nodes/gen_node_support.pl',
      'src/backend/nodes/{copyfuncs,equalfuncs,outfuncs,readfuncs}.funcs.c (generated)',
      'src/backend/nodes/nodeFuncs.c (expression_tree_walker / mutator)',
    ],
    notes: 'gen_node_support.pl reads the header files and generates copy/equal/out/read functions. Annotation markers like /* pg_node_attr(no_copy_equal) */ control generation. After adding a Node: rerun build; the .funcs.c files regenerate. If the Node is an expression (subtype of Expr), it must be walked by expression_tree_walker — the switch in nodeFuncs.c needs a new case unless you use the auto-generated dispatch. Storage in pg_node_tree (catalogs like pg_rewrite or new-style SQL fn bodies) triggers catversion bump.'
  },
  { slug: 'add-new-utility-statement', title: 'Add a new utility statement',
    trigger: 'New CREATE/DROP/ALTER-style statement: XxxStmt Node + standard_ProcessUtility dispatch + tab-complete.',
    skills: ['parser-and-nodes'],
    related: ['add-new-sql-keyword', 'add-new-node-type'],
    seeds: [
      'src/backend/tcop/utility.c (standard_ProcessUtility)',
      'src/backend/parser/gram.y',
      'src/include/nodes/parsenodes.h',
      'src/backend/commands/*.c (existing utility impls for shape)',
      'src/bin/psql/tab-complete.in.c',
      'doc/src/sgml/ref/ (one SGML file per statement)',
    ],
    notes: 'standard_ProcessUtility dispatches on T_XxxStmt via switch. Add the case there, calling into a new src/backend/commands/<name>.c with the impl. Permissions: most CREATE/DROP need pg_xxx_aclcheck or superuser-or-owner. Hook chain: ProcessUtility_hook can intercept; document if your statement honors it. New ref/ SGML file is mandatory for any user-visible statement.'
  },

  // Executor / planner
  { slug: 'add-new-plan-node', title: 'Add a new plan node',
    trigger: 'New executor node type: Path + Plan + PlanState + nodeXxx.c + createplan.c + EXPLAIN + (if parallel-aware) DSM hooks.',
    skills: ['executor-and-planner', 'parallel-query'],
    related: ['add-new-node-type', 'add-new-expression-eval-step', 'add-new-cost-model-knob'],
    seeds: [
      'src/include/nodes/pathnodes.h (Path)',
      'src/include/nodes/plannodes.h (Plan)',
      'src/include/nodes/execnodes.h (PlanState)',
      'src/backend/executor/nodeXxx.c (existing nodes for shape — nodeSeqscan.c, nodeHashjoin.c)',
      'src/backend/optimizer/plan/createplan.c',
      'src/backend/optimizer/util/pathnode.c',
      'src/backend/commands/explain.c',
      'src/backend/executor/execProcnode.c (ExecInitNode dispatch)',
    ],
    notes: 'Triplet structure: XxxPath (planner cost), XxxPlan (post-plan structure), XxxState (executor runtime state). createplan.c maps Path → Plan; execProcnode.c maps Plan → State via ExecInitXxx. EXPLAIN dispatch in explain.c — add a case in ExplainNode + show_xxx_info for any custom display. Parallel-aware nodes need ExecXxxEstimate / ExecXxxInitializeDSM / ExecXxxInitializeWorker / ExecShutdownXxx; otherwise mark parallel_safe=false.'
  },
  { slug: 'add-new-expression-eval-step',
    title: 'Add a new expression-eval step',
    trigger: 'New step kind in execExpr.c — interpreter case + JIT mirror in llvmjit_expr.c.',
    skills: ['executor-and-planner'],
    related: ['add-new-node-type', 'add-new-plan-node'],
    seeds: [
      'src/include/executor/execExpr.h (ExprEvalOp enum)',
      'src/backend/executor/execExpr.c (ExecReadyInterpretedExpr)',
      'src/backend/executor/execExprInterp.c (ExecInterpExpr)',
      'src/backend/jit/llvm/llvmjit_expr.c (mirror)',
    ],
    notes: 'Two implementations live in lockstep: the interpreter (execExprInterp.c, switch over ExprEvalOp) and the LLVM JIT (llvmjit_expr.c, llvm_compile_expr). Both must handle the new step or JIT-compiled plans crash. Add the enum value, the interpreter case, the JIT case, and an emit-time helper in execExpr.c that pushes the step. If touching reachable paths, run regress under both JIT and non-JIT (jit=on/off GUC).'
  },
  { slug: 'add-new-cost-model-knob', title: 'Add a new cost-model constant',
    trigger: 'New cost in cost.h + use in cost_*.c (plus a GUC if user-tunable).',
    skills: ['executor-and-planner', 'gucs-config'],
    related: ['add-new-plan-node', 'add-new-guc'],
    seeds: [
      'src/include/optimizer/cost.h',
      'src/backend/optimizer/path/costsize.c',
      'src/backend/utils/misc/guc_tables.c (if a GUC)',
      'src/backend/utils/misc/postgresql.conf.sample',
    ],
    notes: 'Pattern: declare extern double DEFAULT_<name>_COST; define in costsize.c; reference from cost_seqscan / cost_index / cost_bitmap_heap_scan / etc. If user-tunable, add to guc_tables.c (real_typed) with default. Changing existing cost defaults breaks plans across the universe — touch with extreme care and benchmark with TPC-H/pgbench.'
  },

  // Storage / access methods
  { slug: 'add-new-index-am', title: 'Add a new index access method',
    trigger: 'Brand-new index method (not just an opclass for an existing AM): handler function + IndexAmRoutine + WAL rmgr + amapi registration.',
    skills: ['access-method-apis', 'wal-and-xlog'],
    related: ['add-new-operator-class', 'add-new-wal-record', 'add-new-lwlock-tranche'],
    seeds: [
      'src/include/access/amapi.h',
      'src/backend/access/amapi.c',
      'src/backend/access/{nbtree,hash,gist,gin,spgist,brin}/* (existing AMs for shape)',
      'src/include/catalog/pg_am.dat',
      'src/include/catalog/pg_opfamily.dat / pg_opclass.dat (default opclass for the AM)',
      'src/include/access/xlog_internal.h (rmgr id assignment)',
      'src/backend/access/rmgrdesc/*desc.c',
    ],
    notes: 'IndexAmRoutine has ~20 callbacks: ambuild, ambuildempty, aminsert, ambulkdelete, amvacuumcleanup, amcanreturn, amcostestimate, amoptions, amproperty, amvalidate, ambeginscan, amrescan, amgettuple, amgetbitmap, amendscan, ammarkpos, amrestrpos, amestimateparallelscan, aminitparallelscan, amparallelrescan. Each AM gets its own WAL rmgr id (RM_xxx_ID) in xlog_internal.h. amvalidate is non-optional and runs at pg_opclass validation time. Tests: full src/test/regress/sql/<am>.sql with create-index/use/drop coverage.'
  },
  { slug: 'add-new-table-am', title: 'Add a new table access method',
    trigger: 'Brand-new heap-replacement table AM (Heapless, columnar, etc.): handler + TableAmRoutine + visibility-map and toast wiring.',
    skills: ['access-method-apis'],
    related: ['add-new-index-am', 'add-new-wal-record'],
    seeds: [
      'src/include/access/tableam.h',
      'src/backend/access/table/tableam.c',
      'src/backend/access/heap/heapam_handler.c (the canonical TableAmRoutine impl)',
      'src/include/catalog/pg_am.dat',
      'src/include/access/heapam.h',
    ],
    notes: 'TableAmRoutine has 40+ callbacks split across scan / tuple-fetch / tuple-insert+update+delete / DDL / cluster / vacuum / sample / parallel-scan / toast. Reference impl is src/backend/access/heap/heapam_handler.c — read end-to-end before designing. Visibility map and toast tables are still owned by the AM impl; you decide whether to support them. Tests: shape mirrors heap regression coverage but in a contrib/ or src/test/modules/ harness because new TableAMs typically ship as extensions.'
  },
  { slug: 'add-new-wal-record', title: 'Add a new WAL record',
    trigger: 'New WAL record type (new rmgr or new info byte in an existing rmgr): redo function + rmgrdesc + identify + XLOG_PAGE_MAGIC if needed.',
    skills: ['wal-and-xlog'],
    related: ['add-new-index-am', 'add-new-table-am'],
    seeds: [
      'src/include/access/xlog_internal.h',
      'src/include/access/rmgrlist.h',
      'src/backend/access/rmgrdesc/<rmgr>desc.c',
      'src/include/access/xlog.h (XLOG_PAGE_MAGIC)',
      'src/backend/access/transam/xlogrecovery.c',
    ],
    notes: 'Two flavors: (a) new RmgrId — add to rmgrlist.h, implement rmgr struct (redo/desc/identify/startup/cleanup/etc.) in src/backend/access/<area>; (b) new info-byte on an existing rmgr — add the XLOG_FOO constant, extend the redo switch, extend the desc and identify functions. Either flavor changes the WAL format → XLOG_PAGE_MAGIC bump. pg_waldump uses the desc/identify functions; broken desc = broken pg_waldump. Hot Standby conflict generation: if the record can drop tuples a standby is still reading, the redo function must emit ResolveRecoveryConflictWithSnapshot.'
  },
  { slug: 'add-new-buffer-strategy', title: 'Add a new BufferAccessStrategy ring',
    trigger: 'New ring-buffer class for scans that should not pollute the main buffer pool.',
    skills: ['memory-contexts'],
    related: ['add-new-table-am'],
    seeds: [
      'src/include/storage/bufmgr.h (BufferAccessStrategyType)',
      'src/backend/storage/buffer/freelist.c',
      'src/backend/storage/buffer/bufmgr.c (StrategyRejectBuffer paths)',
    ],
    notes: 'GetAccessStrategy(BAS_xxx) returns a BufferAccessStrategy. Ring size is per-class (BAS_BULKREAD=256KB, BAS_BULKWRITE=16MB, BAS_VACUUM=256KB historically). Adding a new class is rare — most use-cases get covered by existing rings. Heuristic: only add if a recurring workload pollutes shared_buffers AND none of BULKREAD/BULKWRITE/VACUUM fits.'
  },

  // Infrastructure / runtime
  { slug: 'add-new-guc', title: 'Add a new GUC',
    trigger: 'New GUC: either a built-in (static struct config_xxx) or a custom one (DefineCustomXxxVariable from an extension).',
    skills: ['gucs-config'],
    related: ['add-new-cost-model-knob', 'add-new-hook'],
    seeds: [
      'src/backend/utils/misc/guc_tables.c',
      'src/backend/utils/misc/guc.c',
      'src/backend/utils/misc/postgresql.conf.sample',
      'src/include/utils/guc.h',
      'doc/src/sgml/config.sgml',
    ],
    notes: 'Built-in GUCs go in guc_tables.c (one of ConfigureNamesBool/Int/Real/String/Enum). Required fields: name, context (PGC_USERSET/PGC_SUSET/PGC_POSTMASTER/etc.), group, short_desc, long_desc, GUC_UNIT_*, &variable, default_val, min/max, check_hook, assign_hook, show_hook. Extension GUCs use DefineCustomXxxVariable + MarkGUCPrefixReserved. postgresql.conf.sample must list it (commented out with default) — release scripts depend on this. config.sgml documents it. Tests: pg_settings view + check/assign-hook coverage if non-trivial.'
  },
  { slug: 'add-startup-hook', title: 'Add a new startup-lifecycle hook',
    trigger: 'A hook point in the PostmasterMain / PostgresMain / InitPostgres flow (the "main ring in postgres.c" question).',
    skills: ['bgworker-and-extensions'],
    related: ['add-new-bgworker', 'add-new-hook', 'add-new-shared-memory-region'],
    seeds: [
      'src/backend/postmaster/postmaster.c (PostmasterMain)',
      'src/backend/tcop/postgres.c (PostgresMain)',
      'src/backend/utils/init/postinit.c (InitPostgres)',
      'src/backend/storage/ipc/ipci.c (CreateSharedMemoryAndSemaphores)',
      'src/backend/utils/init/miscinit.c (process-role flags)',
    ],
    notes: 'Three canonical lifecycle slots, each at a different invariant: (1) postmaster startup (BEFORE any fork: shmem sizing, file checks) → shmem_request_hook. (2) per-backend init (AFTER fork, BEFORE auth) → ClientAuthentication_hook or backend startup additions in PostgresMain. (3) per-backend post-auth (AFTER user is known) → InitPostgres tail. Pick by what state you need. RegisterBackgroundWorker → see add-new-bgworker. The user-typed "hook into the main ring" usually means one of these three slots; ask which lifecycle stage.'
  },
  { slug: 'add-new-bgworker', title: 'Add a new background worker',
    trigger: 'A background process: static (preloaded) or dynamic (started by SQL/extension).',
    skills: ['bgworker-and-extensions', 'parallel-query'],
    related: ['add-new-extension', 'add-new-shared-memory-region', 'add-startup-hook'],
    seeds: [
      'src/include/postmaster/bgworker.h',
      'src/backend/postmaster/bgworker.c',
      'src/test/modules/worker_spi/worker_spi.c (the canonical example)',
      'src/backend/postmaster/postmaster.c (maybe_start_bgworkers)',
    ],
    notes: 'Two registration paths: RegisterBackgroundWorker (static, must be called from shared_preload_libraries _PG_init) vs RegisterDynamicBackgroundWorker (called by a running backend, returns a handle to wait on). Required fields in BackgroundWorker struct: bgw_name, bgw_type, bgw_flags (BGWORKER_SHMEM_ACCESS, BGWORKER_BACKEND_DATABASE_CONNECTION), bgw_start_time (BgWorkerStart_*), bgw_restart_time (or BGW_NEVER_RESTART), bgw_function_name + bgw_library_name, bgw_main_arg, bgw_notify_pid. Worker main signature: void worker_main(Datum main_arg). Must call BackgroundWorkerInitializeConnection before SPI; install signal handlers; loop on WaitLatch.'
  },
  { slug: 'add-new-hook', title: 'Add a new extension hook',
    trigger: 'A new extension hook in the planner_hook / ExecutorStart_hook / ProcessUtility_hook style.',
    skills: ['bgworker-and-extensions'],
    related: ['add-startup-hook', 'add-new-guc'],
    seeds: [
      'src/backend/optimizer/plan/planner.c (planner_hook)',
      'src/backend/executor/execMain.c (ExecutorStart_hook / ExecutorRun_hook)',
      'src/backend/tcop/utility.c (ProcessUtility_hook)',
      'src/backend/parser/analyze.c (post_parse_analyze_hook)',
      'src/backend/utils/init/miscinit.c (ClientAuthentication_hook)',
    ],
    notes: 'Pattern: declare `XxxHook_type Xxx_hook = NULL;` in a .c file, expose extern in the matching .h. Callers wrap as `if (Xxx_hook) Xxx_hook(...) else standard_Xxx(...);` — the standard function is exported so chained extensions can fall through. NEVER make the hook synchronous-stop only: it must be chainable. Document the contract: when does the hook run, what state is set, what may it mutate. Adding hooks needs broad agreement on pgsql-hackers; an extension-need-only hook is often rejected.'
  },
  { slug: 'add-new-lwlock-tranche', title: 'Add a new LWLock tranche',
    trigger: 'A built-in LWLock tranche (lwlocknames.txt) or extension tranche (RequestNamedLWLockTranche).',
    skills: ['locking'],
    related: ['add-new-shared-memory-region', 'add-new-index-am'],
    seeds: [
      'src/backend/storage/lmgr/lwlocknames.txt',
      'src/include/storage/lwlock.h',
      'src/backend/storage/lmgr/lwlock.c (LWLockNewTrancheId, GetLWLockIdentifier)',
      'src/backend/utils/activity/wait_event_names.txt',
      'src/test/modules/test_shm_mq/test.c (extension example)',
    ],
    notes: 'Built-in: append an entry to lwlocknames.txt with the tranche id; build regenerates lwlocknames.h + numeric enum. Extension: call LWLockNewTrancheId once, LWLockInitialize per lock, LWLockRegisterTranche(id, name) in every backend that touches the shmem. Add an entry to wait_event_names.txt so pg_stat_activity.wait_event surfaces a friendly name instead of "extension" or "??\??".'
  },
  { slug: 'add-new-shared-memory-region', title: 'Add a new shared-memory region',
    trigger: 'New shmem area sized at postmaster start: RequestAddinShmemSpace + shmem_request_hook + shmem_startup_hook.',
    skills: ['memory-contexts'],
    related: ['add-new-lwlock-tranche', 'add-new-bgworker'],
    seeds: [
      'src/backend/storage/ipc/ipci.c (CreateSharedMemoryAndSemaphores)',
      'src/include/storage/ipc.h (shmem_request_hook / shmem_startup_hook)',
      'src/backend/storage/ipc/shmem.c (ShmemInitStruct, ShmemAlloc)',
      'src/test/modules/test_shm_mq/setup.c',
    ],
    notes: 'Three-step pattern: (1) hook into shmem_request_hook to call RequestAddinShmemSpace(size) and RequestNamedLWLockTranche if needed; (2) hook into shmem_startup_hook to ShmemInitStruct your area, LWLockInitialize each lock, populate initial state — guard with LWLockAcquire(AddinShmemInitLock); (3) initialization must be idempotent because crashed-backend restart re-enters the hook. Extension must be in shared_preload_libraries for postmaster-startup hooks to fire.'
  },
  { slug: 'add-new-pg-stat-view', title: 'Add a new pg_stat_* view',
    trigger: 'Cumulative or live statistics view: pgstat machinery + system_views.sql + supporting set-returning function.',
    skills: ['catalog-conventions'],
    related: ['add-new-system-view', 'add-new-builtin-function'],
    seeds: [
      'src/backend/utils/activity/pgstat.c',
      'src/backend/utils/activity/pgstat_*.c (per-kind file)',
      'src/include/utils/pgstat_internal.h',
      'src/backend/catalog/system_views.sql',
      'src/include/catalog/pg_proc.dat',
      'doc/src/sgml/monitoring.sgml',
    ],
    notes: 'pg_stat machinery has a pluggable per-kind structure (PgStat_KindInfo). For a new persistent stat kind: add to PgStat_Kind enum, implement KindInfo (flush_cb / reset_*_cb), register via pgstat_register_kind (if extension) or extend the static table. For a simple ephemeral view over existing state, often just need a new SRF + system_views.sql entry. Stats file format changes need PGSTAT_FILE_FORMAT_ID bump (in pgstat_internal.h).'
  },

  // Replication / wire / extensions
  { slug: 'add-new-protocol-message', title: 'Add a new libpq protocol message',
    trigger: 'New byte-tag on the wire — frontend libpq + backend dispatch + protocol.sgml.',
    skills: [],
    related: ['add-new-replication-message'],
    seeds: [
      'src/include/libpq/protocol.h (message-type constants)',
      'src/interfaces/libpq/fe-protocol3.c',
      'src/backend/tcop/postgres.c (PostgresMain main loop)',
      'src/backend/libpq/pqcomm.c',
      'doc/src/sgml/protocol.sgml',
    ],
    notes: 'Protocol changes are NOT backwards-compatible by definition — they bump PG_PROTOCOL_LATEST (src/include/libpq/pqcomm.h). Both v3 backwards compat + new version must coexist for a release. Adding a message that violates an existing exchange (Sync/Ready cycle, async error frame) breaks every existing libpq-compatible client. Document on protocol.sgml AND the wire-protocol section in the docs. This is one of the highest-risk change-classes; pgsql-hackers review is mandatory.'
  },
  { slug: 'add-new-replication-message', title: 'Add a new replication / logical-decoding message',
    trigger: 'New logical-decoding output_plugin callback OR new walsender command.',
    skills: ['replication-overview'],
    related: ['add-new-wal-record', 'add-new-protocol-message'],
    seeds: [
      'src/include/replication/output_plugin.h',
      'src/backend/replication/logical/logical.c',
      'src/backend/replication/walsender.c',
      'src/backend/replication/pgoutput/pgoutput.c (canonical output plugin)',
      'doc/src/sgml/logicaldecoding.sgml',
    ],
    notes: 'Two distinct surfaces. (a) Output plugin: add a callback hook to OutputPluginCallbacks (e.g. stream_start_cb), thread through pgoutput. Plugins implement the new callback or NULL it. (b) Walsender command: add a parser rule in replication grammar (repl_gram.y), handler in walsender.c. Both surfaces are protocol-visible to subscribers; bumping LOGICALREP_PROTO_VERSION_NUM is the protocol-versioning lever for case (a).'
  },
  { slug: 'add-new-extension', title: 'Add a new contrib extension',
    trigger: 'New contrib/<name>/: .control + foo--1.0.sql + _PG_init + Makefile + meson + tests.',
    skills: ['extension-development'],
    related: ['add-new-bgworker', 'add-new-hook', 'add-new-test-module'],
    seeds: [
      'contrib/<existing>/Makefile + meson.build (read several for shape)',
      'contrib/<existing>/<name>.control',
      'contrib/<existing>/<name>--1.0.sql',
      'contrib/<existing>/<name>.c (_PG_init)',
      'contrib/meson.build',
      'contrib/Makefile',
    ],
    notes: 'Layout: contrib/<name>/<name>.control (META: comment, default_version, module_pathname=$libdir/<name>, relocatable=true), <name>--1.0.sql (SQL objects: types, functions, opclasses), <name>.c (_PG_init for hook setup, PG_MODULE_MAGIC). Makefile sets MODULE_big or MODULES, OBJS, EXTENSION, DATA, PGFILEDESC. meson.build needs add to contrib/meson.build subdir() list. Tests: REGRESS in Makefile, sql/ + expected/. Upgrade scripts: <name>--1.0--1.1.sql when bumping default_version.'
  },
  { slug: 'add-new-test-module', title: 'Add a new src/test/modules/<name>',
    trigger: 'In-tree test module for backend behavior that cannot be exercised from SQL alone: TAP, isolation hooks, or C-only test surface.',
    skills: ['testing'],
    related: ['add-new-extension', 'add-new-bgworker'],
    seeds: [
      'src/test/modules/<existing>/Makefile + meson.build',
      'src/test/modules/<existing>/<name>.c',
      'src/test/modules/<existing>/sql/ + expected/',
      'src/test/modules/<existing>/t/*.pl (TAP)',
      'src/test/modules/meson.build',
      'src/test/modules/Makefile',
    ],
    notes: 'Shape is like a contrib extension, but installed only for the regress + TAP suites — not shipped to users. Used for hook-coverage tests (e.g. worker_spi for bgworker), TAP-via-Cluster.pm (multi-cluster scenarios), and isolation tests that need C support functions. Cluster.pm at src/test/perl/PostgreSQL/Test/Cluster.pm is the TAP harness; check examples in src/test/recovery/t/ for usage.'
  },
]

phase('Write scenarios')

const results = await parallel(SCENARIOS.map((s, i) => () =>
  agent(
    `You are writing scenario #${i+1} of 31 for the pg-claude knowledge corpus.

Your scenario: \`${s.slug}\`
Title: ${s.title}
Trigger: ${s.trigger}
Companion skills: ${JSON.stringify(s.skills)}
Related scenarios: ${JSON.stringify(s.related)}

# Output

Write a single file at: \`${REPO}/knowledge/scenarios/${s.slug}.md\`

Follow EXACTLY the template at \`${REPO}/knowledge/scenarios/_template.md\`. Read it first.
Also read \`${REPO}/knowledge/scenarios/README.md\` and \`${REPO}/knowledge/scenarios/_index.md\` for context on the layer's purpose and the linking conventions.

# Required content

Frontmatter MUST include:
- \`scenario: ${s.slug}\`
- \`when_to_use:\` <one-sentence trigger>
- \`companion_skills: ${JSON.stringify(s.skills)}\`
- \`related_scenarios: ${JSON.stringify(s.related)}\`
- \`canonical_commit:\` — pick a representative historical PG commit by searching \`git -C source log --oneline --grep=...\` for the change-class. If you can't confidently identify one, use the short SHA \`e18b0cb7344\` (current anchor) and add a "TODO: find historical canonical commit" inline.
- \`last_verified_commit: e18b0cb7344\`

# The file checklist (the heart of the scenario)

Verify file:line cites against the live tree. The anchor is \`e18b0cb7344\` (HEAD of \`${REPO}/source\` at write time — already checked out). Run greps under \`${REPO}/source/\` to confirm:
- Every file in the checklist EXISTS at the cited path.
- The "why" column accurately states what changes (read the file briefly if unsure).
- If a per-file doc exists under \`${REPO}/knowledge/files/<same-relative-path>.md\`, link it as the fourth column.
- Companion skill column points to a real \`.claude/skills/<name>/\` dir (verify via \`ls ${REPO}/.claude/skills/\`).

Seed files (you should look at these and likely many more — grep widely):
${s.seeds.map(p => `- \`${p}\``).join('\n')}

Domain notes for this scenario: ${s.notes}

# Confidence-tag rules

Per CLAUDE.md: every concrete claim about PG behavior needs \`[verified-by-code]\`, \`[from-comment]\`, \`[from-README]\`, \`[from-docs]\`, \`[inferred]\`, or \`[unverified]\`. Tag inline. Aim mostly for \`[verified-by-code]\` since you have the source tree.

# Tone + length

Match the existing knowledge corpus tone: terse, technical, no marketing. Read \`${REPO}/knowledge/idioms/catalog-conventions.md\` (or any idiom) for the voice if unsure.

Aim for ~150-300 lines. The file checklist table is the load-bearing section — be exhaustive there. Phases section should suggest 3-4 phases. Pitfalls should have 3-6 entries. Verification names exact test files / meson invocations.

# Discipline

- Do NOT invent file paths. Verify before citing.
- For NEW files (the change itself creates them), mark per-file doc column as \`—\` and "Why" as "(NEW) ..."
- Cross-refs section MUST list at least: companion skills, related scenarios, one or more idioms, one or more subsystems.

# Output

The agent's final text is consumed by the orchestrator. After successfully writing the file, return ONLY a short JSON-like line: \`{"slug": "${s.slug}", "files_in_checklist": <count>, "lines": <approx>}\`. Do NOT echo the file contents.
`,
    {
      label: s.slug,
      phase: 'Write scenarios',
    }
  )
))

const summary = results.filter(Boolean)
return { written: summary.length, of: SCENARIOS.length, summary }
