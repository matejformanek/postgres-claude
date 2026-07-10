# pldebugger — a runtime PL/pgSQL step debugger that freezes a live backend inside the executor and drives it over a backend-to-backend socket

> Ideology note produced by the `pg-extension-anthropologist` cloud routine.
> Repo: `EnterpriseDB/pldebugger` @ branch `master` (EXTENSION=`pldbgapi`,
> MODULE_big=`plugin_debugger`). All `file:line` cites below point into that
> repo (not `source/`), since this doc characterizes an *external* extension's
> divergence from core idioms. Cites verified against the files fetched on
> 2026-07-09 (see Sources footer).
>
> **Read alongside `[[knowledge/ideologies/plpgsql_check]]`.** pldebugger and
> plpgsql_check are the two poles of the same hook: both install a
> `PLpgSQL_plugin` into the running PL/pgSQL interpreter, but plpgsql_check
> *type-checks a compiled tree without executing it* (static, offline), while
> pldebugger *rides the live executor and stops it between statements*
> (dynamic, online). The contrast is drawn explicitly throughout.

## Domain & purpose

pldebugger is the server-side half of the pgAdmin PL/pgSQL debugger: "a set of
shared libraries which implement an API for debugging pl/pgsql functions"
(`README-pldebugger.md:3`) `[from-README]`. It lets a GUI client set
breakpoints on a function, then **step through that function line-by-line in a
real backend**, inspecting and modifying live variable values as the code runs.
Where plpgsql_check answers "will this function be correct?" by walking a parse
tree in a fake execution environment, pldebugger answers "what is this function
actually doing *right now*?" by pausing a genuine `PLpgSQL_execstate` mid-flight
and handing control to a human. It is one of the very few PostgreSQL extensions
whose core behavior is to **make one backend block, indefinitely, on the whim of
a second backend**.

The moving parts are three processes (`README-pldebugger.md:48-78`,
`pldbgapi.c:1-31`) `[from-README][from-comment]`:

- **the target backend** — the ordinary session running the code being debugged;
  `plugin_debugger.so` is loaded into it (via `shared_preload_libraries`) and it
  hosts the "debugger server";
- **the proxy backend** — a *second* backend the GUI connects to over normal
  libpq; it runs the `pldbg_*` SQL API functions and relays commands to the
  target;
- **the client** — pgAdmin, which speaks only plain SQL to the proxy and never
  sees the private target↔proxy protocol.

## How it hooks into PG

### The `PLpgSQL_plugin` rendezvous — the one sanctioned entry point

Like plpgsql_check, pldebugger reaches the PL/pgSQL interpreter through the
**rendezvous-variable** mechanism, not through a linker symbol. In
`plpgsql_debugger_init()` it fetches the well-known pointer slot and stores the
address of its own callback struct into it (`plpgsql_debugger.c:132-138`)
`[verified-by-code]`:

```c
PLpgSQL_plugin ** var_ptr = (PLpgSQL_plugin **) find_rendezvous_variable( plugin_name );
*var_ptr = &plugin_funcs;
```

`plugin_name` is `"PLpgSQL_plugin"` (or `"spl_plugin"` for the EDB variant)
(`plpgsql_debugger.c:93-97`) `[verified-by-code]`. When the plpgsql library
starts up it reads that same rendezvous slot and, if non-NULL, calls the
installed callbacks — so pldebugger's coupling to plpgsql internals runs through
a channel plpgsql *deliberately exposes*. This is the sanctioned part; almost
everything else pldebugger touches (the layout of `PLpgSQL_execstate`,
`estate->datums[]`, `estate->plugin_info`) is unsanctioned struct-layout
coupling obtained by `#include "plpgsql.h"` (`plpgsql_debugger.c:34`) and a
build-time `-I$(top_srcdir)/src/pl/plpgsql/src` (`Makefile:40-41`)
`[verified-by-code]`.

### The callback set — only two of five slots wired, plus a *return* channel

The plugin struct is initialized as (`plpgsql_debugger.c:99`) `[verified-by-code]`:

```c
static PLpgSQL_plugin plugin_funcs = { dbg_startup, NULL, NULL, dbg_newstmt, NULL };
```

