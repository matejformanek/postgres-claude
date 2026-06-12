# Subsystem: tcop (traffic cop)

## Owners (as of 2026-06-12)

- **Top committers (last 24mo):** Heikki Linnakangas (20), Peter Eisentraut (15), Michael Paquier (14), Álvaro Herrera (9)
- **Top reviewers (last 24mo):** Tom Lane (12), Michael Paquier (11), Daniel Gustafsson (9), Chao Li (8)
- **Recent landmark commits (12mo):**
  - `2c16deee2f7 (Andres Freund, 2026-04-08): instrumentation: Allocate query level instrumentation in ExecutorStart`
  - `910690415b6 (Michael Paquier, 2025-11-14): Revert "Drop unnamed portal immediately after execution to completion"`
  - `b63f25bddfe (Michael Paquier, 2026-05-11): Fix unbounded recursive handling of SSL/GSS in ProcessStartupPacket()`

See `knowledge/personas/domain-ownership.md` for the cross-subsystem index, methodology, and committer/reviewer affinity clusters.

---


- **Path:** `source/src/backend/tcop/` (7 `.c` files), `source/src/include/tcop/`
  (6 headers)
- **Verified against commit:** `4b0bf0788b066a4ca1d4f959566678e44ec93422`
  (2026-06-01 refresh anchor)
- **Confidence:** verified=14, from-README=0, from-comment=18, inferred=2,
  unverified=2 (Open Questions §9)
- **Primary README:** none. The authoritative narrative is in the top-of-file
  comments of `postgres.c` (the main loop) and `utility.c` (the dispatcher).

## 1. Purpose

`tcop` is the **per-backend traffic cop**: the layer between the
postmaster-forked child socket and the rest of the backend. It owns:

1. **The postmaster handoff** (`backend_startup.c`) — auth, startup-packet
   decode, PGPROC allocation.
2. **The main loop** (`postgres.c:PostgresMain`) — read protocol messages
   from the client, dispatch parse/bind/execute/utility/fastpath/copy,
   and host the top-level error-recovery `sigsetjmp`.
3. **The portal runner** (`pquery.c`) — wrap one or more `PlannedStmt`s in
   a `Portal`, drive `ExecutorStart`/`Run`/`Finish`/`End`, manage
   per-portal snapshots + resource owners.
4. **The utility dispatcher** (`utility.c`) — the `switch(nodeTag(parsetree))`
   that routes every non-DML statement (DDL, COPY, VACUUM, EXPLAIN,
   transaction control, SET, SECURITY LABEL, CREATE EXTENSION, …) to its
   `commands/*.c` implementation.
5. **The destination receiver factory** (`dest.c`) — abstract sink for
   executor output (client, SPI, tuplestore, COPY TO, SELECT INTO, parallel
   workers' tuple queue, explain-serialize).
6. **The function-fastpath path** (`fastpath.c`) — server side of `PQfn()`,
   bypass parse/plan/execute for a single-function call.
7. **The CommandTag table** (`cmdtag.c`) — central registry of every
   `CommandTag` enum value, used by `EndCommand`, event triggers, the
   rewriter.

**Mental model:** one backend process = one client = one `PostgresMain`
invocation that never returns. The traffic cop is the **bottom of the
exception stack** (the outermost `PG_TRY`-equivalent via `sigsetjmp`) and
the **outermost memory-context resetter** (`MessageContext` is reset
every iteration).

This synthesis distills the 7 per-file docs under
`knowledge/files/src/backend/tcop/` and the 6 header docs under
`knowledge/files/src/include/tcop/`.

## 2. Key files

| File | Lines | Role | Per-file doc |
|---|---|---|---|
| `postgres.c` | 5320 | `PostgresMain` loop, simple-query path, extended-query messages, signal handlers, `ProcessInterrupts` | [via `postgres.c.md`] |
| `pquery.c` | 1788 | Portal runner (`PortalStart`/`PortalRun`/`PortalRunFetch`/`PortalRunUtility`/`PortalRunMulti`) | [via `pquery.c.md`] |
| `utility.c` | 3823 | `ProcessUtility` / `standard_ProcessUtility` / `ProcessUtilitySlow`, `CreateCommandTag`, read-only/parallel/recovery gates | [via `utility.c.md`] |
| `dest.c` | 298 | `DestReceiver` factory (`CreateDestReceiver`), `BeginCommand`/`EndCommand`/`NullCommand`/`ReadyForQuery` | [via `dest.c.md`] |
| `fastpath.c` | 458 | `HandleFunctionRequest` — server side of `PQfn()` | [via `fastpath.c.md`] |
| `backend_startup.c` | 1157 | `BackendMain`, `BackendInitialize`, startup-packet decode, cancel-request handling | [via `backend_startup.c.md`] |
| `cmdtag.c` | 163 | `CommandTag` table + lookup/formatting helpers | [via `cmdtag.c.md`] |

### Header anchors

| Header | What it defines |
|---|---|
| `include/tcop/tcopprot.h` | `PostgresMain`, `pg_parse_query`, `pg_analyze_and_rewrite_*`, `pg_plan_query`, `pg_plan_queries`, GUCs (`log_statement`, `debug_print_*`) | [via `tcopprot.h.md`] |
| `include/tcop/pquery.h` | `Portal` runner API | [via `pquery.h.md`] |
| `include/tcop/dest.h` | `DestReceiver` contract + `CommandDest` enum | [via `dest.h.md`] |
| `include/tcop/utility.h` | `ProcessUtility`, `ProcessUtility_hook` typedef | [via `utility.h.md`] |
| `include/tcop/fastpath.h` | `HandleFunctionRequest` prototype | [via `fastpath.h.md`] |
| `include/tcop/cmdtag.h` + `cmdtaglist.h` | `CommandTag` enum + `QueryCompletion` struct + the canonical `PG_CMDTAG()` list (edit `cmdtaglist.h` to add a tag) | [via `cmdtag.h.md`] |
| `include/tcop/backend_startup.h` | `BackendStartupData`, `ConnectionTiming` | (covered in `backend_startup.c.md`) |

## 3. Key data structures

### `Port` (`MyProcPort`)

Per-backend connection state (in `libpq/libpq-be.h`, not tcop's own
header). Holds the client socket, remote host/port, database/user name,
GUC overrides from startup packet, SSL/GSSAPI state, HBA match record.
Set up by `BackendInitialize` in `pq_init` (`backend_startup.c:177`).
Lives in `TopMemoryContext` for the backend's whole life.

### `Portal` (`portalmem.c` + `pquery.c`)

Runtime-visible container around one or more `PlannedStmt`s + a
`QueryDesc` + an `ActiveSnapshot` + a `ResourceOwner` + its own memory
context (`portalContext`).

- `name` — empty for unnamed (extended-query) portal, non-empty for cursors.
- `strategy` — `PORTAL_ONE_SELECT` / `PORTAL_ONE_RETURNING` /
  `PORTAL_ONE_MOD_WITH` / `PORTAL_UTIL_SELECT` / `PORTAL_MULTI_QUERY`,
  chosen by `ChoosePortalStrategy` (`pquery.c:206`).
- `status` — `PORTAL_NEW` → `PORTAL_DEFINED` → `PORTAL_READY` →
  `PORTAL_ACTIVE` → `PORTAL_DONE` / `PORTAL_FAILED`.
- `cursorOptions` — `CURSOR_OPT_HOLD`, `CURSOR_OPT_SCROLL`,
  `CURSOR_OPT_BINARY`, etc.
- `tupDesc`, `formats[]` — output row description + per-column format codes.
- `holdContext`, `holdSnapshot` — for `WITH HOLD` cursors that survive
  the transaction. `holdContext` is a SIBLING of `TopPortalContext`, not
  a child — so commit doesn't drop it. [via
  `knowledge/files/src/backend/utils/mmgr/portalmem.c.md`]
