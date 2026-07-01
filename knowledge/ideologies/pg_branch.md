# pg_branch — `CREATE DATABASE ... WITH TEMPLATE` rewired to a btrfs copy-on-write subvolume snapshot, so a whole DB clones in seconds without copying a single tuple

> Ideology note produced by the `pg-extension-anthropologist` cloud routine.
> Repo: `NAlexPear/pg_branch` @ branch `main`. All `file:line` cites below point
> into that repo (not `source/`), since this doc characterizes an *external*
> extension's divergence from core idioms. Cites verified against the files
> fetched on 2026-06-30 (see Sources footer). **EXPERIMENTAL**: the README
> self-labels this "pre-alpha software, meant as an experimental
> proof-of-concept" (`README.md:18-19`) `[from-README]`. Tiny codebase (~340
> lines of Rust across 5 files). Where claims go beyond the code they are
> tagged `[inferred]`.

## Domain & purpose

pg_branch is "a Postgres extension for quickly creating 'branches' of
individual databases within a Postgres cluster using copy-on-write file
systems like BTRFS" (`README.md:7`) `[from-README]`. Its target is the
well-known pain that `CREATE DATABASE name WITH TEMPLATE template` (a) refuses
to run while there is any active connection to `template`, and (b) degrades
toward linear-in-DB-size copy time (`README.md:21-28`) `[from-README]`. The
extension's pitch: if `PGDATA` lives on a copy-on-write filesystem, every
`CREATE DATABASE ... TEMPLATE` becomes "an atomic file system snapshot that
takes seconds instead of minutes (or hours)" and "only writing new segment
data files to disk when they're modified" (`README.md:28`) `[from-README]`. The
load-bearing trick: it does not copy rows, pages, or files. It asks the
**filesystem** to clone the template database's per-database data subdirectory
(`$PGDATA/base/<oid>`) as a btrfs subvolume snapshot, then forges a matching
`pg_database` catalog row pointing the new OID at the cloned directory.

## How it hooks into PG

Built on **pgrx** (`Cargo.toml:42` pins `pgrx = "=0.10.2"`,
`crate-type = ["cdylib"]` at `:19-20`) `[verified-by-code]`. The control file is
`relocatable = false`, `superuser = true` (`pg_branch.control:4-5`)
`[verified-by-code]` — installation is superuser-gated.

- **`_PG_init` → `hooks::init()`** (`src/lib.rs:70-72`) which calls
  `pgrx::register_hook(&mut HOOKS)` (`src/hooks.rs:98-99`) `[verified-by-code]`.
- **The single hook installed is `process_utility_hook`**
  (`src/hooks.rs:5-7`) `[verified-by-code]` — the pgrx-wrapped
  `ProcessUtility_hook`. It tests `is_a(pstmt.utilityStmt,
  NodeTag_T_CreatedbStmt)` (`src/hooks.rs:30`) and intercepts only
  `CREATE DATABASE`; every other utility statement is forwarded untouched to
  `prev_hook` (`src/hooks.rs:80-91`) `[verified-by-code]`.
- **SQL surface:** one `#[pg_extern]` function, `branch(target, template)`
  (`src/lib.rs:14-15`) `[verified-by-code]`, callable directly from SQL; the
  utility hook routes intercepted `CREATE DATABASE` into the same
  `crate::branch(...)` (`src/hooks.rs:78`).

There is **no `shared_preload_libraries` requirement enforced in code** — unlike
orioledb/citus, `_PG_init` does not check
`process_shared_preload_libraries_in_progress`. But because the hook must be
registered at backend startup to intercept `CREATE DATABASE`, in practice the
library must be preloaded (or the extension's `_PG_init` run via
`shared_preload_libraries`) for the interception to fire on ordinary sessions
`[inferred]`. The README's getting-started path uses `cargo pgrx run`
(`README.md:88-94`) and does not spell out the preload line — a gap consistent
with proof-of-concept status `[inferred]`.

