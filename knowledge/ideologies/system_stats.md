# system_stats — a monitoring extension that inverts pg_stat_*: it answers SQL from the OS kernel (/proc, sysctl, uname, WMI) instead of from Postgres' own shared state

> Ideology note produced by the `pg-extension-anthropologist` cloud routine.
> Repo: `EnterpriseDB/system_stats` @ branch `master`. All `file:line` cites
> below point into *that* repo (not `source/`), since this doc characterizes an
> external extension's divergence from core idioms. Cites verified against files
> fetched on 2026-06-28 (see Sources footer). Line numbers are for the `master`
> blobs as fetched.
>
> Read alongside `[[knowledge/ideologies/pgsentinel]]` and
> `[[knowledge/ideologies/pg_tracing]]` — both observability siblings — but note
> the key contrast: those two read *Postgres* internals (parse state, wait
> events, spans), whereas system_stats reads the *operating system* and reports
> host-level facts that have nothing to do with the PG instance issuing the
> query.

## Domain & purpose

system_stats is "a Postgres extension that provides functions to access system
level statistics that can be used for monitoring. It supports Linux, macOS and
Windows" (`README.md:2-4`) `[from-README]`. It exposes ten SQL-callable
set-returning functions — `pg_sys_os_info`, `pg_sys_cpu_info`,
`pg_sys_cpu_usage_info`, `pg_sys_memory_info`, `pg_sys_io_analysis_info`,
`pg_sys_disk_info`, `pg_sys_load_avg_info`, `pg_sys_process_info`,
`pg_sys_network_info`, `pg_sys_cpu_memory_by_process`
(`system_stats.c:57-66`, `README.md:70-102`) `[verified-by-code]` — each of
which returns OS-level metrics (kernel name, CPU model, RAM, swap, disk inodes,
per-PID CPU/memory) read live from the host at call time. "Note that not all
values are relevant on all operating systems. In such cases NULL is returned for
affected values" (`README.md:6-7`) `[from-README]`; the Linux memory reader, for
instance, hard-NULLs the five Windows-only columns
(`linux/memory_info.c:112-117`) `[verified-by-code]`.

The reason to document it: system_stats is the corpus's clearest case of an
extension that uses Postgres purely as a **query transport for host telemetry**.
Core `pg_stat_*` views read PG-internal counters out of shared memory (the
stats collector / `pgstat.c` shmem); system_stats reads `/proc`, `sysconf`,
`uname(2)`, `sysinfo(2)`, and (on Windows) WMI. The SQL surface is identical in
shape to `pg_stat_activity`, but the data source is the kernel, not the
backend.

## How it hooks into PG

Pure fmgr SRF extension — no background worker, no shared memory, no GUCs, no
hooks on `_PG_init`:

- **`_PG_init` is nearly empty.** It only `ereport(DEBUG1, …)`s a load message,
  and on Windows initializes the WMI COM connection; there is no
  `RegisterBackgroundWorker`, no `RequestAddinShmemSpace`, no
  `ProcessUtility_hook` (`system_stats.c:68-84`) `[verified-by-code]`. Confirms
  the "no bgworker / no shmem" claim by absence.
- **Ten `PG_FUNCTION_INFO_V1` SRFs** (`system_stats.c:57-66`), each declared in
  SQL as `RETURNS SETOF record` with named `OUT` params and bound to
  `MODULE_PATHNAME` `LANGUAGE C` (`system_stats--4.0.sql:25-39` for
  `pg_sys_os_info`; same pattern for all ten) `[verified-by-code]`.
