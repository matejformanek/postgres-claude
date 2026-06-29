# pg_netstat — a bgworker that runs a libpcap promiscuous packet-capture loop inside a Postgres process, with the kernel (not PG) as its data source

> Ideology note produced by the `pg-extension-anthropologist` cloud routine.
> Repo: `supabase/pg_netstat` @ branch `main`. All `file:line` cites below point
> into *that* repo (not `source/`), since this doc characterizes an external
> extension's divergence from core idioms. Cites verified against files fetched
> 2026-06-28 (see Sources footer). Read alongside `[[knowledge/ideologies/pg_net]]`
> (the other Supabase "network from a worker" case — but pg_net does *outbound
> application-layer HTTP* via libcurl, where pg_netstat does *raw link-layer
> sniffing* via libpcap), the observability siblings
> `[[knowledge/ideologies/pg_tracing]]` and `[[knowledge/ideologies/pgsentinel]]`
> (both ship a SQL-visible view over data a bgworker harvests), and the framework
> substrate `[[knowledge/ideologies/pgrx]]` (this is a `pgx 0.6.1` Rust extension).

## Domain & purpose

pg_netstat "monitors your PostgreSQL database network traffic. This extension
runs a background worker to capture network packets on the Postgres port, and
provides realtime network stats data by a view `pg_netstat`" (`README.md:9-11`)
`[from-README]`. It uses libpcap to sniff TCP packets whose source or
destination is the cluster's listen port, aggregates packet/byte counts into
fixed-interval time buckets, and exposes the last 60 buckets per device through
`SELECT * FROM pg_netstat` (`README.md:11-13`, `sql/finalize.sql:1-19`)
`[verified-by-code]`. The whole thing is a Rust/pgx extension with exactly two
non-PG crates: `pcap = "=1.0.0"` and `heapless = "=0.7.16"` (`Cargo.toml:21-23`)
`[verified-by-code]`.

The reason to document it: pg_netstat is the corpus's clearest case of an
extension whose **primary data source is the OS kernel's packet filter, not the
database**. Almost every other monitoring extension (`pgsentinel`, `pg_tracing`,
`pg_stat_statements`) samples *PG's own* in-memory/SPI state. pg_netstat instead
opens a promiscuous capture handle on a NIC and reads frames the kernel copies
up from the wire — an entirely non-PG I/O model bolted into a backend process.

## How it hooks into PG

The `shared_preload_libraries` + static-bgworker model, expressed through pgx's
Rust builders rather than the C `BackgroundWorker` struct directly:

- **`_PG_init`** initializes a shared-memory struct and registers the worker:
  `pgx::pg_shmem_init!(STATS)` then `BackgroundWorkerBuilder::new(...)
  .set_function("bg_worker_main").set_library("pg_netstat")
  .set_start_time(BgWorkerStartTime::ConsistentState).enable_shmem_access(None)
  .enable_spi_access().load()` (`src/lib.rs:250-261`) `[verified-by-code]`. The
  README confirms it must go in `shared_preload_libraries` and the server be
  restarted (`README.md:62-66`) `[from-README]`. See
  `[[knowledge/idioms/background-worker-startup]]`.
- **Shared memory** is a single `static STATS: PgLwLock<Stats> = PgLwLock::new()`
  (`src/lib.rs:248`) — pgx's `PgLwLock` wraps an LWLock-guarded shmem struct;
  `Slot` and `Stats` are marked `unsafe impl PGXSharedMemory`
  (`src/lib.rs:196, 246`) `[verified-by-code]`. See `[[knowledge/subsystems/...]]`
  note below and `[[knowledge/idioms/lwlock-rank-discipline]]`.
- **Seven GUCs**, all `GucContext::Sighup`: `pg_netstat.devices` (string),
  `.interval`, `.capture_loopback`, `.packet_wait_time`, `.pcap_buffer_size`,
  `.pcap_snaplen`, `.pcap_timeout` (`src/lib.rs:73-131`) `[verified-by-code]`.
  See `[[knowledge/idioms/guc-variables]]`.
- **SQL surface** is one set-returning function plus a view: `#[pg_extern] fn
  netstat() -> TableIterator<...>` (`src/lib.rs:263-294`) materializes every slot
  of every device into rows; `sql/finalize.sql` wraps it as `CREATE VIEW
  pg_netstat AS SELECT ... FROM netstat() ORDER BY device, ts`
  (`sql/finalize.sql:1-19`) `[verified-by-code]`. `sql/bootstrap.sql` is empty
  (0 bytes) `[verified-by-code]`. See `[[knowledge/idioms/fmgr]]`.