- `portalSnapshot`, `setHoldSnapshot` — the per-portal snapshot scoped
  by `EnsurePortalSnapshotExists`.

`ActivePortal` (`pquery.c:36`) — global pointer to the innermost
currently-running portal. Saved/restored around each `PortalRun` via
`PG_TRY` so nesting works.

### `DestReceiver` abstraction

`dest.h:115-130`. Every receiver is a struct with `receiveSlot(slot,
self)`, `rStartup(self, op, typeinfo)`, `rShutdown(self)`,
`rDestroy(self)`, and a `mydest` tag (`CommandDest`). Concrete receivers
embed `DestReceiver` as the first field so casting from `DestReceiver*`
yields the subclass state. [from-comment] `dest.h:38-53`.

`CommandDest` enum (`dest.h`):
- `DestNone` — discard (singleton `None_Receiver` at `dest.c:91-96`).
- `DestDebug` — single-user mode tuple dump.
- `DestRemote` / `DestRemoteExecute` — V3 protocol text/binary
  (`access/common/printtup.c`).
- `DestRemoteSimple` — minimal protocol, no catalog access
  (`access/common/printsimple.c`).
- `DestSPI` — `executor/spi.c:spi_printtup`.
- `DestTuplestore` — `executor/tstoreReceiver.c`.
- `DestIntoRel` — `SELECT INTO` / `CREATE TABLE AS`
  (`commands/createas.c`).
- `DestTransientRel` — materialized-view refresh (`commands/matview.c`).
- `DestCopyOut` — `COPY ... TO STDOUT` (`commands/copy*.c`).
- `DestSQLFunction` — SQL-language function return (`executor/functions.c`).
- `DestTupleQueue` — parallel-worker → leader (`executor/tqueue.c`).
- `DestExplainSerialize` — `EXPLAIN (SERIALIZE)` (PG 17+,
  `commands/explain_dr.c`).

### `CommandTag` (`cmdtag.h` + `cmdtaglist.h`)

Enum + static data table, both generated from `cmdtaglist.h` via the
`PG_CMDTAG(tag, name, evtrgok, rwrok, rowcnt)` macro. `tag_behavior[]`
sorted by name so `GetCommandTagEnum` can binary-search. [verified-by-code]
`cmdtag.c:30-37, :83-107`.

`QueryCompletion` carries `(CommandTag, nprocessed)` — the formatted
output e.g. `"INSERT 0 5"` (the `0` is the legacy WITH-OIDS slot —
always written as 0 now for protocol compat). [from-comment]
`cmdtag.c:140-145`.

### `BackendStartupData` (`backend_startup.h`)

Postmaster → backend handoff struct: `canAcceptConnections` flag, plus
extras filled by postmaster before fork. Validated by `BackendMain`
(`backend_startup.c:80`).

### `ConnectionTiming` (`backend_startup.h`)

Per-stage timestamps for `log_connections=duration` (PG 17+) —
`pre_auth_start`, `auth_done`, `ready_for_query`, etc.

### `fp_info` (`fastpath.c:48-56`)

Per-call cache for `PQfn()` invocation: funcid, `FmgrInfo`, namespace,
rettype, argtypes[], short fname. Per-call (NOT cached across calls)
because each fastpath message is its own transaction command.
[from-comment] `fastpath.c:37-47`.

## 4. Core algorithms / control flow