Statement-strategy escape hatch: if `CREATE DATABASE` carries an explicit
`STRATEGY` option whose value is anything other than `snapshot`, the hook
forwards to `prev_hook` and the snapshot path is skipped (`src/hooks.rs:57-70`)
`[verified-by-code]` — so `STRATEGY wal_copy` / `file_copy` reverts to core
behavior (`README.md:100`) `[from-README]`.

## Where it diverges from core idioms

### 1. The whole feature reaches *outside* PostgreSQL into the OS filesystem — it FFI-calls libbtrfsutil to snapshot a subvolume, rather than copying tuples or pages

This is the divergence the extension exists for. Core's `CREATE DATABASE`
copies the template's data at the *storage* layer it controls: `FILE_COPY`
copies relation segment files via smgr with a checkpoint, `WAL_COPY`
(`STRATEGY wal_copy`, the modern default) reads each block through the buffer
manager and WAL-logs it. pg_branch instead calls
`btrfsutil_sys::btrfs_util_create_snapshot(source_path, destination_path, 0,
NULL, NULL)` (`src/fs/btrfs.rs:22-28`) `[verified-by-code]` — a direct FFI into
the C `libbtrfsutil` library (`Cargo.toml:41` depends on `btrfsutil-sys
= "1.3.0"`). The source is the template's `$PGDATA/base/<template_oid>`
directory (`src/database.rs:66-75`, `src/lib.rs:39`), the destination is
`$PGDATA/base/<new_oid>` (`src/lib.rs:44-50`) `[verified-by-code]`. Postgres
never reads or writes the bytes; the kernel's btrfs COW machinery shares
extents between the two subvolumes until one side writes. The
storage-substrate seam core *owns* (smgr / segment files / buffer manager,
`[[knowledge/subsystems/storage-buffer]]`) is bypassed entirely for the copy.

A `Branching` trait (`src/fs/mod.rs:9-12`) abstracts "atomic snapshot" so other
COW filesystems (ZFS/XFS, future work `README.md:108`) could implement it;
btrfs is the only impl today (`src/fs/btrfs.rs:13`) `[verified-by-code]`.

### 2. It synthesizes a `pg_database` catalog row by hand with `CatalogTupleInsert`, instead of going through `createdb()` / `dbcommands.c`

Core never lets a backend hand-forge a `pg_database` tuple; `createdb()` builds
the row, copies files, and updates shared invalidation state in one coherent
path. pg_branch instead:

1. checks for a name clash with an SPI `select oid from pg_database`
   (`src/lib.rs:19-35`) `[verified-by-code]`;
2. allocates an OID via `pg_sys::GetNewObjectId()` (`src/lib.rs:42`)
   `[verified-by-code]` — note: a raw cluster-wide OID, **not**
   `GetNewRelFileNumber`/db-OID-specific allocation, and not collision-checked
   against `pg_database` beyond the name `[inferred]`;
3. opens `pg_database` with
   `PgRelation::open_with_name_and_share_lock("pg_database")` — a **ShareLock**,
   not the RowExclusiveLock core's catalog inserts take (`src/lib.rs:59`)
   `[verified-by-code]`;
4. builds a 16-column `Record` in hard-coded column order and calls
   `pg_sys::CatalogTupleInsert(pg_database.as_ptr(), tuple.into_pg())`
   (`src/database.rs:79-102`, `src/lib.rs:61-65`) `[verified-by-code]`.

The 16 datums at `src/database.rs:84-101` are positional and partly
**constants**: `encoding = 6` (UTF8), `datlocprovider = 'c'`,
`datistemplate = false`, `datallowconn = true`, `datconnlimit = -1`,
`datfrozenxid = 716`, `datminmxid = 1`, collate/ctype `"C.UTF-8"`, and three
trailing `None`s (`src/database.rs:88-100`) `[verified-by-code]`. The
`datdba`/`dattablespace` are copied from the template via
`Spi::get_three_with_args` over `pg_database` (`src/database.rs:50-63`)
`[verified-by-code]`. Risks this raises vs core:
- **No `pg_shdepend` / ACL / `pg_db_role_setting` rows** are created
  `[inferred]` — core's `createdb` records shared dependencies; this path
  inserts only the `pg_database` tuple.
