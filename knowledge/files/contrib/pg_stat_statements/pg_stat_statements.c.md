# pg_stat_statements.c

**Source pin:** `4b0bf0788b0` · **Path:** `source/contrib/pg_stat_statements/pg_stat_statements.c` (2913 LOC)

## One-line summary

THE query-telemetry extension touched by virtually every PG installation:
intercepts planner + executor + ProcessUtility hooks to record per-(userid,
dbid, queryid, toplevel) call counts, planning/execution time, buffer / WAL /
JIT / parallel-worker usage, and a normalized query text (constants replaced
with `$n`), all in a fixed-size shared-memory hash plus a side-car query-text
file in `pg_stat_tmp/`.

## Public API / entry points

Hooks installed in `_PG_init` (loaded only via `shared_preload_libraries`,
gracefully no-ops otherwise) `[verified-by-code]`:

- `pgss_post_parse_analyze` — installs into `post_parse_analyze_hook`
  (`source/contrib/pg_stat_statements/pg_stat_statements.c:480-481`). Creates a
  sticky placeholder entry the moment jumbling sees ≥1 ignorable constant, so
  the *normalized* form is captured even if the query subsequently errors out
  (`:865-879`).
- `pgss_planner` — `planner_hook` (`:482-483`). Times planning when
  `pg_stat_statements.track_planning = on`; otherwise just bumps nesting depth
  to keep "top-level" labelling honest (`:886-988`).
- `pgss_ExecutorStart` / `pgss_ExecutorRun` / `pgss_ExecutorFinish` /
  `pgss_ExecutorEnd` — `:484-491`. ExecutorStart sets `INSTRUMENT_ALL` on the
  queryDesc only when this query will be tracked (`:1001-1011`); ExecutorEnd is
  where `PGSS_EXEC` accounting actually lands (`:1058-1086`).
- `pgss_ProcessUtility` — `:492-493`. Forces `pstmt->queryId = 0` on the way
  in so the inner planner/executor hooks don't double-count, and records the
  utility statement as a single PGSS_EXEC sample (`:1091-1255`). Note the
  cautious comment at `:1170-1178` about not touching `pstmt` after
  ProcessUtility returns (ROLLBACK may have freed it).

SQL-callable functions, all `PG_FUNCTION_INFO_V1`:

- `pg_stat_statements_reset()` v1.0 — `:324, :1543` — wipes everything.
- `pg_stat_statements_reset(oid, oid, bigint)` v1.7 — `:325, :1508`.
- `pg_stat_statements_reset(oid, oid, bigint, bool)` v1.11 — `:326, :1524`
  (last arg = `minmax_only`).
- `pg_stat_statements_1_2 / _1_3 / _1_8 / _1_9 / _1_10 / _1_11 / _1_12 /
  _1_13` — `:327-334`, all funnel through `pg_stat_statements_internal`
  (`:1668`).
- `pg_stat_statements()` — legacy 1.0/1.1 entry (`:335, :1657`).
- `pg_stat_statements_info()` — exposes the global `dealloc` counter and
  `stats_reset` timestamp (`:336, :2037`).

GUCs (`_PG_init` `:412-468`):

| GUC | Type | Default | Context |
|---|---|---|---|
| `pg_stat_statements.max` | int | 5000 (cap `INT_MAX/2`) | `PGC_POSTMASTER` |
| `pg_stat_statements.track` | enum `none`/`top`/`all` | `top` | `PGC_SUSET` |
| `pg_stat_statements.track_utility` | bool | **true** | `PGC_SUSET` |
| `pg_stat_statements.track_planning` | bool | false | `PGC_SUSET` |
| `pg_stat_statements.save` | bool | true | `PGC_SIGHUP` |

Also calls `EnableQueryId()` (`:407`) so `compute_query_id = auto` lights up
when this module is preloaded.

## Key invariants

`[from-comment, :22-34]`:

1. To **create / delete** a hash entry or to modify any field other than
   counters, hold `pgss->lock` **exclusive**.