### Backend lifecycle — postmaster fork to `PostgresMain`

```
postmaster_child_launch(B_BACKEND, ...)             postmaster/launch_backend.c
  └─ child_process_kinds[B_BACKEND].main_fn = BackendMain
       │
       ▼
BackendMain(startup_data)                          backend_startup.c:76
  │  ├─ validate startup_data size
  │  ├─ #ifdef EXEC_BACKEND + USE_SSL: re-init SSL
  │  ├─ BackendInitialize(socket, canAcceptConnections)  ← NO shmem
  │  │    ├─ ReserveExternalFD()
  │  │    ├─ pq_init(client_sock)
  │  │    ├─ pre-auth signal handlers + InitializeTimeouts()
  │  │    ├─ ProcessSSLStartup
  │  │    ├─ ProcessStartupPacket → MyProcPort fields
  │  │    └─ (cancel request? negotiate version?) → proc_exit(0)
  │  └─ InitProcess()                              ← FIRST shmem access
  ▼
PostgresMain(dbname, user)                         postgres.c:4274
  └─ never returns
```

[verified-by-code] `backend_startup.c:76-125`, `postgres.c:4274`.

**The "no shmem in BackendInitialize" invariant** [from-comment]
`backend_startup.c:128-139`:

> *"this code does not depend on having any access to shared memory.
> Indeed, our approach to SIGTERM/timeout handling REQUIRES that shared
> memory not have been touched yet."*

`process_startup_packet_die` is the SIGTERM handler during this window;
it does `_exit(1)` because there's nothing in shmem to clean up. If
postmaster needs FAST/IMMEDIATE shutdown while a client is hung sending
a startup packet, this is what protects us.

### Cancel request

`ProcessCancelRequestPacket` (`backend_startup.c:917`) decodes pid +
32/64-bit cancel key and calls `SendCancelRequest(pid, key)`
(`storage/ipc/procsignal.c`), then exits. The whole exchange is handled
by a `B_DEAD_END_BACKEND` so the TARGET backend's main process never
sees the cancel-channel socket.

### `PostgresMain` setup + sigsetjmp landing

`PostgresMain` (`postgres.c:4274`):

1. Install per-backend signal handlers (different for walsender vs
   regular). `:4303-4342`:
   - `SIGINT` → `StatementCancelHandler` (`:3065`).
   - `SIGTERM` → `die` (`:3024`).
   - `SIGQUIT` → `quickdie` (`:2927`) under postmaster, `die` standalone.
   - `SIGFPE` → `FloatExceptionHandler` (`:3082`).
2. `BaseInit()` (`:4345`).
3. Generate random cancel key. `:4354-4368`.
4. **`InitPostgres(dbname, ...)`** (`:4379`) — DB connect, catalogs, HBA
   load. Anything DB-touching goes there, NOT here. [from-comment]
   `:4372-4378`.
5. Delete `PostmasterContext`. `:4388-4391`.
6. Send `BackendKeyData`. `:4422-4429`.
7. Create `MessageContext` + `row_description_context`. `:4441-4456`.
8. Fire login event triggers. `:4459`.
9. **`sigsetjmp(local_sigjmp_buf, 1)` — error recovery landing pad.**
   `:4483-4594`. On longjmp:
   - `disable_all_timeouts`, `QueryCancelPending = false`.
   - `pq_comm_reset`, `EmitErrorReport`.
   - `AbortCurrentTransaction`, `PortalErrorCleanup`,
     `ReplicationSlotRelease/Cleanup`, `jit_reset_after_error`.
   - Switch back to `MessageContext`, `FlushErrorState`.
   - If `pq_is_reading_msg()` mid-error → `ereport(FATAL, "protocol
     sync lost")`.
   - If mid-extended-query, set `ignore_till_sync = true` so subsequent
     P/B/E/D are skipped until Sync. [verified-by-code] `:4569-4574`.
10. `PG_exception_stack = &local_sigjmp_buf`. `:4597`.
11. **Main loop** `for(;;)` at `:4606`:
    - `MessageContextReset`. `:4628-4629`
    - `ReadCommand` → first byte + message body.
    - Dispatch on first byte.

### First-byte dispatch (`postgres.c:4700+`)

| Byte | Meaning | Handler |
|---|---|---|
| `Q` | Simple Query | `exec_simple_query(query_string)` (`:1029`) |
| `P` | Parse | `exec_parse_message` (`:1406`) |
| `B` | Bind | `exec_bind_message` (`:1640`) |
| `E` | Execute | `exec_execute_message(portal, max_rows)` (`:2122`) |
| `F` | Function call | `HandleFunctionRequest` (`fastpath.c`) |
| `C` | Close | drop portal or prepared stmt |
| `D` | Describe | `exec_describe_*` |
| `H` | Flush | `pq_flush` |
| `S` | Sync | `finish_xact_command` + clear `ignore_till_sync` |
| `X`, EOF | Terminate | clean exit |
| `d`/`c`/`f` | COPY data/done/fail | passed to COPY state machine |

### Simple query path (`exec_simple_query`)

`postgres.c:1029-1400+`:

1. `pgstat_report_activity(STATE_RUNNING)`, `start_xact_command`,
   `drop_unnamed_stmt`.
2. `pg_parse_query(query_string)` → `List<RawStmt*>`.
3. If multiple stmts → wrap in an **implicit transaction block**.
   `:1099-1107`.
