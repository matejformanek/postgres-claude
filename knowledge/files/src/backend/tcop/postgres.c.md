# postgres.c

- **Source:** `source/src/backend/tcop/postgres.c` (5320 lines)
- **Last verified commit:** `ef6a95c7c64` (2026-06-01)
- **Depth:** deep-read (PostgresMain, exec_simple_query, exec_execute_message,
  signal handlers)

## Purpose

The **traffic cop**: the per-backend main module. Hosts `PostgresMain`, the
infinite loop that reads protocol messages from the client and dispatches
them to parse / bind / execute / utility / fastpath / copy paths. Owns the
top-level error recovery `sigsetjmp` and the per-message memory-context
lifecycle. [from-comment] `:1-17`

## Mental model

- **One backend process = one client.** `PostgresMain` is the bottom of the
  exception stack; it never returns. `:4274, :4596-4597` (`PG_exception_stack
  = &local_sigjmp_buf`).
- **`MessageContext` is reset every iteration** — each command message gets
  fresh allocator state. `:4441-4443, :4628-4629`.
- **`TopMemoryContext`** holds long-lived per-backend state (Port, prepared
  statements, plan caches). `PostmasterContext` is deleted right after
  `InitPostgres` completes. `:4385-4392`.
- **Extended-query protocol** carries state in **unnamed** + **named**
  prepared statements and portals (`CachedPlanSource`, `Portal`). Mid-extended-
  query errors cause `ignore_till_sync = true` so we skip to next Sync.
  `:4569-4574`.

## Lifecycle entry

`BackendMain` (`backend_startup.c:76`) does `BackendInitialize` (read
startup packet, auth), `InitProcess` (allocate PGPROC), then calls
`PostgresMain(dbname, user)`. `:124` of backend_startup.c.

`PostgresMain` (`postgres.c:4274`):

1. Install per-backend signal handlers (different for walsender vs regular).
   `:4303-4342` — `SIGINT→StatementCancelHandler`, `SIGTERM→die`,
   `SIGQUIT→quickdie` (under postmaster) or `die` (standalone).
2. `BaseInit()` (`:4345`).
3. Generate random cancel key. `:4354-4368`.
4. **`InitPostgres(dbname, …)`** (`:4379`) — connect to DB, load catalogs,
   load HBA, etc. *This is the long-running setup; anything DB-touching
   belongs in InitPostgres, not here.* [from-comment] `:4372-4378`.
5. Delete `PostmasterContext`. `:4388-4391`.
6. Send BackendKeyData. `:4422-4429`.
7. Create `MessageContext` + `row_description_context`. `:4441-4456`.
8. Fire login event triggers. `:4459`.
9. `sigsetjmp(local_sigjmp_buf, 1)` — error recovery landing pad.
   `:4483-4594`. On longjmp:
   - `disable_all_timeouts`, `QueryCancelPending = false`.
   - `pq_comm_reset`, `EmitErrorReport`.
   - `AbortCurrentTransaction`, `PortalErrorCleanup`,
     `ReplicationSlotRelease/Cleanup`, `jit_reset_after_error`.
   - Switch back to `MessageContext`, `FlushErrorState`.
   - If `pq_is_reading_msg()` mid-error → `ereport(FATAL, "protocol sync lost")`.
10. Set `PG_exception_stack = &local_sigjmp_buf`. `:4597`.
11. **Main loop** `for(;;)` at `:4606` — reset `MessageContext`, read a
    message via `ReadCommand`, dispatch on first byte.

## Dispatch (the first-byte switch — `:4700+`)

| Byte | Meaning | Handler |
|---|---|---|
| `Q` | Simple Query | `exec_simple_query(query_string)` (`:1029`) |
| `P` | Parse | `exec_parse_message` (`:1406`) |
| `B` | Bind | `exec_bind_message` (`:1640`) |
| `E` | Execute | `exec_execute_message(portal, max_rows)` (`:2122`) |
| `F` | Function call | `HandleFunctionRequest` (`fastpath.c:188`) |
| `C` | Close | drop portal or prepared stmt |
| `D` | Describe | `exec_describe_*` |
| `H` | Flush | `pq_flush` |
| `S` | Sync | `finish_xact_command` + clear ignore_till_sync |
| `X`, `EOF` | Terminate | clean exit |
| `d`, `c`, `f` | COPY data/done/fail | passed to COPY state machine |