2. To **look up** an entry, hold `pgss->lock` **shared**.
3. To **read or update counters** inside an entry, hold `pgss->lock`
   shared-or-exclusive (so the entry can't vanish) **and** the per-entry
   `mutex` spinlock. (`:1393-1493` is the canonical bump-counters sequence.)
4. `pgss->extent` (next free byte in the text file) is protected by either
   `pgss->mutex` spinlock or exclusive `pgss->lock`. This split exists
   precisely so `qtext_store` can reserve file space while holding only
   shared lock on `pgss->lock` (`:2237-2247`).
5. **Rewriting the entire query-text file** (i.e. `gc_qtexts`) requires
   exclusive `pgss->lock`; individual entries may be read/written under shared
   lock because their byte ranges are reserved and stable.
6. **Parallel workers never store** anything (`pgss_enabled` short-circuits on
   `IsParallelWorker()`, `:310-313`) — only the leader records.
7. Hash key is `(userid, dbid, queryid, toplevel)` with explicit padding zero
   (`memset(&key, 0, ...)` at `:1308-1314`) — `HASH_BLOBS` uses `tag_hash` so
   any uninitialised padding byte would scatter identical logical keys across
   buckets `[from-comment, :139-142]`.
8. `entry->stats_since` / `minmax_stats_since` are read **without** the
   spinlock (`:1888-1893`) — safe only because they're written **only** under
   exclusive lock `[from-comment]`.
9. `qtext_fetch` self-validates: bogus offset, negative length, or missing
   trailing NUL all return NULL (`:2410-2418`). This is the GC-race safety net.
10. `query_offset = 0, query_len = -1` is the **"text invalidated"** marker
    used after a failed `gc_qtexts` (`:2618-2621, :230-232`).

## Notable internals

### Hash sizing & eviction

`pgss_max` (default 5000) is the hard ceiling. `entry_alloc` enforces it via
a `while (hash_get_num_entries >= pgss_max) entry_dealloc();` loop
(`:2088-2090`). `entry_dealloc` sorts all entries by `counters.usage`,
multiplies every entry's usage by `USAGE_DECREASE_FACTOR = 0.99` (or
`STICKY_DECREASE_FACTOR = 0.50` for sticky placeholders), then deletes the
bottom `USAGE_DEALLOC_PERCENT = 5%` (min 10) and bumps
`pgss->stats.dealloc++` (`:2139-2212`). The visible
`pg_stat_statements_info.dealloc` counter is **monotonic** within a stats
reset window — exposing it to non-superusers is the audit-leak surface
discussed below.

### Query-text "garbage collection"

`gc_qtexts` runs **only** when `need_gc_qtexts` says the file is BOTH
larger than `512 × pgss_max` AND larger than `mean_query_len × pgss_max × 2`
(`:2437-2456`). Under exclusive lock, it `palloc`s the entire file into
memory, rewrites it in place (relying on the new file being ≤ the old one
for safety on traditional FS — explicitly noted as broken on CoW filesystems
at `:2506-2509`), `ftruncate`s, and bumps `pgss->gc_count`. **On any
failure** (`gc_fail:` `:2605-2654`) it walks the hash table and sets every
entry's `query_offset = 0, query_len = -1` (i.e. blanks all query texts),
unlinks `PGSS_TEXT_FILE`, creates a fresh empty one, and resets
`pgss->extent = 0`. So a single GC OOM/IO failure makes EVERY query text
disappear cluster-wide until each query is rerun and re-jumbled.

### `pg_stat_tmp/pgss_query_texts.stat` torn-write window

`qtext_store` writes directly via `pg_pwrite` to a byte-offset reserved
under spinlock (`:2241-2272`). Concurrent writers from multiple backends
overlay distinct regions, but `qtext_load_file` (`:2310-2395`) reads the
whole file in 1 GiB chunks via plain `read()` with no locking — if a `read`
returns short and `errno == 0`, it assumes "GC truncated the file under us"
and returns NULL without complaint (`:2366-2384`). This is the only sanity
check: there's no per-text checksum.

### Post-crash file format

On clean shutdown (`pgss_shmem_shutdown` `:733-828`) the hash table is
serialized to `PGSTAT_STAT_PERMANENT_DIRECTORY/pg_stat_statements.stat`
(header magic `0x20250731`, then per-entry struct + raw query text + final
`pgssGlobalStats`). On startup (`pgss_shmem_init` `:529-725`) it `unlink()`s
the live text file unconditionally (`:579`) — surviving a crash means
**all query texts are gone**, only counters survive. Sticky entries are
skipped on reload (`:648-650`). The dump file is then unlinked (`:690`) so
it doesn't end up in `pg_basebackup`.