4. For each raw stmt:
   - `CreateCommandTag` (utility.c:2385).
   - `BeginCommand` (dest.c:102 — currently no-op).
   - parse-analysis + rewrite (`pg_analyze_and_rewrite_*`).
   - planning (`pg_plan_query` / `pg_plan_queries`).
   - Build a `Portal` (`PortalCreate` in `portalmem.c`).
   - `PortalStart` (acquire snapshot).
   - `PortalRun(FETCH_ALL, dest=DestRemote)`.
   - `PortalDrop`.
   - `EndCommand`.

### Extended query path

Two-stage: `Parse` creates a `CachedPlanSource` (named or unnamed),
`Bind` creates a `Portal` from that source + parameter values,
`Execute` runs `PortalRun(max_rows, ...)`.

`exec_execute_message` (`:2122-2400+`):

1. `GetPortalByName(portal_name)`. `:2148`.
2. Special-case empty query → `NullCommand`. `:2158-2163`.
3. Set `pgstat` query/plan id from the portal's stmts. `:2188-2210`.
4. `CreateDestReceiver(DestRemoteExecute)`. `:2220+`.
5. `PortalRun(portal, max_rows, false /* isTopLevel */, ...)`.
6. If portal finished, drop it; otherwise leave it open for next
   Execute.

**`ignore_till_sync`** is the extended-query error recovery: mid-extended
errors flip it true and subsequent P/B/E/D/Close/Describe are skipped
until Sync, after which the backend can accept new commands.

### Portal runner — `pquery.c`

`PortalStart` (`pquery.c:430`):
- Save/restore `ActivePortal`, `CurrentResourceOwner`, `PortalContext`.
- Push `PortalContext` as current memory context.
- Initialize executor state via `CreateQueryDesc` + `ExecutorStart`.
- Acquire `ActiveSnapshot` (via `GetActiveSnapshot` or push a fresh one).
- Set `tupDesc`.
- Set `status = PORTAL_READY`.

`PortalRun` (`pquery.c:681`) — dispatcher:
- Save/restore globals via `PG_TRY`.
- Push `PortalContext`.
- Switch on `portal->strategy`:
  - `PORTAL_ONE_SELECT` → `PortalRunSelect` (`pquery.c:860`) →
    `ExecutorRun(forward, count, dest)`.
  - `PORTAL_ONE_RETURNING` / `PORTAL_ONE_MOD_WITH` / `PORTAL_UTIL_SELECT`
    → `FillPortalStore` (drain into `Tuplestorestate`) + serve from
    store on subsequent calls.
  - `PORTAL_MULTI_QUERY` → `PortalRunMulti` (`pquery.c:1182`).
- On error: `status = PORTAL_FAILED`; cleanup in `PortalErrorCleanup`
  called from PostgresMain's sigsetjmp.

`PortalRunUtility` (`pquery.c:1118`) — wraps a single utility statement
by calling `ProcessUtility`.

`PortalRunMulti` (`pquery.c:1182`) — drives a list of statements as the
portal's execution unit; transaction-control + ordinary stmts interleave
here. The implementation of multi-stmt simple-query lives here.

`PortalRunFetch` (`pquery.c:1374`) — cursor `FETCH` with
direction/count.

`EnsurePortalSnapshotExists` (`pquery.c:1761`) — lazily attach
`ActiveSnapshot` to a portal. Required for cursors that need to outlive
their statement.

### Utility dispatcher — `utility.c`

`ProcessUtility(pstmt, queryString, ...)` (`utility.c:504`) — public
entry. Calls `ProcessUtility_hook` (`:72`) if set (pg_stat_statements
and friends), otherwise `standard_ProcessUtility`.

**Two-tier split** [from-comment] `utility.c:533-545`:

- **`standard_ProcessUtility`** (`:548`) handles commands with **no
  event-trigger support**: transaction control, SET, NOTIFY, LISTEN,
  CHECKPOINT, etc. Done inline.
- **`ProcessUtilitySlow`** (`:1094`) handles commands that **do** have
  event-trigger support. Necessary because event-trigger cache refresh
  needs a transaction context, which isn't safe to assume during
  `START TRANSACTION`.

`ProcessUtility_hook` (`:72`) — extension hook (chained). pg_stat_statements
uses this to see every utility statement.

### Read-only / parallel / recovery gates

`CommandIsReadOnly(pstmt)` (`utility.c:96`) for DML `PlannedStmt`s.

`ClassifyUtilityCommandAsReadOnly(parsetree)` (`:130`) returns a
bitmask:
- `COMMAND_OK_IN_READ_ONLY_TXN`
- `COMMAND_OK_IN_PARALLEL_MODE`
- `COMMAND_OK_IN_RECOVERY`

`:577-591` then calls the matching `PreventCommandIf*` helpers
(`:409, :427, :446`). `CheckRestrictedOperation` (`:464`) gates
operations forbidden in security-restricted contexts.

### Routing table (`standard_ProcessUtility` switch at `:597+`)

| Node | Module |
|---|---|
| `T_TransactionStmt` | inline (`BeginTransactionBlock`, `EndTransactionBlock`, …) |
| `T_VariableSetStmt`, `T_VariableShowStmt` | `commands/variable.c` |
| `T_VacuumStmt` | `commands/vacuum.c::ExecVacuum` |
| `T_CopyStmt` | `commands/copy.c::DoCopy` |
| `T_ExplainStmt` | `commands/explain.c::ExplainQuery` |
| `T_NotifyStmt` / `T_ListenStmt` | `commands/async.c` |
| `T_LockStmt` | `commands/lockcmds.c` |
| `T_CheckPointStmt` | `xlog.c::RequestCheckpoint` |
| `T_PrepareStmt` / `T_ExecuteStmt` / `T_DeallocateStmt` | `commands/prepare.c` |
| `T_CreateStmt` / `T_AlterTableStmt` / `T_DropStmt` / DDL family | `ProcessUtilitySlow` → `commands/tablecmds.c` and siblings |