Mapped onto `PLpgSQL_plugin`'s fields, that wires **`func_setup` =
`dbg_startup`** and **`stmt_beg` = `dbg_newstmt`**, leaving `func_beg`,
`func_end`, and `stmt_end` NULL `[inferred]` (from the struct's documented field
order; the file-local comment at `:993-998` confirms the last two slots
—`error_callback`/`assign_expr`— are the interpreter-filled ones). Two design
notes fall out of this:

- **`dbg_startup` is a cheap gate.** On every function entry it asks
  `breakpointsForFunction(func->fn_oid)` and, unless there is a breakpoint or a
  pending step-into, sets `estate->plugin_info = NULL` and returns immediately
  (`plpgsql_debugger.c:954-973`) `[verified-by-code]`. The whole design is
  organized around the comment "it is very important that this function should
  impose negligible overhead when a debugger client is *not* attached"
  (`plpgsql_debugger.c:1354-1357`) `[from-comment]`.
- **The plugin struct is bidirectional.** The PL interpreter writes *back* into
  `plugin_funcs.error_callback` and `plugin_funcs.assign_expr`, which pldebugger
  then copies into its per-frame context (`plpgsql_debugger.c:999-1000`)
  `[verified-by-code]`. `error_callback` is later used as an identity token to
  recognize which `error_context_stack` frames are PL/pgSQL frames
  (`plpgsql_frame_belongs_to_me`, `:145-149`); `assign_expr` is borrowed to
  implement variable "deposit" (below). This is a divergence from the normal
  one-way hook contract: pldebugger doesn't just receive callbacks, it *harvests
  interpreter-internal function pointers back out of the same struct* rather than
  resolving them as symbols — a gentler dependency than plpgsql_check's
  `load_external_function` dlsym of seven `plpgsql_*` entry points
  (contrast `[[knowledge/ideologies/plpgsql_check]]` §1).

### `_PG_init` and shared memory