- **The worker connects to SPI** only to read one setting: `connect_worker_to_spi
  (Some("postgres"), None)` then a single `SELECT current_setting('port')` inside
  `BackgroundWorker::transaction(...)` (`src/lib.rs:407, 445-456`)
  `[verified-by-code]`. SPI is used to discover *which port to sniff*, not to
  move captured data — the data path bypasses PG entirely.
- **`pg_netstat.control`**: `relocatable = false`, `superuser = false`,
  `default_version = '@CARGO_VERSION@'` (cmake/cargo-templated), with the stray
  `module_pathname = '$libdir/wrappers'` left commented out — a copy-paste
  artifact from Supabase's `wrappers` FDW (`pg_netstat.control:1-6`)
  `[verified-by-code]`.

## Where it diverges from core idioms

### 1. The decisive divergence: a libpcap capture loop is the I/O model, not PG's WaitEventSet / sockets

The worker opens, per device and per direction, a live libpcap handle:
`Capture::from_device(name).buffer_size(...).snaplen(...).timeout(...).open()
.setnonblock()` then `cap.filter("tcp and dst|src port <P>", true)`
(`src/lib.rs:344-368`) `[verified-by-code]`. Each tick it drains the handle with
`while let Ok(packet) = cap.next_packet() { ... }` (`src/lib.rs:377-395`)
`[verified-by-code]`. This is a **BPF/promiscuous packet socket** (libpcap opens
an `AF_PACKET`/BPF handle and installs a kernel filter) running inside a PG
backend process. Core PG has no concept of reading from anything but its own
client sockets, files, and shared memory; here the authoritative byte source is
the NIC, copied up by the kernel filter, entirely outside PG's `WaitEventSet`,
`libpq`, and buffer manager. The packets counted include traffic that never
belongs to this backend — any TCP segment on the listen port on the captured
device(s).

### 2. Captured state lives in a Rust `heapless` shmem struct, never in a MemoryContext

The hot aggregation buffers are pgx-shmem Rust types, not palloc'd:
`Stats { interval, write_at, devices: HLVec<HLString<16>, MAX_DEVICES>, slots:
HLVec<HLVec<Slot, MAX_SLOTS>, MAX_DEVICES> }` (`src/lib.rs:198-208`), backed by
`heapless` fixed-capacity collections so the struct is `Copy`/`Clone`-able into
shared memory with no allocator at all (`Cargo.toml:23`, `src/lib.rs:196, 246`)
`[verified-by-code]`. `MAX_DEVICES = 4` and `MAX_SLOTS = 60` are compile-time
constants (`src/lib.rs:19-22`) — the "at most 60 history rows" the README warns
about (`README.md:13`). This sidesteps `[[knowledge/idioms/memory-contexts]]`
entirely: there is no `palloc`, no context lifetime, no `MemoryContextReset`; the
ring buffer's size is fixed in the type system. The per-tick *working* counters
(`Counter { slots: Vec<VecDeque<Slot>> }`, `src/lib.rs:296-330`) DO use the Rust
global allocator (std `Vec`/`VecDeque`), i.e. plain `malloc`, again bypassing
PG's memory discipline. Only the SRF return path touches palloc, implicitly via
pgx's `TableIterator` (`src/lib.rs:280-293`).

### 3. Requires `CAP_NET_RAW` / `CAP_NET_ADMIN` on the postgres binary — a privilege escalation core never asks for

Installation demands `setcap cap_net_raw,cap_net_admin=eip
/usr/local/pgsql/bin/postgres` (`README.md:34-38`) `[from-README]`. Raw packet
capture needs `CAP_NET_RAW`; without it `Capture::open()` fails. So every backend
forked from this postmaster inherits raw-socket capability — a meaningfully wider
kernel attack surface than a stock PG install, which needs no special
capabilities. Note the control file declares `superuser = false`
(`pg_netstat.control:6`): the *SQL* surface is unprivileged, but the *binary*
must be specially capability-granted at the OS level. The privilege lives below
PG's permission model, where PG cannot mediate it.

### 4. Wall-clock time-bucketing with a deliberate late-packet grace window — semantics core has no analog for