### Function fastpath — `fastpath.c`

`HandleFunctionRequest(msgBuf)` (`fastpath.c:188`) is the dispatch entry
called from `PostgresMain` on `'F'`:

1. Read function OID and format codes from `msgBuf`.
2. `fetch_fp_info(funcid, &fp_info)` (`:119`) — syscache lookup, ACL
   check, build `FmgrInfo`.
3. Snapshot setup (`PushActiveSnapshot`).
4. `parse_fcall_arguments` (`:329`) decodes args (text or binary per
   format codes).
5. `FunctionCallInvoke(fcinfo)`.
6. `SendFunctionResult` (`:67`) sends `'V'` reply.
7. Pop snapshot, command-complete.

**No caching of function info across calls** — an earlier attempt was
removed because each fastpath message is its own transaction command, so
cached `FmgrInfo` could never be reused safely. [from-comment]
`fastpath.c:37-47`.

### Destination receivers — `dest.c`

`CreateDestReceiver(CommandDest)` (`:112-162`) — switch that returns the
right (static or freshly palloc'd) receiver. Stateless receivers
(`donothingDR`, `debugtupDR`, `printsimpleDR`, `spi_printtupDR`) are
file-scope singletons. Configurable ones (`DestIntoRel`, `DestCopyOut`,
`DestTupleQueue`) are returned with defaults; caller patches in extras
via setters (e.g. `SetTuplestoreDestReceiverParams`).

Per-statement helpers:
- `BeginCommand(commandTag, dest)` (`:102`) — currently no-op; legacy
  hook spot.
- `EndCommand(qc, dest, force_undecorated)` (`:204`) /
  `EndCommandExtended` (`:169`) — format `CommandComplete` tag (e.g.
  `"INSERT 0 5"` via `BuildQueryCompletionString` in `cmdtag.c`) and
  send.
- `EndReplicationCommand` (`:216`) — stripped-down version for
  replication commands.
- `NullCommand(dest)` (`:229`) — send `EmptyQueryResponse`.
- `ReadyForQuery(dest)` (`:267`) — send `'Z'` with
  `TransactionBlockStatusCode()` and `pq_flush()`.

### Signal handling

Per-backend handlers installed at `PostgresMain` (`postgres.c:4303-4342`):

| Symbol | Triggered by | Effect |
|---|---|---|
| `quickdie` (`:2927`) | SIGQUIT under postmaster | `_exit(2)` — emergency, no atexit |
| `die` (`:3024`) | SIGTERM | set `ProcDiePending`; latch |
| `StatementCancelHandler` (`:3065`) | SIGINT | set `QueryCancelPending`; latch |
| `FloatExceptionHandler` (`:3082`) | SIGFPE | `ereport(ERROR)` |
| `HandleRecoveryConflictInterrupt` (`:3098`) | procsignal | flag recovery-conflict reason |

**`ProcessInterrupts`** (`postgres.c:3362`) is the central interrupt
drain, called from `CHECK_FOR_INTERRUPTS()` everywhere. It checks
`ProcDiePending`, `QueryCancelPending`, `IdleInTransactionSessionTimeoutPending`,
recovery-conflict flags, etc. — and raises `ereport(FATAL/ERROR)` as
appropriate.

### Memory-context discipline (load-bearing)

[from-comment] `postgres.c:4441-4629`:

- **`TopMemoryContext`** holds long-lived per-backend state (Port,
  prepared statements, plan caches). Essentially never reset under
  `PostgresMain`.
- **`PostmasterContext`** is deleted right after `InitPostgres`
  completes. `:4388-4391`.
- **`MessageContext`** is RESET every iteration of the main loop
  (`:4628-4629`). Everything allocated by parse/plan for the current
  message lives here (or hangs off it).
- **`portalContext`** (per portal, child of `TopPortalContext`) has its
  own lifetime — independent of `MessageContext`. Dropped by
  `PortalDrop`.
- **`holdContext`** (for `WITH HOLD` cursors) is a SIBLING of
  `TopPortalContext`, NOT a child, so transaction commit doesn't drop
  it.

## 5. Invariants

- INV-tcop-1: **One backend = one client = one `PostgresMain`.** It
  never returns; it's the bottom of the exception stack via
  `sigsetjmp`. [verified-by-code] `postgres.c:4274, :4596-4597`.
- INV-tcop-2: **`MessageContext` is reset every iteration.**
  Everything allocated by parse/plan for the current message lives in
  (or hangs off) it. [verified-by-code] `postgres.c:4441-4443, :4628-4629`.
- INV-tcop-3: **`BackendInitialize` MUST NOT touch shared memory.**
  Approach to SIGTERM/timeout during auth requires this; `_exit(1)` is
  safe because there's nothing in shmem to clean up. [from-comment]
  `backend_startup.c:128-139`.
- INV-tcop-4: **`InitProcess` is the FIRST shmem access** after
  `BackendInitialize`. Allocates PGPROC. Must precede any LWLock /
  shmem access. [verified-by-code] `backend_startup.c:113-116`.
- INV-tcop-5: **The sigsetjmp landing must `disable_all_timeouts`
  BEFORE `EmitErrorReport`** to prevent cascading interrupts during
  cleanup. [verified-by-code] `postgres.c:4483-4594`.
- INV-tcop-6: **Mid-extended-query errors set `ignore_till_sync = true`**
  so subsequent P/B/E/D/Close/Describe are skipped until Sync.
  [verified-by-code] `postgres.c:4569-4574`.
- INV-tcop-7: **`pq_is_reading_msg()` mid-error triggers FATAL
  "protocol sync lost"** — can't safely recover at that point.
  [verified-by-code] `postgres.c:4483-4594`.
- INV-tcop-8: **Anything DB-touching belongs in `InitPostgres`,
  NOT in `PostgresMain` setup.** [from-comment] `postgres.c:4372-4378`.
- INV-tcop-9: **`PostmasterContext` is deleted right after
  `InitPostgres` completes** — so its lifetime is bounded by the
  postmaster-fork → HBA-data-no-longer-needed window. [verified-by-code]
  `postgres.c:4388-4391`.
- INV-tcop-10: **`MyProcPort` is set up in `TopMemoryContext`** so it
  outlives all per-message resets. [verified-by-code]
  `backend_startup.c:177`.
- INV-tcop-11: **`whereToSendOutput = DestRemote`** only AFTER
  `pq_init`, so `ereport` can talk to the client. [verified-by-code]
  `backend_startup.c`.
- INV-tcop-12: **Cancel requests are handled by `B_DEAD_END_BACKEND`,
  not the target backend.** Cancel never sees the target's main
  socket. [verified-by-code] `backend_startup.c:917`.
- INV-tcop-13: **`ActivePortal` is saved/restored around every
  `PortalRun`** via `PG_TRY`, so nesting works. [verified-by-code]
  `pquery.c:36, :430-460+`.
- INV-tcop-14: **`PortalContext` is pushed as current memory context
  during `PortalRun`**, so palloc inside the executor lands there.
  [verified-by-code] `pquery.c:430-460+`.
- INV-tcop-15: **`receiveSlot` must be called with the same TupleDesc
  that was given to `rStartup`.** [from-comment] `dest.h:107-111`.
- INV-tcop-16: **Concrete DestReceivers embed `DestReceiver` as the
  first field** so casting from `DestReceiver*` yields the subclass
  state. [from-comment] `dest.h:38-53`.
- INV-tcop-17: **`utility.c` is split into `standard_ProcessUtility`
  (no event triggers) and `ProcessUtilitySlow` (has event triggers)**
  because event-trigger cache refresh needs a transaction context.
  [from-comment] `utility.c:533-545`.
- INV-tcop-18: **`ProcessUtility_hook` is chained** — each extension
  must call the previous hook (or `standard_ProcessUtility`) if it
  doesn't terminate the chain. [verified-by-code] `utility.c:519-526`.
- INV-tcop-19: **`tag_behavior[]` is sorted by name** so
  `GetCommandTagEnum` can binary-search. [verified-by-code]
  `cmdtag.c:83-107`.
- INV-tcop-20: **Adding a new statement type requires editing
  `cmdtaglist.h`** (the canonical `PG_CMDTAG()` list). The enum and
  data table are generated from it. [from-comment]
  `cmdtag.c:30-37`.
- INV-tcop-21: **`fp_info` is NOT cached across `PQfn` calls** because
  each call is its own transaction command. [from-comment]
  `fastpath.c:37-47`.
- INV-tcop-22: **`PortalRun` on a portal that needs `ActiveSnapshot`
  but doesn't have one lazily attaches via `EnsurePortalSnapshotExists`.**
  [verified-by-code] `pquery.c:1761`.
- INV-tcop-23: **`WITH HOLD` cursor `holdContext` is a SIBLING of
  `TopPortalContext`, not a child** — so commit doesn't drop it. [via
  `knowledge/files/src/backend/utils/mmgr/portalmem.c.md`]

