# omnigres (omnigres/omnigres) — Postgres as an all-in-one application server: a hot-reloadable in-backend module loader (`omni`) and an HTTP server that terminates HTTP *inside* bgworkers and dispatches to SQL handlers (`omni_httpd`)

> Ideology note produced by the `pg-extension-anthropologist` cloud routine.
> Repo: `omnigres/omnigres` @ branch `master`. All `file:line` cites point into
> THAT repo (not `source/`). Cites verified against files fetched 2026-07-12
> (see Sources footer). omnigres is a LARGE C++/C monorepo of 40+ extensions;
> this doc covers only its two load-bearing divergences — the `omni` dynamic
> module loader and the `omni_httpd` in-backend HTTP server. Everything else in
> the monorepo (fintech stack, `omni_vfs`, `omni_types`, `omni_web`, the SQL
> layers) is un-read and out of scope. Read alongside the contrasts
> `[[wasmer-postgres]]`, `[[pg_tle]]`, `[[pg_net]]`, `[[pgsql-http]]`,
> `[[pgrx]]`, `[[pgrouting]]`.

## Domain & purpose

Omnigres "makes Postgres a developer-first application platform. You can deploy
a single database instance and it can host your entire application, scaling as
needed" (`README.md`) `[from-README]`. The pitch is that a Postgres instance
should itself run application logic, serve HTTP/WebSocket protocols, cache, and
ship routine building blocks (authn/authz, payments) — collapsing the
app-server / cache / database tiers into one process tree (`README.md`)
`[from-README]`. Two extensions carry the architecture:

1. **`omni`** — a *loader* extension (preloaded via `shared_preload_libraries`)
   that gives every other omnigres extension a richer in-backend module
   lifecycle than core's `_PG_init`: hot load/unload/upgrade without a server
   restart, a shared-memory module registry, a shared hook switchboard, and a
   versioned module ABI.
2. **`omni_httpd`** — a full HTTP/1 + WebSocket server built on the H2O library,
   running inside Postgres background workers, that terminates HTTP itself and
   routes each request to a **SQL/plpgsql handler function**.

These two are the standout divergences from core PG design, so they anchor this
doc.

## How it hooks into PG

### `omni` — the loader

`omni` MUST be in `shared_preload_libraries`: `_PG_init` sets a static
`preloaded` flag and `ereport(ERROR)`s if a later `CREATE EXTENSION`/`LOAD`
finds it was not preloaded (`extensions/omni/init.c:42-65`) `[verified-by-code]`.
At preload it does five things `[verified-by-code]`:

- **Plants a rendezvous marker.** `find_rendezvous_variable("omni(loaded)")` is
  set to a static struct with magic `"0MNI"`, the interface version, and the
  library path (`init.c:44-48`). This is how any later-loaded copy of `omni`
  detects the already-resident loader.
- **Seizes the conventional hooks, once.** A `save_hook` macro saves and
  replaces `needs_fmgr_hook`, `planner_hook`, `ExecutorStart_hook`,
  `ExecutorRun/Finish/End_hook`, `ProcessUtility_hook`, `emit_log_hook`,
  `check_password_hook` with `omni`'s own dispatchers (`init.c:82-95`). A
  `default` entry is seeded first in each per-type hook array so the original
  saved hook still runs (`init.c:99-133`).
- **Requests shmem + an LWLock tranche.** `shmem_request` calls
  `RequestAddinShmemSpace(sizeof(omni_shared_info))` and
  `RequestNamedLWLockTranche("omni", __omni_num_locks)`
  (`init.c:187-197`); `shmem_hook` `ShmemInitStruct`s the shared header and
  creates a DSA tranche (`init.c:203-227`).
- **Arms per-backend init.** It registers `init_backend` as a *reset callback on
  `PostmasterContext`* (`init.c:135-142`), so every forked backend runs module
  loading when the postmaster context is torn down at backend start; plus a
  master `RegisterBackgroundWorker("omni startup")` (`init.c:144-155`).