Slots are indexed by wall-clock seconds since the worker's `ts_start`:
`slot_idx = ((now - cntr.ts_start) / cfg.interval + 1)` (`src/lib.rs:486`), and a
slot is only flushed to shmem once `now > ts_start + interval + packet_wait_time`
(`src/lib.rs:514-516`) `[verified-by-code]`. The `packet_wait_time` GUC (default
5s, `src/lib.rs:99-104`) exists because pcap delivery is asynchronous — packets
for a bucket can arrive after the bucket's nominal end, so the code waits before
sealing it. Per-packet timestamps come from the *pcap header* (`hdr.ts.tv_sec`,
`src/lib.rs:380-382`), i.e. kernel capture time, not any PG clock or
`GetCurrentTimestamp()`. `as_row_tuple` then divides counts by interval to derive
`*_speed` columns (`src/lib.rs:185-191`). This is a streaming windowed-aggregate
with watermark-style lateness handling, hand-rolled in the worker loop.

### 5. SIGHUP wipes all history — config reload is destructive

On `sighup_received()` the worker reloads config and calls `cntr.reset()` +
`STATS.exclusive().reset(&cfg)` (`src/lib.rs:478-483`), and `reset` does
`self.devices.clear(); self.slots.clear()` (`src/lib.rs:231-243`)
`[verified-by-code]`. So a `pg_ctl reload` — the very mechanism the README
recommends for changing `pg_netstat.interval` (`README.md:88-94`) — silently
discards all 60×N captured buckets. The device list is also re-derived on reload,
so the ring buffer is rebuilt from empty. Core GUC `SIGHUP` reloads are expected
to be non-destructive to in-flight state; here reload == "forget everything."

### 6. `panic!`/`.expect()` as the error model — a worker that aborts the capture restarts and replays

Failures are Rust panics/`expect`, not `ereport`: `create_capture` has five
chained `.expect("... failed")` calls (`src/lib.rs:356-366`), device lookup is
`.expect("device lookup failed").expect("no device availabe")`
(`src/lib.rs:417-419`), and over-specifying devices is a bare `panic!`
(`src/lib.rs:436-442`) `[verified-by-code]`. Under pgx these unwind into a PG
`ERROR`/FATAL via `#[pg_guard]` (`src/lib.rs:398-400`), which for a bgworker means
the worker exits and the postmaster restarts it — so a transient capture failure
(e.g. a device disappearing) becomes a crash-loop rather than a logged retry. The
`assert_eq!`/`assert!` in the hot path (`src/lib.rs:212, 381`) are likewise
panic-on-violation. Contrast `[[knowledge/idioms/error-handling]]`'s `ereport`
+ elevel ladder.

### 7. Data crosses into PG only at read time, pulled through an LWLock, with no SPI/table write

Unlike `[[knowledge/ideologies/pg_net]]` (worker INSERTs results into a table) or
`pgsentinel` (worker writes a ring buffer queried via SRF), pg_netstat's worker
*writes only to shmem* under `STATS.exclusive()` (`src/lib.rs:318-319, 458, 482`)
and the SQL side *reads* it under `STATS.share()` (`src/lib.rs:280`)
`[verified-by-code]`. There is no queue table, no `pgstat_report_stat`, no SPI
write-back — the captured counters never become heap tuples until `netstat()`
synthesizes transient rows on demand. This keeps the data path off WAL and off
disk entirely (the README notes replication is "haven't tested yet, use at your
own risk", `README.md:106`).

## Notable design decisions with cites

- **Two capture handles per device (in + out)**, distinguished by a BPF filter
  on `dst port` vs `src port`, because libpcap's `Direction` is mapped onto the
  filter string rather than `cap.direction()` (`src/lib.rs:344-368, 463-467`)
  `[verified-by-code]`. In/out counts are thus two independent kernel filters.
- **Non-blocking pcap (`.setnonblock()`) drained to exhaustion each 1s tick**:
  the worker `wait_latch(Some(Duration::from_secs(1)))` loops, and on each wake
  drains every handle via `next_packet()` until `Err` (`src/lib.rs:363, 377,
  477`) `[verified-by-code]`. Sleep is PG's latch, work is pcap's queue — two
  event sources stitched together by hand.
- **Device auto-detection** uses `pcap::Device::lookup()` when
  `pg_netstat.devices` is unset, and `find_loopback()` scans `Device::list()`
  for `IfFlags::LOOPBACK` when `capture_loopback` is on (`src/lib.rs:332-341,
  414-428`) `[verified-by-code]` — device discovery is libpcap's, not PG's.
- **Port is the only thing read from PG**, via a one-shot SPI
  `current_setting('port')` marshalled through a `Mutex<i32>` because the pgx
  `transaction` closure can't return a value directly (`src/lib.rs:445-456`)
  `[verified-by-code]`.
- **Ring write index is shared, not per-device**: `write_at = (write_at + 1) %
  MAX_SLOTS` advances once per flush across all devices (`src/lib.rs:228`), and
  `Stats::write` overwrites `tgt[self.write_at]` once a device's vec is full
  (`src/lib.rs:211-229`) `[verified-by-code]`.
- **`pg_test` is a stub**: the only test is `fn test_pg_netstat() { todo!(); }`
  (`src/lib.rs:527-530`) `[verified-by-code]` — there is effectively no automated
  test coverage, unsurprising given the capture path needs a live NIC +
  capabilities.
- **PG 14/15 only** (`README.md:104`, `Cargo.toml:5-11` enumerates pg11-pg15
  features but `default = ["pg14"]`), Windows unsupported "inherits from pgx"
  (`README.md:103`) `[from-README]`.

## Links into corpus

- `[[knowledge/ideologies/pg_net]]` — the sibling Supabase "network from a
  worker" extension; the deliberate contrast (outbound HTTP/libcurl + queue
  tables vs inbound raw capture/libpcap + shmem-only). Read together.