`_PG_init` walks a small table of `debugger_language_t` vtables (PL/pgSQL, plus
optional EDB-SPL) and calls each one's `initialize()` (`plugin_debugger.c:109-115,
156-171`) `[verified-by-code]`. Shared-memory reservation is version-gated: on
PG ≥ 15 it chains a `shmem_request_hook` (`pldebugger_shmem_request`), otherwise
it reserves inline (`plugin_debugger.c:164-182`) `[verified-by-code]`. The
reservations are the global-breakpoint hashes (`reserveBreakpoints`,
`:1358-1368`) and the connection-authentication slots (`dbgcomm_reserve`,
`dbgcomm.c:106-110`) `[verified-by-code]`.

### The SQL API — proxy functions as SQL-callable C

`pldbgapi.c` exposes the debugger as ~18 `PG_FUNCTION_INFO_V1` C functions —
`pldbg_attach_to_port`, `pldbg_wait_for_breakpoint`, `pldbg_step_into`,
`pldbg_step_over`, `pldbg_continue`, `pldbg_get_stack`, `pldbg_get_variables`,
`pldbg_deposit_value`, `pldbg_set_global_breakpoint`, `pldbg_abort_target`, …
(`pldbgapi.c:141-159`) `[verified-by-code]`, declared in the install script
`pldbgapi--1.1.sql`. These run **in the proxy backend**. Each one marshals a
one-character command onto the private socket to the target and blocks reading
the reply (e.g. `pldbg_step_into` → sends `PLDBG_STEP_INTO`; `pldbg_attach_to_port`
→ `dbgcomm_connect_to_target` then reads the initial breakpoint string,
`:300-333`) `[verified-by-code]`. The client thus drives a live backend using
nothing but `SELECT pldbg_*(...)`.

### The inter-backend protocol — `dbgcomm.c`

The target and proxy communicate over a **TCP socket on `127.0.0.1`**, not
shared memory. `dbgcomm.c` opens `AF_INET`/`SOCK_STREAM` sockets, binds an
ephemeral loopback port, and does `connect()`/`listen()`/`accept()` between the
two backends (`dbgcomm.c:159-363`) `[verified-by-code]`. Direction depends on
breakpoint scope:

- **Local breakpoint** → target calls `connectAsServer()` →
  `dbgcomm_listen_for_proxy()`, raises `NOTICE "PLDBGBREAK:%d"` carrying its
  backend id, and waits for the proxy to connect (`plugin_debugger.c:571-587`,
  `dbgcomm.c:258-363`) `[verified-by-code]`.
- **Global breakpoint** → the proxy is already listening; the target calls
  `connectAsClient()` → `dbgcomm_connect_to_proxy(port)` using the port it read
  out of the shared-memory breakpoint (`plugin_debugger.c:599-618`,
  `dbgcomm.c:159-251`) `[verified-by-code]`.

Because a loopback TCP port is reachable by *any* local process, the channel is
authenticated out-of-band through shared memory: each backend advertises its
connecting/listening port in a `dbgcomm_target_slot_t` slot, and the accepting
side only trusts a connection whose **remote port matches a value posted in a
slot** (`dbgcomm.c:44-68, 314-358, 519-543`) `[from-comment][verified-by-code]`.
Reads/writes are length-prefixed counted strings (`readn`/`writen`/`dbg_send`,
`plugin_debugger.c:230-415`) `[verified-by-code]`.

## Where it diverges from core idioms

### 1. A backend blocks *inside the executor*, waiting on a human

The heart of the divergence is `dbg_newstmt` → `plugin_debugger_main_loop`. When
stepping or stopped at a breakpoint, the target sends its current line to the
client and then **loops on `dbg_read_str()`**, executing debugger commands, until
the user issues step/continue (`plpgsql_debugger.c:1472-1487`,
`plugin_debugger.c:961-1129`) `[verified-by-code]`. This is a synchronous
`recv()` in the middle of `exec_stmt` — the backend is frozen mid-transaction,
holding whatever locks, snapshots, and buffer pins the executing statement had
acquired, for an unbounded wall-clock time. Core PostgreSQL has no notion of
"pause a query and wait for interactive input"; pldebugger manufactures exactly
that. Contrast plpgsql_check, which never blocks and never touches a live
executor — it walks a compiled tree offline (`[[knowledge/ideologies/plpgsql_check]]`
§2). The two extensions share a hook and could not be more opposite in what they
do behind it.

### 2. A backend-to-backend TCP socket — vanishingly rare in the ecosystem

Most extensions that coordinate two backends use core IPC: shared memory,
`shm_mq` (as `[[knowledge/ideologies/pg_background]]` does), `SIGUSR1`
multiplexing, or a latch. pldebugger instead opens a **real TCP socket between
two backends** (`dbgcomm.c`) `[verified-by-code]`. The socket buys it two things
core IPC would make awkward: an ordinary blocking bytestream with backpressure
(so the target can just `recv()` and sleep), and a channel the proxy can span
across the fe/be boundary to a remote GUI without the client ever learning the
private protocol (`pldbgapi.c:17-31`, `README-pldebugger.md:64-78`)
`[from-comment][from-README]`. The cost is that it must reinvent authentication
(the shmem port-matching scheme, §How-it-hooks) because a loopback port has no
inherent access control — a concern core IPC primitives handle by construction.

### 3. Global breakpoint state lives in shared memory, protected by its own LWLock

Breakpoints that must be visible to *other* backends (so that whichever backend
next runs the function stops) live in two shmem hash tables — `globalBreakpoints`
and a companion `globalBreakCounts` — created with `ShmemInitHash` under
`AddinShmemInitLock` (`plugin_debugger.c:1395-1458`, `globalbp.h:27-51`)
`[verified-by-code]`. pldebugger allocates its **own LWLock tranche named
`"pldebugger"`** via `LWLockNewTrancheId()`/`LWLockRegisterTranche` and guards
all global-scope hash operations with it (`plugin_debugger.c:1409-1433,
1489-1515`) `[verified-by-code]`. The `BreakCounts` table is a deliberate
secondary index: the breakpoint key is `(databaseId, functionId, lineNumber,
targetPid)` so you cannot look up "is there *any* breakpoint on this function?"
without a full scan — so a second hash keyed only by `(databaseId, functionId)`
answers that in one probe, which is exactly the O(1) check `dbg_startup` runs on
every function entry (`BreakpointOnId`, `plugin_debugger.c:1536-1562`)
`[verified-by-code][from-comment]`. This is the same "maintain a cheap auxiliary
index so the hot path stays cheap" instinct core uses widely, lifted into the
extension.

### 4. Coupling to plpgsql internals — via struct layout, not symbol theft

pldebugger depends on the exact shapes of `PLpgSQL_execstate`, `PLpgSQL_function`,
`PLpgSQL_var`, and the `estate->plugin_info` back-pointer it stows a private
`dbg_ctx` into (`plpgsql_debugger.c:66-78, 975-1038`) `[verified-by-code]`. It
walks `error_context_stack` to reconstruct the PL call stack, recognizing its own
frames by matching `frame->callback` against the interpreter-supplied
`error_callback` (`plugin_debugger.c:1261-1274`, `plpgsql_debugger.c:145-149`)
`[verified-by-code]` — a direct consumer of the
`[[knowledge/idioms/error-context-callbacks]]` mechanism for something it was
never designed for (stack reconstruction, not error annotation). Where
plpgsql_check `dlsym`s named compiler functions and guards them with
`StaticAssertVariableIsOfType`, pldebugger's exposure is the *silent* kind: a
field reordering in `PLpgSQL_execstate` compiles clean and misbehaves at runtime.
Its portability strategy is instead a dense thicket of `#if PG_VERSION_NUM`
guards tracking struct evolution across versions (`PLPGSQL_DTYPE_PROMISE`,
expanded-record `erh`, `ProcNumber`-vs-`BackendId`, …:
`plpgsql_debugger.c:311-313, 665-678`, `dbgcomm.h:16-20`) `[verified-by-code]`.