- **`datfrozenxid = 716` is a literal**, not the template's actual frozen xid
  or the current cluster horizon (`src/database.rs:92`) `[verified-by-code]`.
  Because the on-disk clog/relfrozenxid state is the template's (it came along
  in the snapshot), a hard-coded frozenxid that disagrees with the cloned data
  is a correctness hazard for vacuum/wraparound accounting `[inferred]`.
- **No `CountOtherDBBackends` / connection check** on the template
  `[inferred]`. The README sells exactly this — branching "without requiring an
  exclusive lock or dedicated connection" (`README.md:100`) `[from-README]` —
  but it means the snapshot can be taken while the template has live writers.

### 3. Snapshot coherence of a *running* cluster's buffers and WAL is not addressed in code

Core's `FILE_COPY` forces a checkpoint so the template's on-disk files are
consistent before copy; `WAL_COPY` reads through shared buffers so it sees
committed state. pg_branch's snapshot is a pure filesystem-level clone of
`base/<oid>` (`src/fs/btrfs.rs`, `src/lib.rs:50`) with **no checkpoint, no
buffer flush, no `RequestCheckpoint`, and no fsync barrier in the code**
`[verified-by-code]` (absence). Consequences, all `[inferred]` because the code
simply omits the step:
- Dirty pages for the template still sitting in shared buffers are **not** in
  the snapshot; the clone captures only what btrfs sees on disk at snapshot
  time.
- WAL is cluster-global and lives in `$PGDATA/pg_wal`, *outside* the
  per-database `base/<oid>` subvolume that gets snapshotted — so the branch
  shares the parent's WAL stream and has no independent recovery boundary.
- A crash between `btrfs_util_create_snapshot` and `CatalogTupleInsert` (two
  non-atomic steps spanning the FS and the catalog) leaves an orphan subvolume
  or a catalog row with no/garbage data dir `[inferred]`.

The init step that makes snapshots possible — converting each
`$PGDATA/base/<oid>` into its own btrfs subvolume — is done **out-of-band by a
shell script** before the cluster is trusted to pg_branch: `init.sh` walks
`$PGDATA/base`, and for each segment dir does `mv dir dir_old; btrfs subvolume
create dir; cp dir_old/* dir/; rm -rf dir_old` (`init.sh:26-32`)
`[verified-by-code]`. So the per-database directory boundary that core treats
as an implementation detail is, here, promoted to a filesystem subvolume
boundary as a manual setup precondition.

### 4. PGDATA, not tablespace — and one snapshot granularity (one database)

The clone unit is exactly `$PGDATA/base/<oid>` resolved from the
`data_directory` GUC via SPI (`src/database.rs:66-75`) `[verified-by-code]`.
That means:
- Databases stored in a **non-default tablespace** (whose files live under
  `pg_tblspc/.../<db_oid>`, not `base/<oid>`) are **not** handled by this path
  `[inferred]` — `data()` always joins `base`. The catalog row still copies the
  template's `dattablespace` (`src/database.rs:60`, `src/lib.rs:56`), so a
  template in a custom tablespace would get a catalog row pointing at a
  tablespace whose files were never snapshotted `[inferred]`.
- It is per-database, not cluster-wide; a cluster-wide `fork` is explicit
  future work (`README.md:105`) `[from-README]`.

### 5. Locking model is lighter than core's catalog-mutation discipline

