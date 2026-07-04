# prest_bgworker — a minimal reference template for hosting a Go program as a PostgreSQL background worker: `RegisterBackgroundWorker` in C, real logic in Go, bridged by cgo

> Headline: the smallest possible "Go inside Postgres" skeleton. It is not a
> feature — it prints `Hello World from GoLang!!!` from a background worker
> every 10 seconds. Its entire pedagogical payload is the *glue*: a C
> translation unit (`main_c.c`) that owns `_PG_init` +
> `RegisterBackgroundWorker` + the signal/latch primitives, and a Go
> translation unit (`main.go`) that owns the worker's main loop, stitched
> together by cgo so that PostgreSQL's postmaster forks a worker whose actual
> body is a `//export`'d Go function. The whole thing compiles to one `.so`
> via `go build -buildmode=c-shared`.

> Ideology note produced by the `pg-extension-anthropologist` cloud routine.
> Repo: `prest/bgworker` @ branch `main` (92★, Go + C, from the pREST project),
> fetched 2026-07-03. All `file:line` cites point into that repo, **not** into
> `source/`. Caveat: fetched via `raw.githubusercontent.com` only (GitHub API
> tree, codeload tarballs, and github.com HTML are all 403 — no directory
> listing was possible). The manifest's expected filenames
> (`worker.c` / `worker.go` / `Makefile`) do **not** exist; the actual files,
> discovered by probing the cgo `#include` and the README's build reference,
> are `main.go`, `main_c.c`, `main_c.h`, and `build.bash` (there is **no**
> Makefile — the build is a shell script). Files read in full: `README.md`,
> `main.go`, `main_c.c`, `main_c.h`, `build.bash`. Confidence tags:
> `[verified-by-code]` `[from-README]` `[from-comment]` `[inferred]`
> `[unverified]`.

## Domain & purpose

prest_bgworker is a **template / skeleton**, not a production extension. Its
README is four sentences long: "Background Worker Processes for PostgreSQL
written in Go" plus build + config instructions (`README.md:1-3,20-24`)
`[from-README]`. The worker does no useful work — its loop body is a single
`elog(LOG, ...)` printing `"Hello World from GoLang!!! Yeahhhhh!!!!"`
(`main.go:29`) `[verified-by-code]`. The value is entirely pedagogical: it
answers one question — *how do you make PostgreSQL run a Go program as a
long-lived background process?* — and answers it in the minimum number of
lines. It ships from the pREST project (a Go-based REST server over Postgres),
which is presumably why the authors wanted a proof-of-concept for embedding Go
directly in the backend rather than talking to it over a socket. Treat every
claim about "what a real worker would do" below as commentary on what this
skeleton *omits* — the omissions are the ideological content.

## How it hooks into PG

The C side is a normal PG loadable module. `main_c.c:14` declares
`PG_MODULE_MAGIC`; `main_c.c:86-100` defines `_PG_init`, which the postmaster
calls once at `shared_preload_libraries` load time `[verified-by-code]`. Inside
`_PG_init` it zeroes a stack `BackgroundWorker`, fills its fields, and calls
`RegisterBackgroundWorker(&worker)` (`main_c.c:99`) — the **static**
registration path that is only legal from `_PG_init` while running out of
`shared_preload_libraries` `[verified-by-code]`. The README confirms the
required config line: `shared_preload_libraries = 'go_background_worker'`
(`README.md:22-24`) `[from-README]`.

The `BackgroundWorker` struct is filled at `main_c.c:90-98` `[verified-by-code]`:

- `bgw_flags = BGWORKER_SHMEM_ACCESS` (`:91`) — shared-memory access only.
  Notably **not** `BGWORKER_BACKEND_DATABASE_CONNECTION`, so this worker may
  never attach to a database or run SQL.
- `bgw_start_time = BgWorkerStart_RecoveryFinished` (`:92`) — start after the
  server has finished crash recovery / reached a consistent state.
- `bgw_library_name = "go_background_worker"` (`:93`) and
  `bgw_function_name = "background_main"` (`:94`) — the postmaster will `dlopen`
  `go_background_worker.so` and jump to the C symbol `background_main`.
- `bgw_name = "GoBackgroundWorker"` (`:95`) — the label in `pg_stat_activity`.
- `bgw_restart_time = BGW_NEVER_RESTART` (`:96`) — if the worker exits, the
  postmaster will not relaunch it.
- `bgw_main_arg = (Datum) 0` (`:97`) and `bgw_notify_pid = 0` (`:98`) — no
  argument is passed and no process is signalled on start/stop.

The worker entry point is `background_main` (`main_c.c:69-84`), declared
`pg_attribute_noreturn()` (`main_c.c:20`) `[verified-by-code]`. It: (1) installs
a `SIGTERM` handler via `pqsignal(SIGTERM, background_sigterm)` (`:73`); (2)
calls `BackgroundWorkerUnblockSignals()` (`:76`) to start receiving signals;
(3) calls the Go function `BackgroundWorkerMain()` (`:79`); and (4)
`proc_exit(1)` on nonzero return, else `proc_exit(0)` (`:80-83`). The signal
handler `background_sigterm` (`main_c.c:54-62`) sets a `volatile sig_atomic_t
got_sigterm` flag and `SetLatch(&MyProc->procLatch)` to wake the loop, saving
and restoring `errno` around it `[verified-by-code]` — the textbook async-signal
handler shape.