### 5. Error handling and interrupts while paused mid-statement

Pausing inside a statement forces pldebugger to reimplement several safety nets
core normally owns:

- **Socket errors longjmp past the executor.** A dedicated
  `sigsetjmp(client_lost.m_savepoint)` is armed in `dbg_newstmt` before entering
  the command loop; any fatal socket error in `readn`/`writen` calls
  `siglongjmp` back to it, whereupon pldebugger *pretends no debugger is attached*
  and lets the executor run on rather than hang the backend forever
  (`plpgsql_debugger.c:1391-1412`, `plugin_debugger.c:822-956`)
  `[verified-by-code][from-comment]`. Socket-layer failures are reported with
  `ereport(COMMERROR, …)` precisely so they are logged but **not** sent to the
  client and **do not** abort the transaction (`dbgcomm.c:141-148`)
  `[from-comment]`.
- **"Deposit" runs arbitrary SQL in a sub-transaction.** Setting a variable from
  the GUI builds `SELECT <value>`, wraps it in `BeginInternalSubTransaction` +
  `PG_TRY/PG_CATCH`, and calls the borrowed `assign_expr`; on failure it rolls
  back the subxact and retries the value as a quoted literal
  (`plpgsql_debugger.c:1059-1198`) `[verified-by-code]`. This leans on the
  `[[knowledge/idioms/subtransaction-stack]]` machinery to make an interactive
  side-effect transaction-safe.
- **Waiting is interrupt-aware.** The proxy's `dbgcomm_accept_target` `select()`s
  with a 1-second timeout, re-checking `CHECK_FOR_INTERRUPTS()` and
  `PostmasterIsAlive()` each iteration so a hung debug session can still be
  cancelled or torn down on postmaster death (`dbgcomm.c:461-552`)
  `[verified-by-code]`. Stopping the target is done by having it
  `ereport(ERROR, (errcode(ERRCODE_QUERY_CANCELED), …))` out of the command loop
  on a `STOP`/`RESTART` command (`plugin_debugger.c:1110-1120`)
  `[verified-by-code]`.
- **Exit cleanup.** The proxy registers `cleanupAtExit` via `on_shmem_exit` to
  close sockets and release its global breakpoints (`pldbgapi.c:1406-1417`,
  `BreakpointCleanupProc`, `plugin_debugger.c:1833-1858`) `[verified-by-code]` —
  though it self-notes it only cleans the most-recent session, not all of them
  (`pldbgapi.c:1408-1411`) `[from-comment]`.