The only lock taken is the `ShareLock` on `pg_database`
(`src/lib.rs:59`) `[verified-by-code]`. There is no `LockSharedObject` on the
new database OID, no advisory lock against concurrent `branch()` of the same
target beyond the initial name SELECT (a TOCTOU window between the existence
check at `src/lib.rs:19-35` and the insert at `:64`) `[inferred]`, and no
exclusive lock against the template (by design — that's the selling point).

## Notable design decisions (cited)

- **One hook, narrowly scoped** — only `process_utility_hook`, only
  `T_CreatedbStmt`, everything else forwarded (`src/hooks.rs:5-7,30,80-91`)
  `[verified-by-code]`. Minimal blast radius; no planner/executor involvement.
- **Opt-out via `STRATEGY`** — `strategy` ≠ `snapshot` (case-insensitive)
  forwards to the previous hook, so users can still get core `WAL_COPY` /
  `FILE_COPY` per-statement (`src/hooks.rs:57-70`, `README.md:100`)
  `[verified-by-code]`.
- **SQL-callable `branch()` independent of the hook** (`src/lib.rs:14-15`)
  `[verified-by-code]` — the snapshot logic is reachable directly, the utility
  hook is just sugar over it.
- **Template defaults to `template1`** when none given (`src/lib.rs:16`)
  `[verified-by-code]`.
- **`superuser = true`, `relocatable = false`** (`pg_branch.control:4-5`)
  `[verified-by-code]` — gated to superusers; a `// FIXME: check CREATEDB
  privilege of the user` (`src/hooks.rs:29`) admits the per-user privilege
  check is not implemented `[verified-by-code]`.
- **Hard-coded catalog datums** including `datfrozenxid = 716`,
  `encoding = 6`, `"C.UTF-8"` collate/ctype (`src/database.rs:88-97`)
  `[verified-by-code]` — a proof-of-concept shortcut, not derived from the
  template's real catalog row.
- **`panic!`-based error model on the FS side** — `create_snapshot` panics if
  `btrfs_util_create_snapshot` returns `> 0` (`src/fs/btrfs.rs:31-33`); the
  Rust panic unwinds (`Cargo.toml:48,51` set `panic = "unwind"`) and pgrx's
  `#[pg_guard]` converts it to a Postgres `ERROR` `[verified-by-code]` /
  `[inferred]` (the guard-to-ereport bridge is pgrx's, see
  `[[knowledge/ideologies/pgrx]]`).
- **pgrx `=0.10.2` exact pin, PG 11–16 feature-gated, default `pg15`**
  (`Cargo.toml:23-29,42`) `[verified-by-code]` — uses pgrx's `pg_sys`
  bindings (`CatalogTupleInsert`, `GetNewObjectId`, `pgrx_list_nth`,
  `PgHeapTuple`) rather than a patched server; it is a true in-seam extension,
  not a fork (contrast orioledb).

## Links into corpus

- `[[knowledge/ideologies/pgrx]]` — the framework pg_branch is built on
  (`Cargo.toml:42`); the `#[pg_extern]`, `PgHooks`, `PgBox`, `PgHeapTuple`,
  `Spi`, and `#[pg_guard]` panic→ereport machinery all come from there.
- `[[knowledge/idioms/process-utility-hook-chain]]` — the
  `ProcessUtility_hook` chaining contract pg_branch's `process_utility_hook`
  participates in (forward-to-`prev_hook` discipline at `src/hooks.rs:80-91`).
- `[[knowledge/idioms/catalog-conventions]]` — the `pg_database` row pg_branch
  hand-forges with `CatalogTupleInsert` (`src/lib.rs:61-65`,
  `src/database.rs:84-101`), bypassing `createdb()`/`dbcommands.c`.
- `[[knowledge/idioms/spi]]` — the SPI queries against `pg_database` /
  `pg_settings` used to resolve OIDs, dba, tablespace, and the data directory
  (`src/lib.rs:19-31`, `src/database.rs:50-75`).
- `[[knowledge/subsystems/storage-buffer]]` — the smgr / segment-file /
  buffer-manager copy path pg_branch *replaces* with a kernel-level btrfs
  subvolume snapshot; also why no-checkpoint snapshot coherence is a hazard.
- `[[knowledge/ideologies/pg_repack]]`, `[[knowledge/ideologies/pg_squeeze]]` —
  fellow "manipulate physical storage outside the normal write path" cousins,
  though those stay inside PG's smgr/relfilenode model; pg_branch goes one
  layer deeper, into the OS filesystem.
- `.claude/skills/extension-development/SKILL.md` and the
  `bgworker-and-extensions` skill — `_PG_init` + hook-registration entry point.

## Anthropology takeaway (for STATE.md / cross-corpus)

pg_branch is the corpus's clearest case of an extension that **delegates the
hard part to the kernel**. Most "diverge from core" ideologies replace a PG
subsystem with their own C (orioledb's storage engine, citus's distributed
executor). pg_branch writes almost no storage code at all: it intercepts one
utility statement, FFI-calls `btrfs_util_create_snapshot`, and forges a catalog
row. The divergence is *architectural placement* — it treats Postgres' on-disk
`base/<oid>` directory as a btrfs subvolume and lets copy-on-write at the
filesystem do what core does with smgr + WAL. The price, honestly visible in
~340 lines, is every invariant core's `createdb()` upholds that this path skips:
checkpoint-before-snapshot, buffer-flush coherence, `pg_shdepend`, a real
`datfrozenxid`, tablespace handling, OID-collision and connection checks. It is
a sharp illustration of *which* of `CREATE DATABASE`'s responsibilities are
about correctness vs. which are about the copy — and a ready reference for any
"could core offer a `STRATEGY snapshot` that calls into a pluggable COW
backend?" discussion.

## Sources

Fetched 2026-06-30 (branch `main`):

- `https://api.github.com/repos/NAlexPear/pg_branch/git/trees/main?recursive=1`
  @ 2026-06-30 → HTTP 200 (tree listing; confirms the 5-file `src/` layout).
- `https://raw.githubusercontent.com/NAlexPear/pg_branch/main/README.md`
  @ 2026-06-30 → HTTP 200 (5967 bytes, 114 lines).
- `https://raw.githubusercontent.com/NAlexPear/pg_branch/main/pg_branch.control`
  @ 2026-06-30 → HTTP 200 (151 bytes, 5 lines).
- `https://raw.githubusercontent.com/NAlexPear/pg_branch/main/Cargo.toml`
  @ 2026-06-30 → HTTP 200 (1121 bytes, 54 lines; pgrx `=0.10.2`,
  `btrfsutil-sys 1.3.0`).
- `https://raw.githubusercontent.com/NAlexPear/pg_branch/main/init.sh`
  @ 2026-06-30 → HTTP 200 (873 bytes, 34 lines; subvolume conversion).
- `https://raw.githubusercontent.com/NAlexPear/pg_branch/main/src/lib.rs`
  @ 2026-06-30 → HTTP 200 (2795 bytes, 91 lines; `branch()`, `_PG_init`).
- `https://raw.githubusercontent.com/NAlexPear/pg_branch/main/src/hooks.rs`
  @ 2026-06-30 → HTTP 200 (4107 bytes, 100 lines; `process_utility_hook`).
- `https://raw.githubusercontent.com/NAlexPear/pg_branch/main/src/database.rs`
  @ 2026-06-30 → HTTP 200 (3401 bytes, 103 lines; `Database`, `as_record`).
- `https://raw.githubusercontent.com/NAlexPear/pg_branch/main/src/fs/mod.rs`
  @ 2026-06-30 → HTTP 200 (524 bytes, 13 lines; `Branching` trait).
- `https://raw.githubusercontent.com/NAlexPear/pg_branch/main/src/fs/btrfs.rs`
  @ 2026-06-30 → HTTP 200 (1080 bytes, 35 lines; `btrfs_util_create_snapshot`).

Code cites are `[verified-by-code]` against the fetched Rust/control/shell
sources (hook install, snapshot FFI, catalog insert, hard-coded datums, locking,
strategy opt-out). The performance/UX narrative (seconds-not-hours, low disk via
COW, no exclusive lock) is `[from-README]`. Claims about *omitted* behavior
(no checkpoint, no `pg_shdepend`, tablespace gap, OID-collision/TOCTOU windows,
WAL sharing) are `[inferred]` from the absence of the corresponding code in a
deliberately small proof-of-concept and should be treated as hypotheses, not
verified failures.
