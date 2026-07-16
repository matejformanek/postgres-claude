# pg_turret — ideology / divergence notes

Extension: **lasect/pg_turret** (`main`, control `comment = 'pg_turret:  Created
by pgrx'`, `default_version = '0.0.0'`, `relocatable = false`, `superuser =
true`, `trusted = false`) `[verified-by-code: pg_turret.control:1-6]`. A
pgrx/Rust extension that hooks PostgreSQL's `emit_log_hook`, normalizes every
`ErrorData` event into a fixed-layout record in a shared-memory ring buffer, and
drains that ring from background workers that stream the events as structured
JSON to external observability destinations (HTTP, Kafka, Sentry). The README
frames it as turning Postgres "from a log file producer into a structured event
source for modern observability platforms" `[from-README: README.md:3]`. It is
the log-export counterpart to [[pg_net]]'s HTTP-export and [[pg_stat_ch]]'s
query-telemetry-export, built on the [[pgrx]] substrate.

> Ideology note produced by the `pg-extension-anthropologist` cloud routine.
> All `file:line` cites point into the fetched pg_turret repo files
> (`pg_turret.control`, `Cargo.toml`, `README.md`, `src/lib.rs`,
> `src/log_capture.rs`, `src/metrics.rs`, `src/config/mod.rs`,
> `src/config/http.rs`, `src/config/kafka.rs`, `src/config/sentry.rs`), NOT into
> `source/`. Verified against files fetched 2026-07-15 (see Sources). Cluster:
> the "network-egress-from-a-worker" family ([[pg_net]], [[pgsql-http]],
> [[pg_amqp]], [[pg_tracing]]) crossed with the "backend-private static footgun"
> family ([[wasmer-postgres]], [[pg-extend-rs]], [[pgrx]]).

---

## Domain & purpose

pg_turret captures log events at the point PostgreSQL emits them, rather than
tailing a log file or running a sidecar. The pitch: `Postgres logs → pg_turret →
structured events → Observability systems` `[from-README: README.md:9-11]`. The
foreground capture path is deliberately thin — it only decodes an `ErrorData`
into a fixed-size struct and pushes it into a shared-memory ring — while all
network I/O is deferred to background workers that batch, filter, compress, and
retry `[from-README: README.md:15-23]`. Each event becomes a JSON object with
`timestamp/level/message/detail/hint/context/sqlerrcode/filename/lineno/funcname/
database/user/query` `[from-README: README.md:158-174]`. Three adapters ship
(HTTP, Kafka, Sentry); Axiom / Datadog / S3 / WebSockets are advertised as
"coming soon" `[from-README: README.md:146-151]` — note `tungstenite` is already
a dependency `[verified-by-code: Cargo.toml:39]` but no `websocket` adapter
module exists in the tree (probed `src/config/websocket.rs` → HTTP 404).

---

## How it hooks into PG

This is the **`shared_preload_libraries` + shmem ring + N background workers**
model, built entirely through pgrx wrappers:

- **`shared_preload_libraries` requirement.** The README requires
  `shared_preload_libraries = 'pg_turret'` and a restart
  `[from-README: README.md:55-59]`; the control file marks it
  `superuser = true`, `trusted = false`, `relocatable = false`
  `[verified-by-code: pg_turret.control:4-6]`. Unlike [[pg_net]]'s `_PG_init`,
  pg_turret's `_PG_init` does **not** guard on
  `process_shared_preload_libraries_in_progress` — it never errors if loaded
  outside `shared_preload_libraries` `[verified-by-code: src/lib.rs:573-612]`.

- **`_PG_init`** (a `#[pg_guard] pub extern "C-unwind"` fn) does five things in
  order: registers ~35 GUCs `[verified-by-code: src/lib.rs:575,87-494]`;
  `pg_shmem_init!(LOG_RING_BUFFER)` to reserve the shmem ring + its LWLock
  `[verified-by-code: src/lib.rs:579]`; chains its own `shmem_startup_hook`
  `[verified-by-code: src/lib.rs:583-586]`; inits metrics
  `[verified-by-code: src/lib.rs:593]`; and spawns `num_workers` (1–8)
  background workers `[verified-by-code: src/lib.rs:596-611]`.