The actual main loop lives in Go (`main.go:11-34`). `BackgroundWorkerMain` is a
`//export`'d Go function (`main.go:10-11`) so cgo emits a C-callable symbol into
`_cgo_export.h`, which `main_c.c:12` includes `[verified-by-code]`. The loop
(`main.go:15-30`) is: `for C.get_got_sigterm() == 0 { rc = C.wait_latch(10000);
C.reset_latch(); if C.postmaster_is_dead(rc) != 0 { return 1 }; elog "Hello
World" }`. The four `C.*` calls are thin C wrappers (`main_c.c:23-40`,
`main_c.h:1-6`):

- `wait_latch(ms)` → `WaitLatch(&MyProc->procLatch, WL_LATCH_SET | WL_TIMEOUT |
  WL_POSTMASTER_DEATH, ms, PG_WAIT_EXTENSION)` (`main_c.c:27-32`).
- `reset_latch()` → `ResetLatch(&MyProc->procLatch)` (`main_c.c:34-36`).
- `postmaster_is_dead(rc)` → `rc & WL_POSTMASTER_DEATH` (`main_c.c:38-40`) — the
  emergency-bailout check.
- `elog_log(str)` → `elog(LOG, string, "")` (`main_c.c:23-25`).

So the control flow is a ping-pong: C owns registration + signals + the
latch/elog primitives; Go owns the loop that calls them. Compare the canonical
C-only shape in [[background-worker-startup]].

## Where it diverges from core idioms

- **A Go runtime lives inside a postmaster-forked worker.** PG's worker is a
  `fork()` of the postmaster with no `exec`; here that forked process is
  actually running the Go runtime (goroutine scheduler, garbage collector,
  signal machinery) because the `.so` was produced by `go build
  -buildmode=c-shared` (`build.bash:19`) `[verified-by-code]`. The Go runtime
  initializes when the `.so` is loaded. This is the whole trick and also the
  whole risk: Go's own signal handling and the `fork`-without-`exec` model are
  not obviously compatible, and this skeleton does nothing to reconcile them
  `[inferred]`.