### `compute_query_id` interaction

`pgss_store` early-exits if `queryId == 0` (`:1296-1297`), so the module
silently records **nothing** when `compute_query_id = off` AND no other
extension computes queryIds. `_PG_init` calls `EnableQueryId()` to flip
`auto` to `on`, but an explicit `compute_query_id = off` in
`postgresql.conf` will silently disable pg_stat_statements
[ISSUE-documentation: silent no-op when compute_query_id=off (nit)].

### Hash collision behaviour

Normalization replaces literal constants with `$1, $2, ...`
(`generate_normalized_query` `:2812-2913`). Two semantically distinct
queries that differ only in a constant **share** the entry. The query text
shown back is whichever one happened to create the entry first — a security
nuance: an attacker can shape the displayed text by being the first to run
the canonical form.

## Trust boundary / Phase D surface

### Who sees what query text?

`pg_stat_statements_internal` (`:1666-2028`) gates query-text and queryid
visibility by:

```c
is_allowed_role = has_privs_of_role(userid, ROLE_PG_READ_ALL_STATS);
```

(`:1686`). If the caller is NOT the entry's owner AND NOT a member of
`pg_read_all_stats`, the queryid is NULL and the query text becomes the
literal string `"<insufficient privilege>"` (`:1867-1881`). So
**non-superusers can see other users' query texts** only via
`pg_read_all_stats` membership — which is the documented contract.

`GRANT SELECT ON pg_stat_statements TO PUBLIC`
(`pg_stat_statements--1.10--1.11.sql:70`) — every login user can read the
view, but per the above they only see their own queries' texts unless they
also have `pg_read_all_stats`.

### `track_utility = on` is the leak vector (the A4 psql-history cycle)

DEFAULT is **true** (`:305, :441`). Once a non-superuser session executes
`CREATE USER ... PASSWORD 'p'`, `ALTER ROLE ... PASSWORD 'p'`, or any DDL
containing a secret string literal:

1. ProcessUtility is hit (`:1091`).
2. `pgss_track_utility && pgss_enabled` is true, so `pgss_store` is called
   with `queryString` **raw** as `query` (`:1202`).
3. `CleanQuerytext` (`:1304`) just trims whitespace — it does NOT redact
   passwords.
4. There is no JumbleState for utility statements
   (`jstate == NULL` path at `:1336`), so normalization is **NOT** applied:
   the raw DDL string lands in `pgss_query_texts.stat` verbatim.
5. The entry's `userid` is `GetUserId()` — i.e. the ALTER ROLE invoker.
   Any member of `pg_read_all_stats` (the role itself can also see its own
   text) can now read the cleartext password through the view.

This is exactly the A4 psql-history exposure pattern: a `~/.psql_history`
file leaks `\password`-substituted DDL; here, the cluster-wide stats view
leaks the same DDL to anyone with read-all-stats
[ISSUE-security: track_utility=on captures CREATE/ALTER ROLE ...PASSWORD
verbatim in shared-readable view (likely)].

Mitigations the user has: set `pg_stat_statements.track_utility = off`
(needs `PGC_SUSET`), use `\password` from psql (which sends a pre-hashed
SCRAM verifier, never the cleartext), or revoke `pg_read_all_stats`
membership.

### Literals in INSERT / UPDATE / MERGE

These are jumbled by `nodes/queryjumble.c` and normalized: each constant
becomes `$N` in the stored text (`:2812-2911`). So `INSERT INTO secrets
VALUES ('hunter2')` is recorded as `INSERT INTO secrets VALUES ($1)` —
NOT a leak path. BUT: the **post_parse_analyze hook** creates a sticky
entry with the normalized text early (`:865-879`); if the *parser* fails
before analyze (e.g. a literal in a malformed statement that aborts in
scan.l), no entry is created, but if analyze succeeds and execution fails
later, the entry still exists with NORMALIZED text. So literals in DML are
genuinely scrubbed.

### Buffer / palloc-size attack via super-long queries