- **The `emit_log_hook` is installed late, from `shmem_startup_hook`, not
  `_PG_init`.** A comment explains why: setting it in `_PG_init` would fire the
  hook "during initdb (bootstrap mode) when shared memory isn't fully ready"
  `[verified-by-code: src/lib.rs:588-590]`. So `turret_shmem_startup` runs the
  previous shmem hook first, calls `mark_shmem_ready()`, then `set_hook()`
  `[verified-by-code: src/lib.rs:616-626]`. `emit_log_hook` is the core-provided
  interception point in `errfinish`; core ships it deliberately for extensions
  to observe/rewrite an `ErrorData` before it reaches the log destination — used
  here read-only for capture. See [[bgworker-and-parallel]].

- **Background workers via the pgrx `BackgroundWorkerBuilder`.**
  `set_function("background_worker_main")`, `set_library("pg_turret")`,
  `BgWorkerStartTime::RecoveryFinished`, `set_restart_time(Some(5s))`,
  `enable_shmem_access(None)`, `.load()`
  `[verified-by-code: src/lib.rs:604-610]`. Worker 0 is named `pg_turret`, the
  rest `pg_turret_<n>` `[verified-by-code: src/lib.rs:597-603]`. The worker main
  attaches SIGHUP+SIGTERM handlers and loops on `wait_latch(poll_interval)`
  `[verified-by-code: src/lib.rs:708-719]`.

- **~35 GUCs, all `GucContext::Sighup`**, defined via pgrx `GucRegistry`
  (`pg_turret.http.*`, `pg_turret.kafka.*`, `pg_turret.sentry.*`,
  `pg_turret.filter.*`, `pg_turret.retry.*`, `poll_interval_s`,
  `ring_buffer_size`, `num_workers`)
  `[verified-by-code: src/lib.rs:87-494]`. See [[guc-variables]].

- **SQL surface** is a handful of `#[pg_extern]` reader functions:
  `get_captured_logs_count`, `get_metrics`, `get_sentry_status`,
  `configure_sentry(...)` `[verified-by-code: src/lib.rs:498-570,
  src/metrics.rs:9-53]`.

---

## Where it diverges from core idioms

### 1. `emit_log_hook` chaining is NOT done — the previous hook is clobbered

This is the sharpest divergence. `set_hook()` installs the callback with a bare
assignment and **never saves or calls the prior `emit_log_hook`**:

```rust
pub fn set_hook() {
    unsafe { pgrx::pg_sys::emit_log_hook = Some(emit_log_hook_func); }
}
```

`[verified-by-code: src/log_capture.rs:774-778]`. And `emit_log_hook_func`
itself has no `prev_hook()` call anywhere in its body
`[verified-by-code: src/log_capture.rs:716-772]`. The core idiom for every
`_hook` global is *save the old value, call it (usually first), then do your
work* — exactly what pg_turret **does** correctly one function up for the shmem
hook (`PREV_SHMEM_STARTUP_HOOK = pg_sys::shmem_startup_hook; ... if let Some(prev)
= PREV_SHMEM_STARTUP_HOOK { prev(); }`)
`[verified-by-code: src/lib.rs:583-586, 616-621]`. The author knows the chaining
discipline and applied it to `shmem_startup_hook` but not to `emit_log_hook`.
Consequence: if any other extension loaded in `shared_preload_libraries` after
pg_turret has installed an `emit_log_hook` (auto_explain-style loggers, other
capture extensions), pg_turret silently overwrites it and that extension's log
interception stops firing; symmetrically, whoever loads *after* pg_turret
clobbers pg_turret. `[verified-by-code: src/log_capture.rs:774-778]` — a genuine
correctness bug, not a style nit.

### 2. Real work inside the log-emit path — allocation-heavy, LWLock-taking

`emit_log_hook_func` runs synchronously inside `errfinish`, in the foreground
backend, potentially at `ERROR`/`FATAL` and inside memory-pressure or
error-recovery paths. Core's contract is that this code must be cheap and
reentrancy-safe. pg_turret guards the front of the function well — null check,
`HOOK_SUPPRESSED` check, `SHMEM_READY` check, then a cheap integer level gate
before any string work `[verified-by-code: src/log_capture.rs:717-738]` — but
once a message passes the gate it is **not** allocation-light:

- It locks a `std::sync::Mutex` (`FILTER_CONFIG.lock()`) up to twice per event
  `[verified-by-code: src/log_capture.rs:732,742]`.
- `build_shm_entry` allocates: `chrono::Utc::now().to_rfc3339()` (a `String`)
  plus a `to_string()` per non-null `ErrorData` field (message, detail, hint,
  context, filename, funcname, query)
  `[verified-by-code: src/log_capture.rs:668-709]`.