## 6. Entry points (how the rest of the backend calls in)

External callers:
- `postmaster/launch_backend.c` — invokes `BackendMain` for backend kinds.
- `replication/walsender.c` — installs different signal handlers
  (`WalSndSignals`) but reuses `PostgresMain`'s loop for replication
  commands.
- Single-user / standalone mode — `main/main.c` → `PostgresMain` with no
  postmaster.

Internal entry points used widely:
- `pg_parse_query` (`tcopprot.h`) — text → `List<RawStmt*>`.
- `pg_analyze_and_rewrite_*` family — `RawStmt` → `List<Query>`.
- `pg_plan_query`, `pg_plan_queries` — `Query` → `PlannedStmt`.
- `ProcessUtility(pstmt, ...)` (`utility.c:504`) — utility dispatch.
- `ProcessUtility_hook` — registered by extensions.
- `PortalStart`, `PortalRun`, `PortalRunFetch`, `PortalRunUtility`,
  `PortalRunMulti` — portal runner API.
- `CreateDestReceiver(commandDest)` — receiver factory.
- `BeginCommand`, `EndCommand`, `EndCommandExtended`, `NullCommand`,
  `ReadyForQuery` — command framing.
- `HandleFunctionRequest` — fastpath entry from `PostgresMain`.
- `GetCommandTagName`, `GetCommandTagEnum`,
  `BuildQueryCompletionString` — `CommandTag` helpers.

Called by tcop:
- `parser/parser.c::raw_parser` (via `pg_parse_query`).
- `parser/analyze.c::parse_analyze_*` (via `pg_analyze_and_rewrite_*`).
- `rewrite/rewriteHandler.c::QueryRewrite`.
- `optimizer/plan/planner.c::planner` (via `pg_plan_query`).
- `executor/execMain.c::ExecutorStart/Run/Finish/End`.
- `commands/*.c` — every utility.
- `utils/mmgr/portalmem.c` — portal storage.
- `utils/time/snapmgr.c` — snapshot acquire/release.
- `libpq/be-secure*.c` — SSL/GSS.

## 7. What the tests tell us

### Regression (`src/test/regress/`)