- **Go GC vs PG memory contexts.** Nothing in this worker allocates PG memory,
  so the two allocators never collide here — but the template offers no guidance
  on the real hazard: a Go worker that calls `palloc` (via cgo) is mixing
  Go-GC'd heap with PG `MemoryContext` lifetimes, and a `CString` handed to C
  (as at `main.go:13,25,29`) is Go-allocated memory whose lifetime Go controls
  `[inferred]`. The `C.CString` calls here are in fact leaked (never
  `C.free`'d), which is harmless at this cadence but is not a pattern to copy
  `[verified-by-code: main.go:13,25,29]`.

- **No database connection.** Because `bgw_flags` is `BGWORKER_SHMEM_ACCESS`
  only (`main_c.c:91`), the worker never calls
  `BackgroundWorkerInitializeConnection` and therefore **cannot run SQL, open a
  transaction, or touch a relation** `[verified-by-code]`. A real worker that
  wanted to do database work would add `BGWORKER_BACKEND_DATABASE_CONNECTION`
  and call `BackgroundWorkerInitializeConnection(db, user, 0)` before its loop.
  This is the single largest thing the skeleton omits.

- **SIGTERM only, no SIGHUP / config reload.** The modern core idiom installs
  `SignalHandlerForConfigReload` on `SIGHUP` and re-reads GUCs when a flag
  fires; this template handles only `SIGTERM` (`main_c.c:73`) and has no GUCs to
  reload `[verified-by-code]`. There is also no `die`-style handler.

- **Older latch idiom.** It waits on `WL_POSTMASTER_DEATH` and manually checks
  `rc & WL_POSTMASTER_DEATH` to bail (`main_c.c:29,38-40`; `main.go:24-27`),
  rather than the newer `WL_EXIT_ON_PM_DEATH` bit that makes the wait itself
  exit the process on postmaster death `[verified-by-code]` `[inferred]`. Both
  are correct; the latter is what current core code prefers.

- **Not a SQL extension at all.** There is no `.control` file, no
  `CREATE EXTENSION`, no SQL install script — it is a pure
  `shared_preload_libraries` static bgworker `[inferred from absence + README:22-24]`.
  You install it by copying the `.so` into `pkglibdir` (`build.bash:23-26`) and
  naming it in `shared_preload_libraries`; that is the entire deployment surface.

- **`elog(LOG, string, "")` is a format-string footgun.** `elog_log`
  (`main_c.c:23-25`) passes its caller-supplied string as the *format* argument
  to `elog` and appends a spurious `""` argument. Fine for the fixed literals
  used here, but copying this wrapper with any user-controlled string is a
  format-string bug `[verified-by-code]`.

## Notable design decisions

- **Single-`.so`, Go-owns-the-object build.** `build.bash:19` runs
  `go build -buildmode=c-shared -o .build/go_background_worker.so`, with
  `CGO_CFLAGS="-I $(pg_config --includedir-server)"` (`build.bash:15`) and
  `CGO_LDFLAGS="-shared"` (`build.bash:16`) `[verified-by-code]`. The output
  `.so` is a Go-produced shared object with the C code (`main_c.c`) compiled in
  via cgo — the inverse of a normal PG extension, where the `.so` is C and links
  a helper library. It then `cp`s the result into `$(pg_config --pkglibdir)`
  (`build.bash:22-26`) `[verified-by-code]`. Note this is `c-shared` (a `.so`),
  **not** the `c-archive` (`.a`) two-stage link the task brief guessed —
  there's no separate C-link step and no Makefile.

- **`main()` is empty; the real entry is an `//export`.** `main.go:8` is
  `func main() {}` — required because `buildmode=c-shared` still needs a `main`
  package, but the library's actual entry point is the `//export
  BackgroundWorkerMain` symbol (`main.go:10-11`) that C calls `[verified-by-code]`.

- **cgo preamble includes only the C header.** `main.go:3-6` is a cgo preamble
  of just `#include "main_c.h"` then `import "C"` `[verified-by-code]`. All PG
  headers (`postgres.h`, `postmaster/bgworker.h`, `storage/latch.h`,
  `storage/proc.h`, …) are included on the C side (`main_c.c:1-12`), keeping the
  Go file free of PG's macro-heavy headers — a clean separation that avoids cgo
  choking on PG's C.

- **The latch is `MyProc->procLatch`, not a custom one.** Both `wait_latch` and
  `reset_latch` operate on `&MyProc->procLatch` (`main_c.c:28,35`)
  `[verified-by-code]` — the per-process latch the postmaster already sets on
  signal delivery, so the SIGTERM handler's `SetLatch(&MyProc->procLatch)`
  (`main_c.c:60`) is what wakes the 10-second `WaitLatch`.

- **Deliberate non-resilience.** `BGW_NEVER_RESTART` (`main_c.c:96`) plus
  `proc_exit(1)` on error (`main_c.c:80`) means any failure permanently removes
  the worker until server restart `[verified-by-code]` — a conscious "skeleton,
  not production" choice.

- **10-second poll cadence.** The loop wakes every 10000 ms (`main.go:19`),
  wrapped so the caller passes milliseconds through to `WaitLatch`
  `[verified-by-code]`.

## Links into corpus

- [[pg_background]] — the corpus's other in-tree bgworker extension; contrast
  its **dynamic** `RegisterDynamicBackgroundWorker` + `shm_mq` result channel
  with this template's **static** `RegisterBackgroundWorker` + do-nothing loop.
- [[pg_cron]] — a static bgworker (registered at `_PG_init`) that actually does
  work, via a libpq connection to its own postmaster; the natural "next step"
  from this skeleton.
- [[pgmq]] — a queue with *no* worker and *no* C, the opposite pole from this
  "all mechanism, no feature" template.
- [[pg_net]] — a worker-driven extension (background worker issuing HTTP via
  libcurl); a realistic example of the loop this template only sketches.
- [[pglite-fusion]] — another "embed a foreign runtime in PG" extension (SQLite
  in a Rust extension), a sibling in spirit to embedding Go here.
- [[background-worker-startup]] — the core idiom this template instantiates:
  `_PG_init` → `RegisterBackgroundWorker` → signal setup →
  `BackgroundWorkerUnblockSignals` → `WaitLatch` loop.
- [[bgworker-and-parallel]] — how core bgworker registration relates to the
  parallel-query worker machinery.

## Sources

- `https://raw.githubusercontent.com/prest/bgworker/main/README.md` — 200
- `https://raw.githubusercontent.com/prest/bgworker/main/main.go` — 200
- `https://raw.githubusercontent.com/prest/bgworker/main/main_c.c` — 200
- `https://raw.githubusercontent.com/prest/bgworker/main/main_c.h` — 200
- `https://raw.githubusercontent.com/prest/bgworker/main/build.bash` — 200
- `https://raw.githubusercontent.com/prest/bgworker/main/worker.c` — 404 (manifest guess; file does not exist)
- `https://raw.githubusercontent.com/prest/bgworker/main/worker.go` — 404 (manifest guess; file does not exist)
- `https://raw.githubusercontent.com/prest/bgworker/main/Makefile` — 404 (no Makefile; build is `build.bash`)
- Probed and 404: `main.c`, `bgworker.c`, `bgworker.go`, `src/worker.{c,go}`,
  `go.mod`, `go_background_worker.{c,go,h}`, `worker.h`, `GNUmakefile`,
  `Makefile.in`