- `[[knowledge/ideologies/pg_tracing]]`, `[[knowledge/ideologies/pgsentinel]]` —
  observability siblings that also expose a SQL view over worker-harvested data,
  but sample *PG's own* state rather than the kernel's packet stream.
- `[[knowledge/ideologies/pgrx]]` — the Rust/pgx framework substrate
  (`#[pg_extern]`, `#[pg_guard]`, `BackgroundWorkerBuilder`, `PgLwLock`,
  `GucSetting`, `TableIterator`, `pg_shmem_init!`).
- `[[knowledge/idioms/background-worker-startup]]` — the static
  `shared_preload_libraries` bgworker registered in `_PG_init`, `wait_latch` loop,
  SIGHUP/SIGTERM handlers.
- `[[knowledge/idioms/memory-contexts]]` — the contrast: heapless fixed-capacity
  shmem + std `Vec` working buffers, no MemoryContext anywhere on the data path.
- `[[knowledge/idioms/lwlock-rank-discipline]]` — `PgLwLock<Stats>` guarding the
  shmem ring with `.share()`/`.exclusive()`.
- `[[knowledge/idioms/fmgr]]` — the `netstat()` set-returning function feeding the
  `pg_netstat` view.
- `[[knowledge/idioms/spi]]` — the single `current_setting('port')` SPI read; SPI
  is used for config discovery, not for the data path.
- `[[knowledge/idioms/error-handling]]` — the contrast: `panic!`/`.expect()` as
  the error model instead of `ereport`.
- `[[knowledge/idioms/guc-variables]]` — the seven `Sighup` GUCs.

> Corpus gap: no `idioms/external-event-loop-in-bgworker.md`. pg_netstat (libpcap
> drain) and pg_net (epoll/kqueue + libcurl reactor) both stitch a foreign I/O
> source into a PG bgworker's latch loop; an idioms note would anchor both.
> `[inferred]`

## Sources

Fetched 2026-06-28 via `raw.githubusercontent.com/supabase/pg_netstat/main`:

- `README.md` @ 2026-06-28 → 200
- `pg_netstat.control` @ 2026-06-28 → 200
- `Cargo.toml` @ 2026-06-28 → 200
- `src/lib.rs` @ 2026-06-28 → 200 (the entire implementation — single file)
- `sql/bootstrap.sql` @ 2026-06-28 → 200 (empty, 0 bytes)
- `sql/finalize.sql` @ 2026-06-28 → 200
- `.cargo/config` @ 2026-06-28 → 200 (`dynamic_lookup` linker flag for PG symbols)
- `https://api.github.com/repos/supabase/pg_netstat/git/trees/main?recursive=1`
  @ 2026-06-28 → 200 (file discovery)

No manifest gaps. The repo is small: the only files not cited above are
`LICENSE`, `.gitignore`, `rustfmt.toml`, and `.github/workflows/release.yml`
(CI release packaging; skimmed-not-fetched, no bearing on the divergence story).
</content>
</invoke>