- `prepared_xacts.sql`, `prepare.sql` — PREPARE/EXECUTE/DEALLOCATE.
- `transactions.sql` — transaction control inside multi-stmt simple
  queries; implicit-block behavior.
- `cursor.sql`, `portals.sql` — cursor + portal semantics, `WITH HOLD`.
- `errors.sql` — error recovery + protocol-sync behavior.
- `event_trigger.sql` — `standard_ProcessUtility` vs `ProcessUtilitySlow`
  split exercised here.

### TAP (`src/test/authentication/t/`, `src/test/ssl/t/`, `src/test/recovery/t/`)

- Authentication / SSL — exercise `backend_startup.c` extensively.
- Cancel-request paths exercised via `pg_terminate_backend` /
  `pg_cancel_backend`.

### Isolation (`src/test/isolation/`)

- `multiple-cursors`, `eval-plan-qual`, others — cursor semantics under
  concurrency.

### `pg_amcheck` + `pg_dump`

- Use the SQL SRF + extended-query protocol heavily — implicit smoke
  test of `exec_parse/bind/execute_message`.

## 8. Gotchas / sharp edges

- **`PostgresMain` is the bottom of the exception stack.** Any code
  that runs outside an explicit `PG_TRY` lands here on error. If you're
  adding interrupt-sensitive logic, think about the longjmp landing.
- **`MessageContext` reset every iteration** — anything you want to keep
  across messages must be in a longer-lived context (TopMemoryContext,
  CacheMemoryContext, etc.) or copy-on-demand.
- **`MyProcPort` is in TopMemoryContext** — outlives every reset.
- **`PostmasterContext` is gone after `InitPostgres`** — HBA data and
  startup-packet GUCs must be consumed or copied before that.
- **The "no shmem in BackendInitialize" invariant** — if you add a
  pre-auth feature that needs shmem, you've broken the SIGTERM model.
  Defer to after `InitProcess`.
- **`InitProcess` allocates PGPROC** — the FIRST shmem access; any
  pre-PGPROC LWLock attempt deadlocks the cluster.
- **`ProcessInterrupts` is called from `CHECK_FOR_INTERRUPTS()`
  EVERYWHERE.** Long-running C code without it is unresponsive to
  cancel/terminate.
- **`quickdie` does `_exit(2)`** — no atexit, no cleanup, no
  `proc_exit`. Designed for emergency only. If you add resource that
  needs cleanup, `quickdie` won't run it; the postmaster has to clean
  shmem after.
- **Extended-query `ignore_till_sync` is the entire error-recovery
  mechanism** for extended protocol. Skipping it (or not setting it)
  leaves the backend desynced and triggers FATAL on next message.
- **`ProcessUtility_hook` MUST chain.** Extensions that fail to call the
  previous hook will silently drop every utility statement.
- **`standard_ProcessUtility` vs `ProcessUtilitySlow` split** — adding
  event-trigger support to a previously-no-trigger command moves it
  between the two; the routing table must be updated.
- **`CommandTag` adds go in `cmdtaglist.h`, not `cmdtag.c`.** The data
  table is generated from the list.
- **DestReceivers are sometimes file-scope singletons** (e.g.
  `None_Receiver`). Don't try to free them after `rDestroy`.
- **`receiveSlot` TupleDesc** must match the one given to `rStartup` —
  changing it mid-stream produces garbled output or crashes.
- **`fastpath.c` doesn't cache `FmgrInfo` across calls** by design.
  Don't add a global cache — earlier attempts were removed for
  correctness reasons.
- **`PortalContext` is pushed during `PortalRun`** so palloc inside the
  executor lands there. If you call code that expects
  `CurrentMemoryContext == MessageContext`, switch explicitly.
- **`WITH HOLD` cursors** — `holdContext` is a SIBLING of
  `TopPortalContext`. Don't try to make it a child or commit will drop
  the cursor data.
- **Implicit-transaction-block for multi-stmt simple queries** — DDL +
  DML inside a single semicolon-separated query string runs as one
  transaction. Surprising for users expecting auto-commit per statement.
- **`whereToSendOutput`** must be set before `ereport` is allowed to
  send to the client. Pre-auth errors that hit `ereport(ERROR)` before
  `pq_init` won't reach the client.
- **`disable_all_timeouts` MUST come first in the sigsetjmp landing** —
  otherwise the timeout subsystem can re-fire during cleanup and
  re-longjmp.
- **`MessageContext` switch back at end of sigsetjmp** — without it,
  the next iteration's `MessageContextReset` would have unpredictable
  effects.

## 9. Open questions

- O1: **Detailed extended-query bind+describe path** (parameter formats,
  RowDescription bytes) deferred to a future query-lifecycle doc. The
  per-file `postgres.c.md` notes this. [unverified]
- O2: **Walsender signal-handler variant** (`WalSndSignals`) is in
  `replication/walsender.c`, not here. The interaction between
  walsender's loop reusing `PostgresMain`'s patterns and its own
  shutdown machinery is documented in [via
  `knowledge/subsystems/replication.md`]. [verified-by-code]
- O3: **Implicit-block boundary semantics for multi-stmt simple query
  with DDL** — does `CREATE TABLE; INSERT;` see the table from the same
  command? Spot-check needed. [unverified]
- O4: **`EnsurePortalSnapshotExists` interaction with parallel query** —
  parallel workers inherit the leader's snapshot, but the lazy-attach
  path is on the leader. Edge cases not exhaustively documented.
  [inferred]

## 10. Related subsystems