- It then acquires the ring-buffer **LWLock** (`LOG_RING_BUFFER.exclusive()`)
  and pushes `[verified-by-code: src/log_capture.rs:766-767]`.

Allocating and taking an LWLock while emitting a `FATAL`/`PANIC` (or an OOM
error) is the delicate scenario core warns about. It does *not* do network I/O
in the hook — that is correctly deferred to the worker via the ring — so the
worst case is added latency/lock contention on the logging path, not a network
stall. It also reads the `debug_query_string` global to fill `query`, with a
candid comment that the pointer "may be null or point to freed memory"
`[verified-by-code: src/log_capture.rs:676-685]` `[from-comment: src/log_capture.rs:681-682]`
— reading a possibly-stale global in the log path is a latent hazard.

### 3. The capture→worker handoff uses REAL shared memory — the footgun avoided here

Unlike the classic pgrx `static`-state footgun ([[wasmer-postgres]],
[[pg-extend-rs]]), the ring buffer is a genuine cross-backend shared-memory
segment: `pub static LOG_RING_BUFFER: PgLwLock<ShmLogRingBuffer>`
`[verified-by-code: src/log_capture.rs:511-512]`, reserved in `_PG_init` via
`pg_shmem_init!` `[verified-by-code: src/lib.rs:579]`. The entry type is
pointer-free by construction — fixed-size inline `ShmStr<N>`/`ShmOptStr<N>`
byte arrays (`#[repr(C)]`, `unsafe impl PGRXSharedMemory`), never `String`/heap
pointers `[verified-by-code: src/log_capture.rs:273-370]`. That is exactly the
right discipline for shmem: no address that would be invalid in another
process. Foreground backends `push` under the LWLock
`[verified-by-code: src/log_capture.rs:766-767]`; workers `drain` under the same
lock `[verified-by-code: src/log_capture.rs:607-612, 470-482]`. So the primary
event pipe is cross-backend-correct.

### 4. …but the metrics counters and per-process config ARE backend-private statics

The footgun re-appears everywhere *except* the ring. The cumulative counters are
plain process-local statics:

```rust
pub static LOGS_CAPTURED: AtomicU64 = AtomicU64::new(0);
pub static LOGS_DROPPED:  AtomicU64 = AtomicU64::new(0);
pub static LOGS_SENT:     AtomicU64 = AtomicU64::new(0);
pub static LOGS_RETRY_FAILED: AtomicU64 = AtomicU64::new(0);
```

`[verified-by-code: src/log_capture.rs:76-79]`. Under the per-connection fork
model each backend/worker gets its own copy. `LOGS_DROPPED` is bumped in the
**foreground** backend inside the hook
`[verified-by-code: src/log_capture.rs:770]`; `LOGS_CAPTURED`/`LOGS_SENT` are
bumped in the **worker** `[verified-by-code: src/log_capture.rs:610,
src/lib.rs:759,777]`; and `get_metrics()` runs in yet a **third** process (the
querying backend), which sees only its own zeroed counters
`[verified-by-code: src/metrics.rs:9-34]`. Net effect: `get_metrics()` returns
near-zero for `logs_captured/logs_dropped/logs_sent/logs_retry_failed` regardless
of real traffic — only `logs_pending`/`ring_buffer_capacity`, which read the
shmem ring, are accurate `[verified-by-code: src/log_capture.rs:621-628]`. A
verifiable observability bug born of the static-vs-shmem split. `[inferred]`
(fork-model copy semantics).

A subtler instance: the **filter config the hook reads is a different
process-local copy than the one the GUCs feed.** `emit_log_hook_func` reads the
`FILTER_CONFIG` static `[verified-by-code: src/log_capture.rs:732,742]`, but
`set_filter_config` (which copies `pg_turret.filter.*` GUCs → `FILTER_CONFIG`) is
only called from `sync_worker_config`, which only runs in
`background_worker_main` `[verified-by-code: src/lib.rs:685-693,712,722,
628]`. Foreground backends never populate `FILTER_CONFIG`, so at capture time
they always use the **defaults** (`level_min = 10`, no include/exclude patterns)
`[verified-by-code: src/log_capture.rs:40-48]` — the user's configured
`filter.level_min` and regex patterns are not applied in the foreground capture
path; they only take effect for whatever the worker re-filters. `[verified-by-code:
src/log_capture.rs:731-762]` + `[inferred]`.

### 5. Config side-channel: a JSON file in DataDir + `pg_reload_conf()`