- **Every SRF uses Materialize mode, not ValuePerCall.** Each entry point
  rejects a non-`SFRM_Materialize` caller, switches into
  `rsinfo->econtext->ecxt_per_query_memory`, builds the tupdesc via
  `get_call_result_type`, opens a `tuplestore_begin_heap(true, false, work_mem)`,
  sets `rsinfo->returnMode = SFRM_Materialize` / `setResult` / `setDesc`, switches
  back, then delegates to a platform `Read*` function that fills the tuplestore
  (`system_stats.c:92-136` for `pg_sys_os_info`; identical scaffold repeated ten
  times through `system_stats.c:606`) `[verified-by-code]`. The C entry point
  owns only the tuplestore plumbing; the actual OS read lives in the
  per-platform `.c` file.
- **The control file is plain and relocatable.** `default_version = '4.0'`,
  `relocatable = true`, comment `'EnterpriseDB system statistics for
  PostgreSQL'` (`system_stats.control:1-5`) `[verified-by-code]`. The install SQL
  carries the whole interface; upgrade scripts `1.0→2.0` and `2.0→3.0` are
  no-ops ("No function has changed") and only `3.0→4.0` actually
  `DROP FUNCTION`/recreates `pg_sys_cpu_memory_by_process` to add four columns
  (`system_stats--3.0--4.0.sql:1-30`) `[verified-by-code]`.

## Where it diverges from core idioms

### 1. The decisive inversion: SQL answered from the OS kernel, not from PG's own state

Core monitoring (`pg_stat_activity`, `pg_stat_bgwriter`, …) reads counters
Postgres itself maintains in shared memory. system_stats reads the *host*:
memory comes from parsing `/proc/meminfo` line-by-line with `getline` + `strstr`
(`linux/memory_info.c:34-119`, file path macro `MEMORY_FILE_NAME
"/proc/meminfo"` at `system_stats.h:136`); OS identity comes from `uname(2)` +
`/etc/os-release` + `sysinfo(2)` uptime (`linux/os_info.c:210-219, 245-290,
312-315`); CPU cache sizes are read straight out of
`/sys/devices/system/cpu/cpu0/cache/index*/size`
(`linux/cpu_info.c:15-18, 23-70`) `[verified-by-code]`. The returned rows
describe the machine, not the database. A query against
`pg_sys_memory_info()` on a replica reports the replica host's RAM — there is no
PG-internal datum involved at all. `[inferred]` from the read paths above.

### 2. Per-platform `#ifdef`/directory sprawl: the same SRF has four divergent bodies

Each metric has four sibling implementations under `linux/`, `darwin/`,
`windows/`, selected at build time, with a parallel `*/system_stats_utils.c`
per platform. The header forks the prototype set on `WIN32`: non-Windows gets
`ConvertToBytes`, `read_process_status`, `trimStr`, etc.; Windows gets
`initialize_wmi_connection`, `execute_query`, `is_process_running`
(`system_stats.h:53-76`) `[verified-by-code]`. The Windows entry points need
explicit `PGDLLEXPORT` prototypes guarded by `#ifdef WIN32`
(`system_stats.c:40-55`) `[verified-by-code]`. So "add a metric" means writing
the read four times against four unrelated kernel APIs (/proc text files vs
sysctl vs WMI COM queries) — a maintenance shape core PG avoids by having one
canonical in-process source of truth.

### 3. A backend doing file I/O and libc syscalls in the query path

The SRF body opens, reads, and parses host files inside the executing backend:
`fopen`/`getline`/`fclose` on `/proc/meminfo` (`linux/memory_info.c:34-150`),
`opendir("/proc")` + per-PID `fopen("/proc/<pid>/stat")` + `fscanf` to tally
process states (`linux/system_stats_utils.c:152-204`), and DNS/`getaddrinfo` +
`/etc/resolv.conf` reads for the domain name (`linux/os_info.c:75-177`)
`[verified-by-code]`. This is ordinary blocking libc I/O on a hot SQL path —
not the buffered-file / `OpenTransientFile` discipline core uses; the extension
calls bare `fopen`/`fclose` directly. A slow `/proc` read (e.g. thousands of
PIDs) stalls the backend with no interrupt checking inside the scan loop.
`[inferred]` from the loop in `linux/system_stats_utils.c:160-196` (no
`CHECK_FOR_INTERRUPTS`).