- **Registers syscache invalidation → reload.** `CacheRegisterSyscacheCallback`
  on `PROCOID` (and `EXTENSIONOID` on PG18+) flips a global
  `backend_force_reload = true` (`init.c:35-37,174-180`).

The shared header `omni_shared_info` holds a `dsa_handle` plus two
`dshash_table_handle`s — one for the module registry, one for cross-module
shmem allocations (`extensions/omni/omni_common.h:41-49`) `[verified-by-code]`.
Each backend attaches to these DSA-backed `dshash` tables in
`initialize_omni_modules` (`extensions/omni/omni.c:83-123`) `[verified-by-code]`.

### `omni_httpd` — an `omni` module

`omni_httpd` is itself an `omni` module: it stamps `OMNI_MAGIC` +
`OMNI_MODULE_INFO` (`extensions/omni_httpd/omni_httpd.c:71-75`) and exposes
`_Omni_init`/`_Omni_deinit` (`omni_httpd.c:212-268,290-316`)
`[verified-by-code]`. Instead of touching `shmem_request_hook` or
`RegisterBackgroundWorker` directly, it calls **through the `omni` handle**:
`handle->declare_guc_variable` for `omni_httpd.temp_dir` /
`omni_httpd.http_workers`, `handle->allocate_shmem` for the per-database
control block + reload semaphore + master-worker handle, and
`handle->request_bgworker_start` to launch the master worker after commit
(`omni_httpd.c:212-268,170-206`) `[verified-by-code]`. It is the clearest
demonstration that `omni` is a *framework* other extensions target.

## Where it diverges from core idioms

### 1. It defeats "a loaded `.so` lives for the backend's life" via a diff-based reload loop

Core PG has no unload path: once a backend `dlopen`s a `.so`, it stays mapped
until the backend exits, and `_PG_init` runs exactly once. `omni` replaces this
with a **desired-state reconciliation** run on nearly every statement.
`load_pending_modules` is called from `omni`'s executor-start, executor-end, and
(for transaction statements) process-utility dispatchers
(`extensions/omni/hook_harness.c:182-186,209-212,237-239`)
`[verified-by-code]`. When `backend_force_reload` is set, it
(`omni.c:489-599`) `[verified-by-code]`:

1. scans `pg_extension`, and for each installed extension derives the module
   `.so` path from the extension's `.control` `module_pathname`
   (`consider_ext` → `get_extension_module_pathname`,
   `extensions/omni/extension.c:59-92`);
2. computes `modules_to_remove = initialized_modules − loaded_modules` and
   `modules_to_load = loaded_modules − initialized_modules`
   (`omni.c:527-529`);
3. **unloads removed modules first** (so upgrades can tear down old state),
   then loads new ones (`omni.c:534-597`).

`load_module` does `dlopen(path, RTLD_LAZY)`, checks the `_Omni_magic` symbol,
and — if this is the first backend to see this path — allocates an
`omni_handle_private` in DSA, assigns a monotonic module id from
`shared_info->module_counter`, and records a `ModuleEntry` keyed by path in the
shared `dshash` (`omni.c:282-451`, dlopen `:285`, magic `:289-293`,
`dshash_find_or_insert` `:357`, `dsa_allocate` `:366`) `[verified-by-code]`.
Each backend then creates a per-module `MemoryContext` named
`"TopMemoryContext/omni"` identified by the module path, `dlopen`s again, and
calls the module's `_Omni_load` (revision < 5) and `_Omni_init` via `dlsym`
(`omni.c:550-587`) `[verified-by-code]`.

The critical subtlety: for the modern ABI (revision ≥ 5) `omni` does **not**
`dlclose` on unload. `unload_module` `dlopen`s the path, calls `_Omni_deinit`,
and then merely `MemoryContextReset`s the module's context — keeping the record
for possible reuse — while only revision < 5 modules take the old
refcount/`_Omni_unload`/`dlclose` path (`omni.c:1072-1151`, deinit `:1106-1108`,
legacy `dlclose` `:1113-1127`, `MemoryContextReset` `:1146`)
`[verified-by-code]`. So "reload" is really: re-run the module's
init/deinit lifecycle and swap the omni handle's state, not reload the machine
code. Genuine code replacement happens on *upgrade*, where a new version's
`.control` yields a different `module_pathname`, hence a new `dshash` key and a
fresh `dlopen` of the new `.so`. Contrast `[[pg_tle]]`, which also reroutes
extension management but keeps core's one-load-per-backend rule; and
`[[wasmer-postgres]]`, which achieves reloadability only because the guest code
is WASM data, not a `.so`.