Because the Sentry config is set through a SQL function (`configure_sentry`) in
one backend but consumed in the worker process — and they share no static —
pg_turret bridges them through the filesystem. `configure_sentry` validates the
DSN, serializes `SentryConfig` to JSON, `write_config_atomic`s it to
`$DataDir/pg_turret_sentry.json` (temp file + POSIX `rename`), then runs
`SELECT pg_reload_conf()` to SIGHUP the workers
`[verified-by-code: src/lib.rs:519-570, 64-79]`. On SIGHUP the worker's
`sync_worker_config` reads the JSON back and applies it
`[verified-by-code: src/lib.rs:673-683]`. This is a hand-rolled IPC channel
(atomic-rename file + signal) standing in for what core extensions would do with
shared memory or a catalog table — novel, and fragile (a stale/partial JSON, or
a `DataDir` that differs from the worker's, silently drops config). HTTP/Kafka
config, by contrast, ride the normal GUC→`sync_worker_config` path
`[verified-by-code: src/lib.rs:628-661]`.

### 6. Network egress: synchronous blocking clients, serialized in the worker loop

All three adapters do **blocking** network I/O — the divergence from [[pg_net]]
(async `curl_multi` reactor) and the similarity to [[pgsql-http]] (sync
`curl_easy`), except pg_turret runs the blocking calls in the dedicated worker
rather than the user backend:

- **HTTP**: `reqwest::blocking::Client`, per-batch `request.send()`
  `[verified-by-code: src/config/http.rs:10-29,144-181]`, optional gzip via
  `flate2::GzEncoder` `[verified-by-code: src/config/http.rs:159-172]`, Bearer
  auth `[verified-by-code: src/config/http.rs:147-149]`.
- **Kafka**: the synchronous `kafka` crate `Producer`, recreated per send
  "for simplicity and reliability", with an in-call retry loop for
  `UnknownTopicOrPartition` that (correctly) does **not** sleep but returns an
  error so the worker retries next poll
  `[verified-by-code: src/config/kafka.rs:72-79,109-166,188-234]`.
- **Sentry**: `sentry::init` guard + `capture_event`, flushed by dropping the
  `ClientInitGuard` (2-second flush deadline) after each batch
  `[verified-by-code: src/config/sentry.rs:147-159,337,340-346]`.

In `background_worker_main` the enabled adapters are sent **sequentially** in a
`for adapter in &adapters` loop `[verified-by-code: src/lib.rs:726-778]`. With
the default `num_workers = 1` `[verified-by-code: src/lib.rs:55]`, one slow or
hung endpoint (bounded only by each adapter's own timeout, e.g. HTTP
`timeout_ms` default 5000) stalls the entire poll cycle and every other adapter
behind it. This does not block user queries (they only `push` to the ring), but
it does throttle drain throughput and can overflow the ring under load.

### 7. `panic = "unwind"` + the pgrx ereport↔panic boundary — with one gap

`Cargo.toml` sets `panic = "unwind"` in both `dev` and `release` profiles
`[verified-by-code: Cargo.toml:46-50]`, and every FFI callback uses the
`extern "C-unwind"` ABI so a Rust `panic!` can unwind through pgrx's guard and be
converted to `ereport` instead of aborting across a plain-`"C"` frame (see
[[pgrx]], [[error-handling]]). `_PG_init` and `background_worker_main` are both
`#[pg_guard] extern "C-unwind"`
`[verified-by-code: src/lib.rs:573-574,705-707]`. **But `emit_log_hook_func` is
`extern "C-unwind"` without `#[pg_guard]`**
`[verified-by-code: src/log_capture.rs:716]` and is assigned straight into
`emit_log_hook` `[verified-by-code: src/log_capture.rs:776]`. A panic inside the
hook would therefore unwind directly into `errfinish`'s C frame with no pgrx
catch. In practice the hook is written to avoid panics (every `.lock()` is
`match`ed with a fail-open/closed arm; string decode uses `unwrap_or_default`;
`ShmStr::as_str` uses `unwrap_or`)
`[verified-by-code: src/log_capture.rs:302-306,732-762,683,686-691]`, so it is
panic-free by construction — but the missing guard on the one callback that runs
inside PG's error machinery is an inconsistency worth flagging.

### 8. Reentrancy / recursive-logging guard — present, correctly scoped

`HOOK_SUPPRESSED` (a process-local `AtomicBool`) short-circuits the hook
`[verified-by-code: src/log_capture.rs:17-22,721-723]`. The Sentry adapter sets
it around its send, because `sentry::init`/`capture_event` (via
`reqwest`/`rustls`) can themselves emit logs that would re-enter the hook in the
worker and recurse: `suppress_hook(true) … capture_event … suppress_hook(false)`
`[verified-by-code: src/config/sentry.rs:316-317,336-337,354]`. Because the flag
is process-local and the worker is the process doing the send, the scoping is
exactly right — reentrancy is a real concern any `emit_log_hook` consumer must
handle, and pg_turret handles it. (The HTTP and Kafka adapters do not suppress;
their client libraries log through Rust's `log` facade, not PG's `ereport`, so
they cannot re-enter `emit_log_hook`.) `[inferred]`.

### 9. Loss model: in-memory ring, drop-oldest, no durability at all

The ring overwrites the oldest entry when full and bumps an in-shmem `dropped`
counter `[verified-by-code: src/log_capture.rs:443-457]`. There is no queue
table, no WAL, no unlogged table — even [[pg_net]] keeps its queue in (unlogged)
tables; pg_turret's pending events live only in shmem, so a crash or restart
loses everything not yet drained. This is a deliberate "observability is
best-effort" stance, more lossy than pg_net's at-most-once. The retry queue is
similarly ephemeral and process-local (`RETRY_QUEUE: Lazy<Mutex<VecDeque<…>>>`,
capped, drop-oldest) `[verified-by-code: src/log_capture.rs:72,173-199]`, so a
batch that fails in worker A and lands in A's retry queue is invisible to worker
B.

### Contrast table

| axis | [[pgsql-http]] | [[pg_net]] | pg_turret |
|---|---|---|---|
| trigger | SQL call | SQL call → queue table | `emit_log_hook` (log events) |
| placement of I/O | foreground backend | one bgworker | N bgworkers |
| network mode | `curl_easy` blocking | `curl_multi` + epoll reactor | `reqwest`/`kafka` **blocking**, serialized |
| foreground→worker handoff | n/a | unlogged queue table | **shmem ring (LWLock)** |
| hook chaining | n/a | n/a | **NOT chained (clobbers prev)** |
| durability | synchronous | unlogged, lost on crash | in-memory ring, lost on crash |
| metrics | n/a | queue tables | **backend-private statics (fragmented)** |

---

## Notable design decisions

- **`emit_log_hook` installed from `shmem_startup_hook`, not `_PG_init`**, to
  dodge bootstrap/initdb firing before shmem is ready.
  `[verified-by-code: src/lib.rs:588-590,616-626]`
- **`emit_log_hook` is not chained** — bare assignment, previous hook never
  saved or called; a real bug given the shmem hook one function above *is*
  chained. `[verified-by-code: src/log_capture.rs:774-778, src/lib.rs:583-586]`
- **Pointer-free `#[repr(C)]` shmem entries** (`ShmStr<N>`/`ShmOptStr<N>` inline
  byte arrays) — correct shmem discipline; no cross-process-invalid pointers.
  `[verified-by-code: src/log_capture.rs:273-370]`
- **Cumulative metrics are process-local `AtomicU64` statics**, incremented in
  three different processes and read in a fourth → `get_metrics()` is
  effectively always near-zero except `logs_pending`.
  `[verified-by-code: src/log_capture.rs:76-79, src/metrics.rs:9-34]`
- **Foreground filter uses defaults**: the hook reads a `FILTER_CONFIG` static
  that only the worker ever populates, so GUC `filter.*` (level/regex) is not
  applied at capture time in user backends.
  `[verified-by-code: src/log_capture.rs:40-48,731-762, src/lib.rs:685-693,712]`
- **Sentry config crosses processes via a JSON file in `DataDir` + atomic
  rename + `pg_reload_conf()`**, a hand-rolled filesystem IPC channel.
  `[verified-by-code: src/lib.rs:519-570,673-683]`
- **All adapters block; sent sequentially under `num_workers=1` default** — a
  slow endpoint stalls the whole drain cycle.
  `[verified-by-code: src/lib.rs:726-778, src/config/http.rs:179, src/config/kafka.rs:110]`
- **Kafka retry does not sleep in-call** — returns an error to defer to the next
  poll, avoiding blocking inside the send. Good.
  `[verified-by-code: src/config/kafka.rs:116-151]`
- **`emit_log_hook_func` lacks `#[pg_guard]`** while other callbacks have it; a
  panic in the hook would unwind into `errfinish` uncaught (mitigated by
  panic-free coding). `[verified-by-code: src/log_capture.rs:716, src/lib.rs:705]`
- **`database`/`user` JSON fields are always null**: catalog lookups are skipped
  in the hook (comment: they "can crash during initdb/early startup"), so the
  README's example object over-promises those two fields.
  `[verified-by-code: src/log_capture.rs:671-674,705-706]` `[from-comment: src/log_capture.rs:671-673]`
- **`_PG_init` does not enforce `shared_preload_libraries`** (no
  `process_shared_preload_libraries_in_progress` guard), unlike [[pg_net]].
  `[verified-by-code: src/lib.rs:573-612]`
- **Per-worker Sentry rate limiter + client-side sample rate** protect the DB
  and Sentry from firehoses; a 1-second token window.
  `[verified-by-code: src/config/sentry.rs:82-109,206-219]`
- **`tungstenite` dependency without a WebSocket adapter** — declared coming
  soon; dead dependency for now.
  `[verified-by-code: Cargo.toml:39]` + `[from-README: README.md:146-151]`

---

## Links into corpus

- [[pg_net]] — the async-worker HTTP-export foil: same "offload network to a
  bgworker" instinct, but pg_net uses an async `curl_multi` reactor + unlogged
  queue *tables*, where pg_turret uses blocking clients + a shmem ring.
- [[pgsql-http]] — the synchronous blocking-client sibling; pg_turret uses the
  same blocking model but moved off the foreground into workers.
- [[pg_stat_ch]] — sibling this run: query-telemetry-export counterpart (the
  "ship structured DB events to an external system" family).
- [[pgrx]] — the substrate: `pg_shmem_init!`, `PgLwLock`, `GucRegistry`,
  `BackgroundWorkerBuilder`, `#[pg_extern]`, `#[pg_guard]`, `extern "C-unwind"`,
  `panic = "unwind"`.
- [[wasmer-postgres]], [[pg-extend-rs]] — the backend-private `static` footgun
  siblings; pg_turret dodges it for the ring but falls into it for metrics/config.
- [[pg_tracing]], [[pg_amqp]] — other "emit DB-internal events to an external
  observability/message system" extensions.
- [[bgworker-and-parallel]] — `RegisterBackgroundWorker`, `bgw_*`, the
  `wait_latch` + SIGHUP/SIGTERM worker skeleton.
- [[guc-variables]] — the ~35 `GucContext::Sighup` GUCs.
- [[memory-contexts]] — the allocation-in-the-log-path concern (Rust `String`s +
  chrono in `build_shm_entry`).
- [[locking-overview]] — the ring-buffer `PgLwLock` acquired on the capture path.
- [[error-handling]] — `emit_log_hook` runs inside `errfinish`; the missing
  `#[pg_guard]` and the panic↔ereport boundary.

> Corpus gap: no `idioms/emit-log-hook.md`. The chaining discipline pg_turret
> violates here (save-and-call-prev), the "install late from shmem_startup to
> avoid bootstrap" trick, and the reentrancy-guard pattern would anchor a future
> idioms note on log-hook extensions. `[inferred]`

---

## Sources

All fetched 2026-07-15 from `https://raw.githubusercontent.com/lasect/pg_turret/main/`:

- `pg_turret.control` — HTTP 200
- `Cargo.toml` — HTTP 200
- `README.md` — HTTP 200
- `src/lib.rs` — HTTP 200 (781 lines; `_PG_init`, GUCs, worker main, shmem hook)
- `src/log_capture.rs` — HTTP 200 (778 lines; ring buffer, `emit_log_hook_func`,
  `set_hook`, filter, retry queue, metrics counters — the load-bearing file)
- `src/metrics.rs` — HTTP 200
- `src/config/mod.rs` — HTTP 200 (`Adapter` trait, `StreamType`)
- `src/config/http.rs` — HTTP 200
- `src/config/kafka.rs` — HTTP 200
- `src/config/sentry.rs` — HTTP 200

Gaps (probed, HTTP 404 — do not exist on `main`): `src/config.rs`,
`src/log_capture/mod.rs` (log_capture is a single file, not a directory),
`src/config/websocket.rs`, `src/log_capture/{hook,event,ring,filter,retry}.rs`.
GitHub git/trees API and MCP `get_file_contents` 403 for this repo; only
`raw.githubusercontent.com` returns 200, so module layout was discovered by
reading `pub mod`/`use` declarations in `src/lib.rs` and `src/config/mod.rs` and
probing candidate paths.