### 4. Bare libc memory management, not palloc/MemoryContext

The OS-read helpers manage their scratch buffers with libc `free`, not
`pfree`/MemoryContext: `getline`'s malloc'd `line_buf` is released with `free`
throughout (`linux/memory_info.c:122-147`, `linux/os_info.c:52-56, 271-287`,
`linux/system_stats_utils.c:240-245`) `[verified-by-code]`. The only palloc-side
allocation is the implicit one when result values become Datums
(`CStringGetTextDatum` in `linux/os_info.c:317-322`) and the tuplestore, which
lives in the per-query context the entry point switched into
(`system_stats.c:116-130`) `[verified-by-code]`. The read layer is essentially
plain C that happens to run inside a backend — it does not participate in PG's
memory-context lifetime model (`[[knowledge/idioms/memory-contexts]]`).

### 5. Security surface: host-level facts exposed through SQL, gated by a custom role

Because the functions leak host information (hostnames, every PID's name and
memory, network interfaces, mounted filesystems), the extension creates a
dedicated `monitor_system_stats` NOLOGIN role and `REVOKE ALL … FROM PUBLIC` /
`GRANT EXECUTE … TO monitor_system_stats` on every function
(`system_stats--4.0.sql:9-22, 41-42`, repeated per function through the tail)
`[verified-by-code]`. "Due to the nature of the information returned by these
functions, access is restricted to superusers and members of the
monitor_system_stats role… The monitor_system_stats role will not be removed
when you run DROP EXTENSION" (`README.md:48-54`) `[from-README]`. This is a
genuinely-correct privilege touch, but it also flags the divergence: a normal PG
function exposes database data scoped by the role's grants; these expose the
*operating system* to whoever holds the role, independent of any catalog ACL.

### 6. `uninstall_system_stats.sql` and a leaked role: object lifecycle outside the extension model

The repo ships a manual `uninstall_system_stats.sql` that bare-`DROP FUNCTION`s
all ten functions (`uninstall_system_stats.sql:1-10`) `[verified-by-code]` —
redundant with `DROP EXTENSION`, a pre-extension-framework habit. And the
`monitor_system_stats` role is deliberately *not* dropped on uninstall
(`README.md:52-54`) `[from-README]`, so a privilege object survives the
extension that created it — outside the clean `CREATE EXTENSION` /
`DROP EXTENSION` ownership graph core expects.

## Notable design decisions with cites

- **Materialize-mode tuplestore is the universal return shape.** All ten SRFs
  are copy-paste variants of one 45-line scaffold: validate `ReturnSetInfo`,
  require `SFRM_Materialize`, build tupdesc, `tuplestore_begin_heap(true, false,
  work_mem)`, delegate to `Read*` (`system_stats.c:92-136` and nine clones).
  No `SRF_FIRSTCALL_INIT`/`SRF_RETURN_NEXT` ValuePerCall path exists. The
  per-row count is asserted against a `Natts_*` macro
  (`Assert(tupdesc->natts == Natts_os_info)`, `system_stats.c:123`)
  `[verified-by-code]`.
- **Column order is pinned by `Anum_*` macros in the header, shared across
  platforms.** Each metric's columns are integer indices
  (`Anum_total_memory 0` … `Anum_avail_page_file 11`, `system_stats.h:137-148`),
  and platform readers index `values[Anum_*]` / `nulls[Anum_*]` directly
  (`linux/memory_info.c:104-117`) `[verified-by-code]`. This is the contract
  that lets four platform bodies fill one tupdesc consistently and NULL the
  columns they can't supply.
- **`ConvertToBytes` parses `/proc/meminfo`'s "N kB" suffix by hand.** It splits
  on `:`, `strtok_r`s the value and unit, and multiplies by 1024/1024²/1024³ for
  kb/mb/gb (`linux/system_stats_utils.c:24-72`) `[verified-by-code]` — a
  string-munging layer that exists only because the data source is a text file,
  not a typed in-process counter.