### 2. Extension *upgrade* rewrites `pg_proc.probin` to repoint C functions at the new `.so`

Because a C-language function's `pg_proc.probin` names a fixed library path,
`ALTER EXTENSION … UPDATE` to a version whose `module_pathname` differs would
leave old function rows pointing at the old library. `omni` installs a *wrapping*
`ProcessUtility` hook (`extension_upgrade_hook`, registered from the `omni`
module's own `_Omni_init`, `extensions/omni/module.c:18-24`) that, on the second
pass of an `AlterExtensionStmt`, walks `pg_depend` for the extension's C
functions and `CatalogTupleUpdate`s each `probin` from the old to the new
`module_pathname` (`extension.c:136-283`, probin rewrite `:247-256`)
`[verified-by-code]`. This is `omni` reaching into the catalog to make
restart-free version swaps of native code coherent — a concern core never has
because core never swaps a live `.so`.

### 3. A shared hook *switchboard* replaces per-extension `_PG_init` hook chaining

Core extensions each save-and-chain the global hook pointers in their own
`_PG_init`, an arrangement that cannot be undone (you cannot un-chain a hook).
`omni` instead owns each global hook exactly once and lets modules register into
per-type arrays at runtime via `handle->register_hook` (`omni.c:601-667`)
`[verified-by-code]`. Hooks may be appended, or registered as `wrap` (a
before+after pair injected at the front, `omni.c:610-642`). The dispatcher
`iterate_hooks` walks the array in reverse, threading a per-hook context and a
`next_action` so a module can short-circuit the chain
(`hook_harness.c:138-164`); the terminal `default_*` entries call the original
saved core hook or `standard_*` routine (`hook_harness.c:38-108`)
`[verified-by-code]`. On unload, `reorganize_hooks` compacts out any hook whose
module is no longer in `initialized_modules` (`hook_harness.c:110-136`)
`[verified-by-code]` — i.e. hook registration is *reversible*, which core's
model is not. The switchboard lives in backend `TopMemoryContext` and is rebuilt
per backend, and `omni_httpd` uses exactly this seam (registering a wrapping
extension-upgrade hook as shown above).

### 4. It runs a network *server* inside PG bgworkers, inverting the client/server model

Postgres is the server for its own wire protocol; extensions that speak HTTP
(`[[pg_net]]`, `[[pgsql-http]]`) are HTTP **clients** that reach *out*. `omni_httpd`
inverts this: it *terminates* HTTP inside the backend and answers it from SQL.
The mechanics `[verified-by-code]`:

- **A master worker opens the listening sockets.** `master_worker` reads
  `omni_httpd.listeners (address, port, id, effective_port)` over SPI, calls
  `create_listening_socket` per row, and records the fds
  (`extensions/omni_httpd/master_worker.c:361-469`). It holds the listeners
  table under `ExclusiveLock` so the fd *order* is stable across workers
  (`:343-357`).
- **Listen fds are handed to workers via `SCM_RIGHTS`.** The master serves a
  Unix domain socket and `send_fds`es the whole socket vector to any connecting
  http worker (`master_worker.c:103-157`); workers `recv_fds`/`accept_fds` them
  (`fd.h:35-45` — capped at `SCM_MAX_FD` = 253; `http_worker.c:477,739`).
  Sharing fds this way is how config reload keeps existing listeners alive.
- **N http workers are dynamic bgworkers.** `omni_httpd.http_workers` (default =
  CPU count) `RegisterDynamicBackgroundWorker`s named `"omni_httpd worker"`
  running `http_worker`, coordinated with the master through a shmem atomic
  `semaphore` and `SIGUSR2` (`master_worker.c:576-635`, signal `:526-531`).
- **Config reload rides LISTEN/NOTIFY.** A `reload_configuration` trigger fires
  `Async_Notify(OMNI_HTTPD_CONFIGURATION_NOTIFY_CHANNEL)` on listener/handler
  changes (`omni_httpd.c:325-338`); the master `Async_Listen`s that channel
  (`master_worker.c:302`) and rebuilds sockets on wake. This layers an HTTP
  control plane on top of PG's own async-notification IPC — cross-ref
  `[[notify-listen-coordination]]`.

### 5. Two H2O event loops per worker — one on a pthread, one on the PG main thread

A PG backend is strictly single-threaded and its error handling is
`setjmp`/`longjmp`. `omni_httpd` nonetheless spins up a **second thread**:
`http_worker` `pthread_create`s an `event_loop` thread that runs a
`worker_event_loop` (H2O, libuv disabled — `CMakeLists.txt:49` sets
`H2O_USE_LIBUV=0`) doing all socket I/O (`http_worker.c:237-243`;
`event_loop.c:400-428`) `[verified-by-code]`. The network thread never touches
SQL; it packages each request into a `handler_message_t` and posts it through an
`h2o_multithread_queue`/`receiver` to a *second* H2O loop, `handler_event_loop`,
which the **PG main thread** drives (`event_loop.c:19-24,290-390`;
`http_worker.h:135-137`) `[verified-by-code]`. The two threads rendezvous over a
`pthread_mutex` + condition variables (`event_loop.c:414-420`,
`http_worker.c:596-614`). This keeps every `palloc`, SPI call, and `ereport`
`longjmp` on the one thread that owns the backend, while the socket loop runs
elsewhere — a deliberate firewall around PG's thread-hostile core.

### 6. A request becomes an `http_request` tuple dispatched to a SQL handler via fmgr

On the main thread, `handler` opens a transaction, builds an `http_request`
composite tuple — `(method::http_method, path, query_string, body::bytea,
headers::http_header[])`, prepending an `omnigres-connecting-ip` header — and
runs it against the route table (`http_worker.c:1118-1257`) `[verified-by-code]`.
Each route's handler is a user **function or procedure**, invoked directly by
`FunctionCallInvoke` after a `match_urlpattern` URL match, not by re-parsing SQL
(`:1305-1398`, invoke `:1378`). Handlers return an `http_outcome` that is a
`RESPONSE` / `ABORT` / `PROXY` tagged union (`http_worker.h:139-141`). Handler
queries are validated at definition time by injecting a `request` CTE
(`NULL::omni_http.http_method AS method, …`) via `omni_sql_add_cte`, so authors
write SQL that selects `FROM request` (`omni_httpd.c:508-520`)
`[verified-by-code]`. Requests run under a persistent `execution_portal` with a
non-atomic `CallContext`, so procedure handlers may do transaction control
(`http_worker.c:356-363,389-395`), and a per-route role triggers
`SetUserIdAndSecContext` to drop privileges before the handler runs
(`:1365-1377`) `[verified-by-code]`.

### 7. C++ across the `extern "C"` boundary, with an exception firewall

`omni_httpd` is a mixed C11 + C++20 target (`CMakeLists.txt:34-35`), pulling in
the `ada` URL library for WHATWG URLPattern matching (`ada_url` dependency,
`:30,39`) `[verified-by-code]`. The single C++ translation unit,
`urlpattern.cpp`, exposes `match_urlpattern` behind `extern "C"` and wraps its
entire body in `try { … } catch (...) { return false; }`
(`extensions/omni_httpd/urlpattern.cpp:79-106`, `try` `:82`, `catch(...)`
`:103-105`) `[verified-by-code]`. That `catch (...)` is the firewall: a C++
exception thrown by `ada::` (e.g. a malformed pattern) is converted to a `false`
("no match") return and never allowed to unwind across the C boundary into PG's
`longjmp` machinery. It is the same class of guard documented for
`[[pgrouting]]` (C++ Boost) and `[[pgrx]]` (Rust panic→ereport), though
`omni_httpd`'s version *swallows* the error into a boolean rather than
translating it to `ereport` — a design choice, not an oversight, given match
failure is a benign outcome.

## Notable design decisions (cited)

- **Versioned module ABI with revision-gated function tables.** `omni_magic`
  carries `{size, version, revision, pg_version}` (`omni/omni/omni_v0.h:53-59`);
  the current interface is version 0, revision 7
  (`OMNI_INTERFACE_VERSION`/`OMNI_INTERFACE_REVISION`, `:63-64`)
  `[verified-by-code]`. `load_module` refuses a module whose `magic.version` ≠
  `OMNI_INTERFACE_VERSION` (`omni.c:353`) and, crucially, **fills the module's
  handle function table differently per revision** — e.g. a
  `struct _omni_handle_0r3` shim for revision < 4 where `register_hook` sat in a
  different slot, and an `allocate_shmem_0_0` shim for revision 0
  (`omni.c:387-427`) `[verified-by-code]`. `omni` thus maintains binary
  compatibility across its own historical ABIs — including an explicit special
  case for legacy omni 0.1.0 modules (`omni.c:305-319`).
- **The loader is unity-built.** The `omni` extension compiles `init.c omni.c
  hook_harness.c module.c extension.c workers.c utils.c dshash.c` as a single
  unity translation unit (`extensions/omni/CMakeLists.txt:21,48-53`), which is
  why `omni_common.h` toggles `static` vs `extern` via a `UNITY_BUILD` macro
  (`omni_common.h:29-38`) `[verified-by-code]`. It uses `dladdr`
  (`HAVE_DLADDR`, `CMakeLists.txt:14`) to discover its own `.so` path.
- **Per-database worker fan-out.** The `omni startup` master worker enumerates
  `pg_database` and `RegisterDynamicBackgroundWorker`s a `database_worker` per
  connectable, non-template DB (`extensions/omni/workers.c:34-86`)
  `[verified-by-code]`; each DB then loads its own module set. `omni_httpd`
  likewise starts one master worker per database, skipping template DBs
  (`omni_httpd.c:159-201`).
- **Cross-module shared memory is name-keyed and refcounted in DSA.**
  `allocate_shmem(handle, name, size, init, …)` stores allocations in the shared
  `omni_allocations` dshash keyed by `(module_id, name)`, with a per-allocation
  atomic refcounter and per-backend acquisition tracking so a shmem block is
  freed only when the last backend releases it (`omni.c:673-831`)
  `[verified-by-code]`. The advice to embed the version in the name
  ("to facilitate easier upgrades", `omni/omni/omni_v0.h:122-123`) mirrors the
  reload model. This is the shared-registry contrast to `[[wasmer-postgres]]`'s
  backend-private `static mut` instance map.
- **Introspection SRFs over the registry.** `omni.modules`, `omni.hooks`, and
  `omni.shmem_allocations` are set-returning functions that seq-scan the DSA
  dshash tables under the omni LWLocks (`extensions/omni/module.c:26-144`)
  `[verified-by-code]` — the registry is user-visible.
- **`omni_httpd` uses a shmem semaphore for reload barrier sync.** Master and
  workers spin on `pg_atomic_compare_exchange_u32(semaphore, …)` to agree that
  all workers have entered/left "standby" before the master commits a new config
  (`master_worker.c:520-556,620-634`) `[verified-by-code]`.

## Links into corpus

- `[[pg_net]]`, `[[pgsql-http]]` — the sharpest contrast: both are HTTP
  *clients* (Postgres reaches out), whereas `omni_httpd` is an HTTP *server*
  (Postgres is reached). Same protocol, inverted role.
- `[[wasmer-postgres]]` — the other "in-backend runtime". Its instance registry
  is a backend-private `static mut`; `omni`'s registry is a DSA-backed `dshash`
  shared across backends with refcounting — the mature version of the same idea.
- `[[pg_tle]]` — the other "reroute extension management" extension. pg_tle
  swaps the *storage substrate* (catalog vs filesystem) but keeps core's
  one-load-per-backend `.so` rule; `omni` keeps the filesystem `.so` but adds a
  reload/unload/upgrade lifecycle core lacks.
- `[[pgrx]]`, `[[pgrouting]]` — FFI-boundary firewalls: Rust panic→ereport and
  C++/Boost exception guards, the analogues of `omni_httpd`'s
  `catch(...)`-to-`false` in `urlpattern.cpp`.
- `[[prest_bgworker]]`, `[[pgmq]]` — other bgworker-centric extensions worth
  comparing on worker lifecycle.
- Idioms: `[[process-utility-hook-chain]]` (the extension-upgrade wrap hook),
  `[[background-worker-startup]]` (master/db/http worker fan-out),
  `[[notify-listen-coordination]]` (omni_httpd config reload channel),
  `[[guc-variables]]` (declared through the omni handle),
  `[[locking-overview]]` (named LWLock tranche + DSA tranche),
  `[[memory-contexts]]` (per-module context reset as the unload primitive),
  `[[parallel-context-and-dsm]]` (DSA/dshash usage),
  `[[cache-invalidation-registration]]` / `[[syscache-invalidation-flow]]`
  (PROCOID/EXTENSIONOID callback → `backend_force_reload`),
  `[[fmgr]]` / `[[spi]]` (handler invocation + listener queries).
- Skills: `.claude/skills/bgworker-and-extensions/SKILL.md` (the
  `RegisterDynamicBackgroundWorker` + `_PG_init`-hook patterns `omni`
  generalizes), `.claude/skills/extension-development/SKILL.md` (the file-based
  `.control` + `module_pathname` model `omni` reads and rewrites).

## Anthropology takeaway

omnigres is the corpus's cleanest example of **an extension that reimplements
the extension mechanism itself**. Where core gives every `.so` a single
`_PG_init` and no way back, `omni` interposes a loader that (a) seizes the
global hooks once and re-lets them as a reversible, per-module switchboard, (b)
keeps a DSA-shared registry of loaded modules keyed by path, and (c) runs a
desired-state reconciliation on nearly every statement so `CREATE`/`ALTER`/`DROP
EXTENSION` load, upgrade, or tear down native modules without a restart — even
rewriting `pg_proc.probin` to keep C functions pointing at the right library
across versions. On top of that substrate, `omni_httpd` inverts Postgres's
client/server posture: it opens listening sockets in a master worker, shares
them to N http workers by `SCM_RIGHTS`, runs an H2O event loop on a side thread
while SQL executes on the main thread, and turns each HTTP request into an
`http_request` tuple dispatched to a SQL/plpgsql handler. For anyone auditing an
omnigres cluster the load-bearing facts are: `omni` must be preloaded and holds
every conventional hook; modules can be unloaded/upgraded live (so backend state
is far more mutable than core's model assumes); and real network servers with a
real second thread live inside ordinary Postgres backends.

## Sources

Fetched 2026-07-12 (branch `master`), all via
`https://raw.githubusercontent.com/omnigres/omnigres/master/<path>`. GitHub
git/trees + `api.github.com` are 403-blocked from this environment;
`raw.githubusercontent.com` returns HTTP 200. File discovery was by probing
candidate paths for 200 vs 404.

- `README.md` → 200 (top-level philosophy; read for §Domain) `[from-README]`.
- `omni/CMakeLists.txt` → 200 (header-only `libomni` INTERFACE lib — the public
  API dir).
- `omni/omni/omni_v0.h` → 200 (506 lines; `omni_magic`, `OMNI_MAGIC`,
  `OMNI_INTERFACE_VERSION`/`REVISION`, `_Omni_init`/`_Omni_deinit`, shmem/hook
  function-pointer typedefs — read for ABI/lifecycle cites).
- `extensions/omni/CMakeLists.txt` → 200 (SOURCES list, `SHARED_PRELOAD ON`,
  `RELOCATABLE false`, `dladdr`, unity build).
- `extensions/omni/omni_common.h` → 200 (282 lines; `omni_shared_info`,
  `omni_handle_private`, `ModuleEntry`/`ModuleAllocation`, hook-entry structs,
  the `UNITY_BUILD` `static`/`extern` macros — full read).
- `extensions/omni/init.c` → 200 (298 lines; `_PG_init`, rendezvous, hook save,
  shmem request/startup, `init_backend`, syscache-invalidation reload — full
  read).
- `extensions/omni/omni.c` → 200 (1216 lines; `load_module`,
  `load_pending_modules`, `unload_module`, `register_hook`, `allocate_shmem`,
  bgworker request ops, `deinitialize_backend` — full read).
- `extensions/omni/hook_harness.c` → 200 (286 lines; `default_*` chaining,
  `iterate_hooks`, `reorganize_hooks`, the `omni_*_hook` dispatchers — full
  read).
- `extensions/omni/module.c` → 200 (144 lines; `_Omni_init` upgrade-hook
  registration + `modules`/`hooks`/`shmem_allocations` SRFs — full read).
- `extensions/omni/extension.c` → 200 (283 lines;
  `get_extension_module_pathname`, `extension_upgrade_hook` probin rewrite —
  full read).
- `extensions/omni/workers.c` → 200 (86 lines; `startup_worker` +
  `database_worker` — full read).
- `extensions/omni_httpd/CMakeLists.txt` → 200 (H2O, C++20/`ada_url`,
  `H2O_USE_LIBUV=0`, SOURCES incl. `urlpattern.cpp` — full read).
- `extensions/omni_httpd/omni_httpd.h` → 200 (68 lines; constants, externs —
  full read).
- `extensions/omni_httpd/http_worker.h` → 200 (145 lines; `listener_ctx`,
  request-plan param indices, outcome tags — full read).
- `extensions/omni_httpd/fd.h` → 200 (46 lines; `send_fds`/`recv_fds`,
  `SCM_MAX_FD` — full read).
- `extensions/omni_httpd/omni_httpd.c` → 200 (625 lines; `_Omni_init`/`_deinit`,
  GUCs, `start`/`stop`, `http_response`, `reload_configuration`,
  `handlers_query_validity_trigger`, websocket send — full read).
- `extensions/omni_httpd/master_worker.c` → 200 (658 lines; fd sharing, listener
  socket setup, http-worker registration, reload semaphore — full read).
- `extensions/omni_httpd/http_worker.c` → 200 (1695 lines; worker main, event
  thread, route setup, `handler` request→SQL dispatch — §223-422 and §1118-1417
  read closely; the websocket-close and error-response tails skimmed).
- `extensions/omni_httpd/event_loop.c` → 200 (605 lines; two-loop/two-thread
  message passing — key regions §400-428 and the `on_message`/`send_message`
  machinery read; not line-audited end to end).
- `extensions/omni_httpd/urlpattern.cpp` → 200 (107 lines;
  `extern "C" match_urlpattern` with the `try/catch(...)` firewall — full read).

**404 / un-read (coverage is partial — this is a 40+-extension monorepo):**
`extensions/omni/omni.control` and `omni_httpd.control` 404 at the probed paths
(the `.control` files are generated by `add_postgresql_extension`, so their
exact contents are `[inferred]`). `extensions/omni/{dshash.c,utils.c}`,
`extensions/omni_httpd/{cascading_query.c,fd.c}`, the `test/` trees, and the
SQL install scripts were not read. All of omnigres beyond `omni` + `omni_httpd`
(fintech, `omni_vfs`, `omni_types`, `omni_web`, `omni_sql`, `omni_http`,
WebSocket internals) is out of scope. Every concrete claim above is tagged
`[verified-by-code]` against a fetched source file or `[from-README]`; the two
generated-control-file remarks are `[inferred]`. The full behavior of
`event_loop.c` response write-back and the websocket lifecycle was read for
structure, not audited line-by-line.