## `exec_simple_query` (`:1029-1400+`)

Per the textbook simple-query pipeline:

1. `pgstat_report_activity(STATE_RUNNING)`, `start_xact_command`,
   `drop_unnamed_stmt`. `:1043-1071`
2. `pg_parse_query(query_string)` → `List<RawStmt*>`. `:1082`
3. If multiple stmts, wrap in an **implicit transaction block**.
   `:1099-1107`
4. For each raw stmt: `CreateCommandTag`, `BeginCommand`, parse-analysis +
   rewrite + plan, build a `Portal`, `PortalStart` (snapshot acquired),
   `PortalRun(FETCH_ALL, dest)`, `PortalDrop`, `EndCommand`.

## `exec_execute_message` (`:2122-2400+`)

Extended-query Execute step on an existing portal:

1. `GetPortalByName(portal_name)`. `:2148`
2. Special-case empty query → `NullCommand`. `:2158-2163`
3. Set `pgstat` query/plan id from the portal's stmts. `:2188-2210`
4. `CreateDestReceiver(DestRemoteExecute)`. `:2220+`
5. `PortalRun(portal, max_rows, false /* isTopLevel */, ...)`.
6. If portal finished, drop it; otherwise leave it open for next Execute.

## Per-iteration memory-context discipline (load-bearing)

`MessageContext` is `Reset` at the top of the loop (`:4629`). Everything
allocated by parse / plan for **this message** lives in (or hangs off)
`MessageContext`. The portal has its own `portalContext` child of
`TopPortalContext`, so its lifetime is independent. `TopMemoryContext`
itself is essentially never reset under PostgresMain — only across error
recovery via the sigsetjmp landing.

## Signal handlers (this file)

| Symbol | Triggered by | Effect |
|---|---|---|
| `quickdie` (`:2927`) | SIGQUIT under postmaster | `_exit(2)` — emergency, no atexit |
| `die` (`:3024`) | SIGTERM | set ProcDiePending; latch |
| `StatementCancelHandler` (`:3065`) | SIGINT | set QueryCancelPending; latch |
| `FloatExceptionHandler` (`:3082`) | SIGFPE | ereport(ERROR) |
| `HandleRecoveryConflictInterrupt` (`:3098`) | procsignal | flag recovery-conflict reason |
| `ProcessInterrupts` (`:3362`) | called from `CHECK_FOR_INTERRUPTS()` everywhere | the central interrupt-drain |

## Interactions

- Parser: `parser/parser.c::raw_parser` via `pg_parse_query`.
- Analyzer: `parser/analyze.c::parse_analyze*` via `pg_analyze_and_rewrite_*`.
- Planner: `optimizer/optimizer.c::planner` via `pg_plan_query`.
- Executor / portals: `tcop/pquery.c`.
- Utility statements: `tcop/utility.c::ProcessUtility`.
- Output destinations: `tcop/dest.c`.
- Function fastpath: `tcop/fastpath.c`.
- Auth + startup packet (called pre-PostgresMain): `tcop/backend_startup.c`.

## Open questions

- Detailed walk of the bind+describe extended-query path (params/format
  codes) deferred to a future query-lifecycle doc.
- Walsender variant signal setup (`WalSndSignals`) is in `replication/walsender.c`.

## Synthesized by
<!-- backlinks:auto -->
- [architecture/overview.md](../../../../architecture/overview.md)
- [subsystems/optimizer.md](../../../../subsystems/optimizer.md)
- [subsystems/parser-and-rewrite.md](../../../../subsystems/parser-and-rewrite.md)
- [subsystems/tcop.md](../../../../subsystems/tcop.md)
- [subsystems/utils-mmgr.md](../../../../subsystems/utils-mmgr.md)

## Appears in scenarios

<!-- scenarios:auto:begin -->

- [Scenario — Add a new libpq protocol message](../../../../scenarios/add-new-protocol-message.md)

<!-- scenarios:auto:end -->