- **Disk enumeration filters pseudo-filesystems with baked-in regexes.** The
  header carries `IGNORE_MOUNT_POINTS_REGEX` and
  `IGNORE_FILE_SYSTEM_TYPE_REGEX` enumerating `proc|sys|cgroup|overlay|…`
  (`system_stats.h:88-89`) `[verified-by-code]`, encoding kernel-filesystem
  knowledge directly into the extension.
- **The `3.0→4.0` upgrade warns about its own lock.** The upgrade comment notes
  `DROP FUNCTION` "takes an AccessExclusiveLock on the function. Run during a
  maintenance window… Any views or materialized views that depend on the old
  function signature must be dropped before running this upgrade"
  (`system_stats--3.0--4.0.sql:5-9`) `[from-comment]` — an honest call-out that
  changing an SRF's column set is a breaking signature change.

## Links into corpus

- `[[knowledge/ideologies/pgsentinel]]` — observability sibling, but reads PG
  parse state + `pg_stat_activity` via a hook + shmem + SPI; system_stats reads
  the OS and needs none of that machinery.
- `[[knowledge/ideologies/pg_tracing]]` — the other monitoring sibling; traces
  PG executor spans (internal) where system_stats samples the host (external).
- `[[knowledge/idioms/fmgr]]` — the `PG_FUNCTION_INFO_V1` +
  `ReturnSetInfo` + Materialize-mode tuplestore SRF pattern instantiated ten
  times here (no SPI is used — this extension is fmgr-only).
- `[[knowledge/idioms/memory-contexts]]` — the contrast: per-query tuplestore in
  the right context, but bare libc `fopen`/`free` for all the scratch reading.

## Sources

Fetched 2026-06-28 via `raw.githubusercontent.com/EnterpriseDB/system_stats/master`:

- `README.md` @ 2026-06-28 → 200 (first fetch returned a stale/cached
  *pg_permissions* README via CDN; re-fetched with cache-bust query string,
  which returned the correct `System Statistics` README — all `README.md` cites
  above are against the corrected blob)
- `system_stats.control` @ 2026-06-28 → 200
- `system_stats--4.0.sql` @ 2026-06-28 → 200
- `system_stats--3.0--4.0.sql` @ 2026-06-28 → 200
- `system_stats--1.0--2.0.sql`, `system_stats--2.0--3.0.sql` @ 2026-06-28 → 200
  (both no-op upgrade stubs)
- `uninstall_system_stats.sql` @ 2026-06-28 → 200
- `system_stats.c` @ 2026-06-28 → 200
- `system_stats.h` @ 2026-06-28 → 200
- `misc.c`, `misc.h` @ 2026-06-28 → 200
- `linux/memory_info.c` @ 2026-06-28 → 200
- `linux/os_info.c` @ 2026-06-28 → 200
- `linux/cpu_info.c` @ 2026-06-28 → 200
- `linux/system_stats_utils.c` @ 2026-06-28 → 200

Manifest gaps: the `darwin/` and `windows/` per-platform readers were enumerated
from the tree but not fetched in full; the divergence claims about macOS/Windows
(WMI, sysctl) rest on the header's `#ifdef WIN32` prototype fork
(`system_stats.h:53-76`), the `_PG_init` WMI init (`system_stats.c:72-74`), and
the README's platform notes (`README.md:2-7, 104-108`) rather than on those
bodies' line-level code. Other Linux readers (`disk_info.c`, `network_info.c`,
`cpu_usage_info.c`, `io_analysis.c`, `load_avg.c`, `process_info.c`,
`cpu_memory_by_process.c`) were enumerated but only sampled via the header
macros; their `/proc` paths are cited from `system_stats.h` not their bodies.