## Notable design decisions (cited)

- **Multi-language vtable.** A `debugger_language_t` function table abstracts
  PL/pgSQL vs EDB-SPL so the language-independent core (`plugin_debugger.c`)
  never hard-codes plpgsql; the SPL build is generated by `sed`-renaming
  `plpgsql_*`→`spl_*` at compile time (`Makefile:55-64`,
  `plpgsql_debugger.c:114-129`) `[verified-by-code]`.
- **Ownership checks on breakpoint creation.** `pldbg_oid_debug` requires
  superuser or function owner (`plugin_debugger.c:210-211`); global breakpoints
  require superuser (`pldbg_set_global_breakpoint`, `pldbgapi.c:406-409`)
  `[verified-by-code]`.
- **"Busy" flag hands a target exclusively to one proxy.** When a proxy attaches,
  `BreakpointBusySession` marks that proxy's global breakpoints busy and copies
  them into the target's *local* hash, so the engaged target keeps hitting them
  while other backends skip them; `BreakpointFreeSession` reverses it
  (`plugin_debugger.c:1660-1721`) `[from-comment][verified-by-code]`.
- **Stale-breakpoint self-healing.** If the target can't attach to the advertised
  proxy (proxy died), it deletes the phantom breakpoint rather than retry forever
  (`plpgsql_debugger.c:1424-1449`) `[verified-by-code]`.
- **Hidden internal variables.** The debugger filters compiler-generated names
  (`found`, `sqlerrm`, SPL `txtNNN`, …) out of the variable list shown to the
  user (`is_datum_visible`, `plpgsql_debugger.c:1211-1276`) `[verified-by-code]`.
- **Honesty about maturity.** Record/row printing, quoted-identifier parsing in
  deposit, and several dtypes are `FIXME`/unimplemented stubs
  (`plpgsql_debugger.c:340-378, 649-696`, `plugin_debugger.c:1143,1152`)
  `[from-comment]`.

## Links into corpus

- `[[knowledge/ideologies/plpgsql_check]]` — **the key sibling.** Same
  `PLpgSQL_plugin` rendezvous hook, opposite philosophy: plpgsql_check compiles
  and type-checks without executing (static/offline); pldebugger rides the live
  executor and blocks it between statements (dynamic/online). plpgsql_check
  dlsyms plpgsql compiler symbols; pldebugger harvests interpreter callbacks back
  out of the shared plugin struct and otherwise couples via struct layout.
- `[[knowledge/ideologies/pg_background]]` — another two-backend coordinator, but
  via core `shm_mq` IPC rather than pldebugger's backend-to-backend TCP socket.
- `[[knowledge/ideologies/plv8]]`, `[[knowledge/ideologies/pljava]]` — PL-family
  siblings that *implement* a new language; pldebugger instead *instruments* an
  existing one.
- `[[knowledge/idioms/error-context-callbacks]]` — pldebugger walks
  `error_context_stack` and identifies PL frames by callback pointer to
  reconstruct the debug call stack.
- `[[knowledge/idioms/subtransaction-stack]]` — variable "deposit" wraps an
  arbitrary `SELECT` in `BeginInternalSubTransaction`/`PG_TRY`.
- `[[knowledge/idioms/lwlock-rank-discipline]]`,
  `[[knowledge/subsystems/storage-lmgr]]` — the private `"pldebugger"` LWLock
  tranche guarding the global-breakpoint shmem hashes.
- `[[knowledge/subsystems/storage-ipc]]` — `ShmemInitHash`/`ShmemInitStruct`
  under `AddinShmemInitLock`, `on_shmem_exit` cleanup, `shmem_request_hook`.
- `[[knowledge/idioms/fmgr]]` / `[[knowledge/idioms/spi]]` — the `pldbg_*` SQL
  API is SRF/`PG_FUNCTION_INFO_V1` C functions; variable rendering uses type
  output functions via `fmgr_info`/`FunctionCall3`.
- `[[knowledge/subsystems/tcop]]` — the debugger command loop is a mini
  read-eval loop layered *inside* a backend already inside the main loop.