`qtext_store` checks `query_len >= MaxAllocHugeSize - off` and sets
`errno = EFBIG` (`:2256-2261`) — bounded. `qtext_load_file` uses
`palloc_extended` with `MCXT_ALLOC_HUGE | MCXT_ALLOC_NO_OOM`, gracefully
returning NULL on failure (`:2341-2354`). A single backend can't OOM the
process trying to read the file. However, a malicious user with the
ability to submit a query of length ≈ 1 GiB can wedge the file growth and
force a `gc_qtexts` storm; this would be visible as elevated
`pg_stat_statements_info.dealloc` and elevated gc cost
[ISSUE-defense-in-depth: no per-query length cap; one 1GB query string
takes 1GB in pgss_query_texts.stat (maybe)].

### The `pg_stat_tmp/pgss_query_texts.stat` filesystem-level exposure

The query-text file lives at `PG_STAT_TMP_DIR "/pgss_query_texts.stat"`
(`:85`). On a default deployment with the postmaster running as `postgres`,
file perms come from `OpenTransientFile(O_RDWR | O_CREAT | PG_BINARY)`
(`:2264`) — i.e. `0600` from umask. **Cross-corpus A7 finding** (genfile.c):
`pg_read_server_files` role members can call `pg_read_binary_file()` on
any path the postmaster process can read. So a non-superuser DB user
**cannot** read this file via `\copy` or `lo_import`, but a member of
`pg_read_server_files` CAN dump the entire text file and recover all query
texts, INCLUDING the `track_utility=on` cleartext passwords, INCLUDING
texts the role-acl filter at `:1867-1881` would have replaced with
`<insufficient privilege>`. This is the classic "view filter is not a
filesystem filter" cycle
[ISSUE-security: pg_stat_tmp/pgss_query_texts.stat readable by
pg_read_server_files bypasses view's role-acl filter (likely)].

### `pg_stat_statements_reset` ACLs

`pg_stat_statements--1.6--1.7.sql:22`: `REVOKE ALL ON FUNCTION
pg_stat_statements_reset(oid,oid,bigint) FROM PUBLIC;`
`pg_stat_statements--1.10--1.11.sql:82` similarly. The C body
(`entry_reset`, `:2678`) does NOT recheck privileges — it relies on the
SQL-level GRANT/REVOKE. The 1.4→1.5 migration once granted reset to
`pg_read_all_stats` (`pg_stat_statements--1.4--1.5.sql:6`) but the 1.5→1.6
migration revoked it again (`pg_stat_statements--1.5--1.6.sql:7`). Net
effect today: **only superuser by default** (modulo per-DB GRANTs)
[ISSUE-audit-gap: entry_reset has no internal ACL check, relies entirely
on SQL GRANT/REVOKE; a custom GRANT could open it widely (nit)].

### `track_planning = on` info-leak surface

When on, every planner invocation records BufferUsage + WalUsage diffs
across the planner alone (`:911-961`). Planner buffer reads can implicitly
reveal whether catalog pages were hot vs cold for the invoking role —
i.e. a timing oracle on whether other sessions have recently planned
similar queries. Subtle, but real. Default-off is the correct posture.

### Garbage-collection vs `pgss_store` race

Documented at `:1361-1369`: between the shared-lock `qtext_store` and the
exclusive-lock `entry_alloc`, a different backend may have run `gc_qtexts`
and truncated our just-written text. The check is `pgss->gc_count !=
gc_count`, in which case we re-store the text under exclusive lock. The
hazard window is between line `:1357` (release shared) and `:1358` (acquire
exclusive). If `qtext_store` itself fails the second time, the entry is
not created (`:1371-1373`). Looks correct, but the gc bumps gc_count BOTH
on success AND on failure (`:2601, :2653`) — the failure path is needed so
readers re-stat the file
[ISSUE-correctness: gc_count++ on gc_fail leaves entries with invalid
text_len=-1 and concurrent writers will see fresh gc_count, force re-store
which then races against a possibly-still-broken file; behavior is sound
but the invariant is subtle (nit)].

### `pg_stat_statements_info.dealloc` workload info-leak

The view has `GRANT SELECT ... TO PUBLIC` (`pg_stat_statements--1.12--1.13.sql:78`).
`dealloc` (`:2210`) increments every time the hash hits `pgss_max` and
evicts 5%. From a non-superuser, watching `dealloc` over time is a coarse
oracle on whether **other** users are running enough distinct queries to
churn the cache. Probably not a high-severity disclosure but it IS
cross-user information
[ISSUE-audit-gap: pg_stat_statements_info.dealloc visible to PUBLIC leaks
coarse cross-user workload signal (nit)].

## Cross-references

- **A7 utils/genfile.c** — `pg_read_server_files` role and `pg_read_binary_file`
  bypass for `pg_stat_tmp/pgss_query_texts.stat`.
- **A4 psql/command.c history** — same data-leak cycle: a "session-local"
  store inadvertently captures `CREATE USER … PASSWORD '…'` cleartext.
- `source/src/backend/nodes/queryjumble.c` — companion jumble + normalization
  logic; defines `JumbleState`, `LocationLen`, `CleanQuerytext`,
  `ComputeConstantLengths`, and is the *only* path through which DML
  literals get redacted.
- `source/src/backend/executor/instrument.c` — `BufferUsage` / `WalUsage` /
  `INSTRUMENT_ALL` plumbing relied on at `:1003-1005` and `:1071-1075`.
- `source/src/backend/storage/lmgr/lwlock.c` — `LWLockNewTrancheId`,
  `LWLockInitialize` used at `:551-552`.
- `source/src/backend/storage/file/fd.c` — `OpenTransientFile`,
  `CloseTransientFile`, `AllocateFile` (used throughout reading/writing
  the .stat files).
- `contrib/pg_stat_statements/pg_stat_statements.h` / `pgss_jumble.c` —
  jumbling lives there in newer split (cross-reference only — outside this
  slice).
- sibling contrib: `auto_explain`, `pg_buffercache`, `pg_visibility`,
  `pgstattuple` — all install hooks with similar lifetime patterns; none
  except pg_stat_statements stores per-statement text durably.

## Issues spotted

- [ISSUE-security: track_utility=on captures CREATE/ALTER ROLE … PASSWORD
  verbatim in shared-readable view (likely)] — see Trust boundary above;
  `pg_stat_statements.c:1202-1304` records the raw queryString without
  redaction for utility statements.
- [ISSUE-security: pg_stat_tmp/pgss_query_texts.stat readable by
  pg_read_server_files bypasses view's role-acl filter (likely)] —
  filesystem-level access to `:85` defeats the `:1867-1881` redaction.
- [ISSUE-defense-in-depth: no per-query length cap; an attacker can submit
  near-1GB queries to bloat the text file and trigger gc storms (maybe)] —
  `:2256-2261` only caps at `MaxAllocHugeSize`.
- [ISSUE-documentation: silent no-op when compute_query_id=off (nit)] —
  `:1296-1297` early-exits with no LOG / WARNING message.
- [ISSUE-audit-gap: entry_reset has no internal ACL check, relies entirely
  on SQL GRANT/REVOKE; a custom GRANT could open it widely (nit)] —
  `:2678-2791` no `superuser()` or `has_privs_of_role` guard in C.
- [ISSUE-audit-gap: pg_stat_statements_info.dealloc visible to PUBLIC leaks
  coarse cross-user workload signal (nit)] —
  `pg_stat_statements--1.12--1.13.sql:78` grants SELECT to PUBLIC on the
  view, and dealloc has no per-user partitioning.
- [ISSUE-correctness: gc_fail path bumps gc_count after wiping all texts to
  query_len=-1; concurrent pgss_store callers will see new gc_count, re-try
  qtext_store against the freshly recreated empty file, but the original
  entry's text is permanently lost (nit)] — `:2605-2654`; behavior is
  intentional per `:2643-2652` comment but the invariant "successful
  pgss_store ⇒ text retrievable" is silently violated.
- [ISSUE-concurrency: `qtext_load_file` reads file with NO lock and only
  detects truncation via short-read + errno==0 (nit)] — `:2310-2386`;
  relies on Linux/POSIX semantics that a `read()` past a concurrent
  `ftruncate` returns short, which is generally true but not guaranteed by
  POSIX on all filesystems.
- [ISSUE-api-shape: hash-collision attacker can dictate displayed text by
  being first to insert a (userid, dbid, queryid) tuple (nit)] — the
  jumble identity is the same for two literals-only-different queries; the
  first one wins.