- **Calls into:**
  - `parser/` — `pg_parse_query`, `pg_analyze_and_rewrite_*`. [via
    `knowledge/subsystems/parser-and-rewrite.md`]
  - `optimizer/` — `pg_plan_query`. [via
    `knowledge/subsystems/optimizer.md`]
  - `executor/` — `ExecutorStart`/`Run`/`Finish`/`End`. [via
    `knowledge/subsystems/executor.md`]
  - `commands/` — every `commands/*.c` dispatched by `ProcessUtility`.
  - `utils/mmgr/portalmem.c` — portal storage. [via
    `knowledge/subsystems/utils-mmgr.md`]
  - `utils/time/snapmgr.c` — snapshot acquire/release.
  - `access/transam/xact.c` — transaction control inside
    `T_TransactionStmt`.
  - `libpq/be-*.c` — wire protocol I/O.
  - `utils/error/elog.c` — `EmitErrorReport`, `FlushErrorState`.
  - `storage/ipc/procsignal.c` — `SendCancelRequest`.
  - `storage/lmgr/proc.c` — `InitProcess` (PGPROC).
    [via `knowledge/subsystems/storage-lmgr.md`]

- **Called by:**
  - `postmaster/launch_backend.c` — invokes `BackendMain`.
  - `main/main.c` — single-user mode jumps straight to `PostgresMain`.
  - `replication/walsender.c` — `exec_replication_command` is
    `PostgresMain`'s replication-command branch. [via
    `knowledge/subsystems/replication.md`]
  - SPI consumers (`executor/spi.c`) call `pg_parse_query` +
    `pg_analyze_and_rewrite_*` directly.
  - `commands/prepare.c` — `PREPARE` builds a `CachedPlanSource`
    similar to extended-query Parse, reusing tcop helpers.

- **Sibling:**
  - `postmaster/` — the fork-side of the connection lifecycle.
    [via `knowledge/files/src/backend/postmaster/postmaster.c.md`]
  - `libpq/` — frontend-protocol read/write under the hood.

## 11. Source pointers — most-cited file:line summary

| Anchor | What it establishes |
|---|---|
| `backend_startup.c:76-125` | `BackendMain` lifecycle |
| `backend_startup.c:128-139` | "No shmem in BackendInitialize" invariant |
| `backend_startup.c:113-116` | `InitProcess` is the first shmem access |
| `backend_startup.c:177` | `pq_init` + `MyProcPort` in TopMemoryContext |
| `backend_startup.c:917` | Cancel-request via B_DEAD_END_BACKEND |
| `postgres.c:1029` | `exec_simple_query` |
| `postgres.c:1406` | `exec_parse_message` |
| `postgres.c:1640` | `exec_bind_message` |
| `postgres.c:2122` | `exec_execute_message` |
| `postgres.c:2927, :3024, :3065, :3082` | `quickdie`, `die`, `StatementCancelHandler`, `FloatExceptionHandler` |
| `postgres.c:3362` | `ProcessInterrupts` (central interrupt drain) |
| `postgres.c:4274` | `PostgresMain` entry |
| `postgres.c:4303-4342` | Per-backend signal-handler setup |
| `postgres.c:4372-4378` | Anything DB-touching belongs in `InitPostgres` |
| `postgres.c:4379, :4388-4391` | `InitPostgres` + `PostmasterContext` delete |
| `postgres.c:4441-4456` | `MessageContext` + `row_description_context` |
| `postgres.c:4483-4594` | sigsetjmp landing |
| `postgres.c:4569-4574` | `ignore_till_sync` mid-extended-query |
| `postgres.c:4596-4597` | `PG_exception_stack = &local_sigjmp_buf` |
| `postgres.c:4606, :4628-4629` | Main loop + `MessageContextReset` |
| `pquery.c:36` | `ActivePortal` global |
| `pquery.c:206` | `ChoosePortalStrategy` |
| `pquery.c:430, :620, :681, :860` | `PortalStart`/`PortalSetResultFormat`/`PortalRun`/`PortalRunSelect` |
| `pquery.c:1118, :1182, :1374` | `PortalRunUtility`/`PortalRunMulti`/`PortalRunFetch` |
| `pquery.c:1761` | `EnsurePortalSnapshotExists` |
| `utility.c:504, :548, :1094` | `ProcessUtility` / `standard_ProcessUtility` / `ProcessUtilitySlow` |
| `utility.c:519-526` | `ProcessUtility_hook` |
| `utility.c:533-545` | Two-tier split rationale |
| `utility.c:577-591, :409, :427, :446, :464` | Read-only / parallel / recovery / restricted gates |
| `utility.c:597+` | The `switch(nodeTag)` routing table |
| `utility.c:2385` | `CreateCommandTag` |
| `dest.c:91-96, :112-162, :204, :267` | `None_Receiver`, `CreateDestReceiver`, `EndCommand`, `ReadyForQuery` |
| `dest.h:38-53, :107-111, :115-130` | Receiver contract |
| `fastpath.c:37-47` | No `FmgrInfo` cache rationale |
| `fastpath.c:188` | `HandleFunctionRequest` |
| `cmdtag.c:30-37, :83-107, :140-145` | `tag_behavior[]` table + `BuildQueryCompletionString` |

## Synthesized over

This synthesis distills the 7 per-file docs under
`knowledge/files/src/backend/tcop/` and the 6 header docs under
`knowledge/files/src/include/tcop/`. See
[[knowledge/architecture/query-lifecycle.md]] for the cross-subsystem
narrative of how a SQL statement flows from `Q`/`P`/`B`/`E` through
parser → rewriter → planner → executor, and
[[knowledge/subsystems/parser-and-rewrite.md]],
[[knowledge/subsystems/optimizer.md]],
[[knowledge/subsystems/executor.md]] for the layers tcop calls into.