- `.claude/skills/plpgsql-internals/SKILL.md`,
  `.claude/skills/extension-development/SKILL.md`,
  `.claude/skills/bgworker-and-extensions/SKILL.md` — the plugin hook, module
  wiring, and shmem-reservation patterns.

## Anthropology takeaway

pldebugger is the corpus's clearest case of an extension **bending the executor's
control flow into an interactive REPL**: it takes plpgsql's sanctioned
`stmt_beg` callback and, behind it, parks a live backend on a blocking socket
`recv()` in the middle of a transaction until a human on another machine says
"step". Two idiom-mining threads. (a) It is the counter-example to
`[[knowledge/ideologies/plpgsql_check]]`: the same `find_rendezvous_variable`
hook can be used for pure static inspection (no execution, no blocking) *or* for
maximal runtime intervention (freeze, inspect, mutate, resume) — a good probe for
how much the plugin ABI actually permits, and how differently two extensions
lean on it. (b) The **backend-to-backend authenticated TCP socket** (`dbgcomm.c`)
is a genuinely unusual IPC choice worth a `knowledge/idioms` note as the "when
you need a blocking interactive bytestream between two backends and shm_mq's
non-blocking ring won't do" pattern — together with its hand-rolled
shmem-port-matching authentication, which is the price of choosing a loopback
socket over a core IPC primitive that carries access control for free.

## Sources

Fetched 2026-07-09 via `raw.githubusercontent.com` (branch `master`; the
GitHub trees/contents API is 403 for this external repo in-session, so only raw
blobs were retrieved):

- `.../EnterpriseDB/pldebugger/master/README-pldebugger.md` → HTTP 200 (92 lines;
  architecture + three-process model, deep-read).
- `.../plugin_debugger.c` → HTTP 200 (1981 lines; deep-read — `_PG_init`, plugin
  install path, `plugin_debugger_main_loop`, breakpoint shmem hashes + LWLock
  tranche, socket helpers, `siglongjmp` error handling).
- `.../plpgsql_debugger.c` → HTTP 200 (1521 lines; deep-read — `PLpgSQL_plugin`
  install, `dbg_startup`/`dbg_newstmt`, variable rendering, `plpgsql_do_deposit`
  subxact wrapper, `error_context_stack` frame identification).
- `.../dbgcomm.c` → HTTP 200 (684 lines; deep-read — connect/listen/accept
  between backends, shmem-slot port-matching authentication, interrupt-aware
  `select()` loop).
- `.../dbgcomm.h` → HTTP 200 (31 lines; `BackendId`→`ProcNumber` shim).
- `.../globalbp.h` → HTTP 200 (64 lines; `Breakpoint`/`BreakpointKey` shmem
  structs + API prototypes).
- `.../pldbgapi.c` → HTTP 200 (1445 lines; deep-read header + proxy-function
  table, `pldbg_attach_to_port`/`pldbg_wait_for_target`/`pldbg_set_global_breakpoint`,
  `cleanupAtExit`; middle bodies skimmed).
- `.../pldbgapi.control` → HTTP 200 (5 lines).
- `.../pldbgapi--1.1.sql` → HTTP 200 (155 lines; SQL install script, skimmed).
- `.../Makefile` → HTTP 200 (65 lines; MODULE_big/OBJS, plpgsql.h include path,
  SPL `sed`-rename rule).

All cites are `[verified-by-code]` against the fetched `.c`/`.h` except: the
three-process architecture and target↔proxy protocol opacity (`[from-README]` /
`[from-comment]`), the shmem-authentication rationale (`[from-comment]`, from the
`dbgcomm.c:44-68` block comment), the "negligible overhead when detached" and
"busy session" intents (`[from-comment]`), and the mapping of the
`{dbg_startup, NULL, NULL, dbg_newstmt, NULL}` initializer onto specific
`PLpgSQL_plugin` fields (`[inferred]` from the struct's field order, corroborated
by the `:993-998` comment). The proxy-side per-command marshalling in the middle
of `pldbgapi.c` (`pldbg_step_over`/`pldbg_continue` bodies) was skimmed, not
line-read; claims about it rest on the visible send-then-read pattern of the two
functions that were read in full.
