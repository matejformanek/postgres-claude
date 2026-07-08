# pg_clickhouse — a two-driver (HTTP + native-binary) OLAP FDW with a push-fail shadow catalog

> Ideology note produced by the `pg-extension-anthropologist` cloud routine.
> Repo: `ClickHouse/pg_clickhouse` @ branch `main`. 253★, language **C**, an
> OFFICIAL ClickHouse project (first commit 2025-09). All `file:line` cites
> below point into that repo (cited as `src/fdw.c:NN`, `src/pglink.c:NN`, …),
> not `source/`, since this doc characterizes an *external* extension. Cites
> verified against the files fetched on 2026-07-07 (see Sources footer).
> Backend target: ClickHouse v23+ reached over EITHER the HTTP interface
> (libcurl, TabSeparated text) OR the native TCP protocol (a vendored
> header-only `clickhouse-c` C library, LZ4/ZSTD framing, OpenSSL TLS). PG 13+
> (`META.json:34`, `README.md:8` `[from-README]`).

pg_clickhouse is the **remote-OLAP FDW done as a full postgres_fdw-class
deparser** — the opposite end of the design axis from
`[[knowledge/ideologies/pg_duckdb]]`, which throws the plan away at
`planner_hook`. pg_clickhouse instead keeps the whole FdwRoutine machine and
pours its energy into (a) an aggressive deparser that translates PG functions,
operators, JOINs and aggregates into ClickHouse SQL, and (b) a **pluggable
transport layer**: one `libclickhouse_methods` vtable per driver, selected at
connect time. Its lineage is the archived **ildus/clickhouse_fdw** (visible in
the `Portions Copyright (c) 2019-2022, Adjust GmbH` / Ildus Kurbangaliev
headers, e.g. `src/fdw.h:6-8`), but where that ancestor spoke the native
protocol through the C++ `clickhouse-cpp` library, pg_clickhouse reimplements
both transports in C and adds the HTTP driver as the default.

## Domain & purpose

Query ClickHouse from Postgres with "no rewriting any SQL" (`README.md:6-8`
`[from-README]`): `CREATE FOREIGN TABLE ... SERVER ch` and a `SELECT`/`JOIN`/
`GROUP BY` over it is deparsed to ClickHouse SQL, shipped, and the result
streamed back as tuples. The README's TPC-H table shows the ambition — full
single-scan pushdown on ~12 of 22 queries, the rest partial (`README.md:40-64`
`[from-README]`). Scope today is **read + append-only INSERT**; UPDATE/DELETE
are an explicit TODO ("via ClickHouse mutations", `src/fdw.c:3690`
`[verified-by-code]`). It also ships SRF escape hatches —
`clickhouse_query(server, sql)` returning `SETOF record` and
`clickhouse_raw_query(sql, connstring)` returning text — both `REVOKE`d from
`PUBLIC` (`sql/pg_clickhouse.sql:15-40` `[verified-by-code]`).

## How it hooks into PG

Textbook SQL/MED wiring: `CREATE FOREIGN DATA WRAPPER clickhouse_fdw HANDLER
clickhouse_fdw_handler VALIDATOR clickhouse_fdw_validator`
(`sql/pg_clickhouse.sql:46-49`). The handler `makeNode(FdwRoutine)`s and fills a
callback set (`src/fdw.c:3666-3715` `[verified-by-code]`) — this is the
`[[knowledge/subsystems/foreign]]` / `[[knowledge/idioms/fdw-routine-callbacks]]`
pattern, NOT the plan-replacement pattern.

The installed callbacks (`src/fdw.c:3671-3712` `[verified-by-code]`):

- **Planning + scan:** `GetForeignRelSize`, `GetForeignPaths`,
  `GetForeignPlan`, `BeginForeignScan`, `IterateForeignScan`,
  `ReScanForeignScan`, `EndForeignScan`, `RecheckForeignScan`.
- **Pushdown (the ambitious part):** `GetForeignJoinPaths`
  (`clickhouseGetForeignJoinPaths`, `src/fdw.c:2540`) AND `GetForeignUpperPaths`
  (`clickhouseGetForeignUpperPaths`, `src/fdw.c:2894`) — so JOINs and
  grouping/aggregation push down, unlike `[[knowledge/ideologies/tds_fdw]]`.
- **DML (append-only):** `PlanForeignModify`, `BeginForeignModify`,
  `BeginForeignInsert`, `ExecForeignInsert`, `EndForeignInsert`/
  `EndForeignModify` (both point at `clickhouseEndForeignInsert`). No
  `ExecForeignUpdate`/`Delete`; no `ExecForeignBatchInsert`/
  `GetForeignModifyBatchSize` — deliberately, because "both drivers already
  buffer rows and stream them as a single INSERT" (`src/fdw.c:3685-3694`
  `[verified-by-code]`).
- **DDL/introspection:** `ExplainForeignScan`, `AnalyzeForeignTable`,
  `ImportForeignSchema` (`clickhouseImportForeignSchema` →
  `chfdw_construct_create_tables`, which reads `system.tables`/`system.columns`
  and emits `CREATE FOREIGN TABLE` DDL, `src/pglink.c:1528-1712`).

`_PG_init` lives in `src/option.c:676` and is small: it defines two GUCs and
reserves the prefix. No `shared_preload_libraries` requirement (contrast
pg_duckdb) — the module loads lazily on first FDW use. GUCs
(`src/option.c:686-716` `[verified-by-code]`): `pg_clickhouse.session_settings`
(string, `PGC_USERSET`, default `"join_use_nulls 1, group_by_use_nulls 1,
final 1"` — key/value ClickHouse session settings forwarded on every query) and
`pg_clickhouse.pushdown_regex` (bool, default true — lets users disable regex
pushdown because "ClickHouse and Postgres use fundamentally different regular
expression engines"). `MarkGUCPrefixReserved("pg_clickhouse")` on PG ≥ 15
(`src/option.c:719`).

**The binary-vs-HTTP driver dispatch** is the load-bearing structural choice.
`clickhouse_connect` reads the `driver` option (server- then user-mapping-level,
default `"http"`) and calls `chfdw_http_connect` or `chfdw_binary_connect`
(`src/connection.c:53-95` `[verified-by-code]`). Each returns a `ch_connection`
= `{ libclickhouse_methods *methods; void *conn; bool is_binary; }`
(`src/fdw.h:106-110`). Every later operation goes through the vtable —
`conn.methods->simple_query(conn.conn, &query)`,
`->fetch_row`, `->disconnect`, `->server_version`, `->is_broken` — so fdw.c and
deparse.c never learn which transport they're on. The two vtables are static
structs in `src/pglink.c`: `http_methods` (`:59-68`) and `binary_methods`
(`:105-116`).

## Where it diverges from core idioms

### 1. Two full transport implementations behind one function-pointer vtable

This is the sharpest architectural divergence from a normal single-transport
FDW. `libclickhouse_methods` (`src/fdw.h:92-104`) is a struct of ten function
pointers; `ch_connection` carries a pointer to whichever vtable the driver
option selected. The **HTTP driver** (`src/http.c` + `src/http_streaming.c`,
using libcurl + libuuid for query-ids) talks to ports 8123/8443 and parses
ClickHouse's `TabSeparated` text format; it supports a streaming cursor
(`http_streaming_query`, `src/pglink.c:456`) built on CURL pause/resume so
memory stays proportional to the fetch batch. The **binary driver**
(`src/binary/*.c` + the vendored header-only `vendor/clickhouse-c` library)
opens a raw TCP socket to ports 9000/9440, does its own OpenSSL handshake,
speaks the native columnar protocol with LZ4/ZSTD block compression, and reads
the server version straight out of the protocol handshake rather than issuing
`SELECT version()` (`src/binary/connection.c:361-390`,
`src/binary/connection.c:260-349` `[verified-by-code]`). Their capability sets
differ and the vtable encodes it: `binary_methods` sets `.streaming_query =
NULL, .streaming_fetch_row = NULL` (no HTTP-style streaming) but provides
`.finalize_insert` and `.is_broken`, both `NULL` on the HTTP side
(`src/pglink.c:59-68`, `:105-116` `[verified-by-code]`). Contrast
`[[knowledge/ideologies/pg_duckdb]]` / `[[knowledge/ideologies/cstore_fdw]]`,
which have one embedded engine; pg_clickhouse's engine is remote and reachable
two ways.

### 2. The push-fail shadow catalog: functions and aggregates that exist only to be pushed down

pg_clickhouse installs real Postgres catalog objects whose C bodies are
**designed to fail or no-op**, so they serve purely as a pushdown vocabulary. If
a query names one and the deparser ships it to ClickHouse, great; if it ever
executes *locally* it raises `pg_clickhouse: failed to push down …`. The
handlers are `clickhouse_op_push_fail` (`src/fdw.c:3730-3739`, takes the
op-name as text) and `clickhouse_push_fail` (`src/fdw.c:3745-3754`, reads its
own `fn_oid`), plus `clickhouse_noop` returning NULL (`src/fdw.c:3721-3724`).
The SQL script wires these into user-facing objects: `argMax`/`argMin`
aggregates whose sfunc is an error-raising PL/pgSQL stub, and a `quantile`
aggregate whose `SFUNC = ch_any_text` (→ `clickhouse_op_push_fail`) with
`FINALFUNC = ch_noop_float8_float8` (→ `clickhouse_noop`) and an `INITCOND`
string naming what to push down (`sql/pg_clickhouse.sql:52-118`
`[verified-by-code]`). This is a genuinely novel use of the catalog: rather than
silently computing a possibly-wrong local answer for a ClickHouse-only
aggregate, the extension makes local execution a **loud, typed error**. No core
FDW does this; it's the inverse of the postgres_fdw philosophy where anything
un-shippable just runs locally.

### 3. Single-query-per-connection forces a busy-lease + private-connection scheme

Connections are cached in a hash keyed by user-mapping OID (`ConnCacheEntry`,
`src/fdw.h:365-377`; `hash_create` in `CacheMemoryContext`,
`src/connection.c:104-123`) — the postgres_fdw shape. But ClickHouse permits
**only one query in flight per connection**, so a normal per-user cached
connection breaks correlated/nested scans. pg_clickhouse adds a *leasing* layer
(`src/fdw.h:271-286`, `src/connection.c:201-263` `[verified-by-code]`):
`chfdw_get_scan_connection` hands out the cached connection marked `busy` if
free; otherwise it opens a **private** connection (tracked in a
`PrivateConnections` list allocated in `CacheMemoryContext`) exclusively for
that scan. `chfdw_release_scan_connection` either drops the busy lease (cache
owns closing) or disconnects the private one. A `RegisterXactCallback`
(`chfdw_xact_callback`, `src/connection.c:321-348`) closes any private
connection whose scan's End was skipped on error and clears leftover busy
markers at commit/abort. Syscache invalidation callbacks on `FOREIGNSERVEROID`
and `USERMAPPINGOID` mark entries `invalidated` for lazy reconnect
(`src/connection.c:120-121`, `:290-312`) — see
`[[knowledge/idioms/cache-invalidation-registration]]`. A broken-connection
guard (`methods->is_broken`, binary only) drops sockets that hit an
unrecoverable protocol/IO error so the next statement doesn't surface a useless
"Broken pipe" (`src/connection.c:157-162` `[verified-by-code]`).

### 4. Foreign-side result data lives outside palloc but is anchored to a MemoryContext reset callback

Where `[[knowledge/ideologies/tds_fdw]]` frees its raw db-lib handles by hand in
`EndForeignScan`, pg_clickhouse ties every foreign resource to a
`MemoryContext` via `MemoryContextRegisterResetCallback`
(`[[knowledge/idioms/memory-contexts]]`, `[[knowledge/idioms/abort-transaction-cleanup]]`).
A cursor is a per-query child of `PortalContext`; its callback frees the curl
response (`http_cursor_free`) or the binary response + conversion states
(`binary_cursor_free`) on reset/delete (`src/pglink.c:308-401`, `:928-1006`,
`:1250-1262` `[verified-by-code]`). The **binary connection's raw fd and OpenSSL
`SSL*`** live under a dedicated `CacheMemoryContext` child whose reset callback
(`binary_state_reset_cb`) does the `close()`/`SSL_free()`, so an aborted
transaction that deletes the context also closes the socket
(`src/binary/connection.c:290-306`, `:70-91`, `:393-403` `[verified-by-code]`;
`src/binary.h:1-8` `[from-comment]`). The curl body buffer and the C-library
response are malloc'd/library-owned (outside palloc) but never leak because the
context callback owns them. This is the disciplined version of the
foreign-handle-ownership problem.

### 5. Aggressive, ClickHouse-specific deparser (deparse.c is ~6000 lines)

`src/deparse.c` is a postgres_fdw-derived deparser
(`classifyConditions`→`chfdw_classify_conditions`, `is_foreign_expr`→
`chfdw_is_foreign_expr` with a `foreign_expr_walker` collation state machine,
`src/deparse.c:371-406`, `:519-…` `[verified-by-code]`) grown far past its
origin. The `custom_object_type` enum (`src/fdw.h:380-432`) enumerates dozens of
PG→ClickHouse rewrites: `date_trunc`/`date_part`, `datetime ± interval`,
`regexp_match`→`extract`/`extractAll`, `regexp_replace`→`replaceRegexpOne/All`,
`@>`/`<@`/`&&` array operators → `hasAll`/`hasAny`, `string_agg`→
`groupConcat`, `to_char`→`formatDateTime` (with a strict format translator,
`chfdw_translate_to_char_format`, `src/fdw.h:495-496`), `->`/`->>` JSON ops →
`col."k1"."k2"`, and so on. It also models ClickHouse table engines
(`CHRemoteTableEngine`, `CollapsingMergeTree`/`AggregatingMergeTree` sign
handling in `CHFdwRelationInfo.ch_table_sign_field`, `src/fdw.h:138-142`,
`:240-247`) so aggregates over collapsing tables deparse correctly. The
`final 1` default session setting (`src/option.c:691`) forces ClickHouse to
merge parts for consistent reads. This is much heavier pushdown than tds_fdw and
a different strategy from pg_duckdb: deparse-to-remote-SQL, not
serialize-and-embed.

### 6. Error firewall across a C (not C++) driver boundary, with remote KILL on cancel

The binary driver is C and returns error codes (`chc_err`), so there is no C++
exception unwinding to trap (contrast pg_duckdb's `InvokeCPPFunc` trampoline,
`[[knowledge/ideologies/pg_duckdb]]` §6). The boundary discipline is instead:
translate library return codes to `ereport` (`raise_chc`,
`src/binary/connection.c:333-337`), and wrap the connect path in `PG_TRY`/
`PG_CATCH` so a palloc failure deletes the connection's MemoryContext before
re-throwing (`src/binary/connection.c:297-345`). Both drivers pass a
`check_cancel`/progress callback that polls `QueryCancelPending`/`ProcDiePending`
(`is_canceled`, `http_progress_callback`, `src/pglink.c:118-141`); on cancel the
HTTP path issues a `KILL QUERY WHERE query_id=…` back to ClickHouse so the
remote query actually stops (`kill_query`, `src/pglink.c:238-254`, called from
`http_simple_query` and the streaming fetch path, `:338-346`, `:553-564`
`[verified-by-code]`). The HTTP driver also retries transport errors up to 3×
(`again:` loop, `src/pglink.c:317-337`). Header-injection is blocked by
rejecting newlines in the database name before it goes into a plaintext HTTP
header (`src/pglink.c:157-173` `[verified-by-code]`).

### 7. TLS and compression handled twice, once per driver, with a cloud-host heuristic

There is no shared TLS layer — each driver does its own. HTTP uses libcurl:
`min_tls_version` maps to `CURLOPT_SSLVERSION`, basic-auth credentials go in the
URL (curl-escaped), default ports 8123 plain / 8443 TLS (`src/http.c:44-65`,
`:120`, `:143-150` `[verified-by-code]`). Binary uses hand-rolled OpenSSL
(`SSL_CTX`, `SSL_set_fd`) plus `chc_lz4_codec_init`/`chc_zstd_codec_init` for
native-protocol block compression, default ports 9000 plain / 9440 TLS
(`src/binary/connection.c:25-32`, `:151-231`, `:288-321` `[verified-by-code]`).
Both consult a **cloud-host heuristic** `ch_is_cloud_host` (declared
`src/internal.h:26`): under the default `secure = auto` TLS mode, a host that
looks like ClickHouse Cloud gets the secure port + TLS automatically
(`src/http.c:120`, `src/binary/connection.c:279-285` `[verified-by-code]`). The
`secure` option (auto/on/off, `tls_mode`) and `min_tls_version` (accepting the
same spellings as PG's `ssl_min_protocol_version`) are the shared knobs, parsed
once in `src/option.c:379-397` and threaded into both drivers via
`ch_connection_details` (`src/engine.h:26-37`).

## Notable design decisions (cited)

- **Driver split is data, not code.** The `driver` option ("http"|"binary")
  selects a static vtable at connect time; every call site is
  transport-agnostic (`src/connection.c:84-88`, `src/fdw.h:92-110`,
  `src/pglink.c:59-116` `[verified-by-code]`). Capability differences are `NULL`
  vtable slots, not `if (is_binary)` branches.
- **Push-fail as a correctness guarantee.** `clickhouse_op_push_fail` /
  `clickhouse_push_fail` / `clickhouse_noop` back catalog aggregates
  (`argMax`, `argMin`, `quantile`) that raise `fdw_error` if executed locally
  rather than returning a wrong answer (`src/fdw.c:3721-3754`,
  `sql/pg_clickhouse.sql:52-118` `[verified-by-code]`).
- **Append-only DML, single INSERT stream.** INSERT callbacks present; no
  UPDATE/DELETE ("TODO … via ClickHouse mutations"); no batch-insert callback
  because both drivers buffer and stream one INSERT (`src/fdw.c:3685-3694`).
  HTTP INSERT uses `FORMAT TSV` with `\N` nulls and a 512 MB flush threshold
  (`http_insert_tuple`, `src/pglink.c:809-892`); binary INSERT appends columnar
  blocks with autoflush (`binary_insert_tuple`, `src/pglink.c:1307-1341`).
- **JSON round-trip avoidance.** When a CH `JSON` column maps to a foreign
  column declared `json` (not `jsonb`), the binary path overrides `state->coltypes`
  to `JSONOID` so CH's exact byte formatting survives instead of being reformatted
  by `jsonb_in`/`jsonb_out` (`src/pglink.c:966-986` `[verified-by-code]`).
- **`IMPORT FOREIGN SCHEMA` reads system tables and synthesizes DDL**, mapping
  CH types via a `str_types_map` table and recursive `parse_type`
  (`Nullable`/`LowCardinality`/`Array`/`AggregateFunction`/`Decimal(p,s)`→
  `NUMERIC(p,s)`, `Enum*`→`TEXT`, …), emitting `AggregateFunction` column
  OPTIONS and `NOT NULL` for non-Nullable columns (`src/pglink.c:1386-1712`
  `[verified-by-code]`).
- **`relocatable = true`** (`pg_clickhouse.control:4`) — unlike pg_duckdb's
  pinned schema; pg_clickhouse's objects don't hardcode their namespace.
- **Own literal escaper, not `quote_literal_cstr`.** `ch_escape_string` /
  `ch_quote_literal` never emit E-quoted strings and match ClickHouse's
  `TabSeparated`/`WriteHelpers` escaping (`src/pglink.c:1714-1823`
  `[from-comment]`).

## Links into corpus

- `[[knowledge/subsystems/foreign]]` + `[[knowledge/idioms/fdw-routine-callbacks]]`
  — the `FdwRoutine` dispatch, catalog accessors, and join/upper-rel pushdown
  hooks this extension fills; the single most important cross-ref.
- `[[knowledge/idioms/fdw-iterate-scan]]` — the `ExecClearTuple`/per-column
  `InputFunctionCall` scan loop the HTTP path follows (`char_to_datum`,
  `src/pglink.c:694-721`).
- `[[knowledge/subsystems/contrib-postgres_fdw]]` — the ancestor of `deparse.c`,
  `classifyConditions`, the connection-cache-by-user-mapping shape, and
  `use_remote_estimate`; pg_clickhouse = postgres_fdw's deparser + a pluggable
  transport + ClickHouse function translation + push-fail.
- `[[knowledge/ideologies/tds_fdw]]` — the conformant read-only foil: pg_clickhouse
  is the *maximal* FDW (JOIN+agg+upper pushdown, DML, two drivers) where tds_fdw
  is the minimal one; both anchor foreign handles differently (tds_fdw hand-frees,
  pg_clickhouse uses MemoryContext reset callbacks).
- `[[knowledge/ideologies/pg_duckdb]]` — the opposite remote-OLAP strategy:
  pg_duckdb replaces the whole plan at `planner_hook` and embeds the engine;
  pg_clickhouse keeps the plan, deparses to remote SQL, and reaches a remote
  engine. Same domain, inverse mechanism.
- `[[knowledge/ideologies/cstore_fdw]]` — FDW-as-columnar-storage; the
  "smuggle a columnar engine in through the FDW seam" sibling.
- `[[knowledge/ideologies/wrappers]]` + `[[knowledge/ideologies/steampipe_postgres_fdw]]`
  + `[[knowledge/ideologies/deltax]]` — other remote/virtual FDWs; wrappers is
  the Rust-framework high-divergence end, steampipe the API-plugin end.
- `[[knowledge/idioms/memory-contexts]]` + `[[knowledge/idioms/abort-transaction-cleanup]]`
  — the `MemoryContextRegisterResetCallback` ownership of curl buffers, binary
  responses, and the raw socket/`SSL*`.
- `[[knowledge/idioms/cache-invalidation-registration]]` — the syscache +
  xact callbacks driving connection invalidation and the busy-lease cleanup.
- `[[knowledge/idioms/error-handling]]` — `ERRCODE_FDW_*` SQLSTATEs, the
  push-fail `ereport`s, the `check_cancel`→remote-`KILL QUERY` path, and the
  C-return-code→`ereport` firewall (contrast pg_duckdb's C++ trampoline).
- `[[knowledge/idioms/fmgr]]` — the `PG_FUNCTION_INFO_V1` handler/validator +
  SRF (`clickhouse_query`) plumbing.
- `.claude/skills/fdw-development/SKILL.md` + `.claude/skills/gucs-config/SKILL.md`
  — the FdwRoutine callback set, pushdown decisions, and the two `PGC_USERSET`
  GUCs (`session_settings`, `pushdown_regex`).

## Sources

Fetched 2026-07-07 (branch `main`), all via
`https://raw.githubusercontent.com/ClickHouse/pg_clickhouse/main/<path>`.
Source set resolved from `Makefile` `OBJS = $(wildcard src/*.c src/*/*.c)` and
include dir `src/include`.

- `README.md` → HTTP 200.
- `Makefile` → HTTP 200 (driver deps: `-lssl -lcrypto -llz4 -lzstd`,
  `curl-config`, `-luuid`, vendored `vendor/clickhouse-c`).
- `META.json` → HTTP 200. `pg_clickhouse.control` → HTTP 200.
- `sql/pg_clickhouse.sql` → HTTP 200 (FDW + push-fail aggregate wiring, first
  120 lines read).
- `src/connection.c` → HTTP 200 (392 lines; cache, busy-lease, xact/inval
  callbacks — deep-read).
- `src/pglink.c` → HTTP 200 (1883 lines; both vtables, cursor lifecycle,
  HTTP+binary fetch/insert, IMPORT FOREIGN SCHEMA, literal escaping — deep-read).
- `src/fdw.c` → HTTP 200 (3762 lines; FdwRoutine handler + push-fail stubs +
  SRF entry points read; scan/join/upper/analyze bodies skimmed via grep).
- `src/option.c` → HTTP 200 (721 lines; `_PG_init`, GUCs, valid-options table,
  TLS/`secure`/`min_tls_version` parsing — deep-read of load path).
- `src/http.c` → HTTP 200 (311 lines; ports, TLS→CURLOPT_SSLVERSION, cloud-host
  heuristic, basic-auth URL — grep-level).
- `src/http_streaming.h` → HTTP 200 (header, deep-read). `src/http.h` → HTTP 200.
- `src/binary/connection.c` → HTTP 200 (404 lines; OpenSSL handshake,
  LZ4/ZSTD, ports, MemoryContext reset-callback cleanup — deep-read).
- `src/binary/binary.c` → HTTP 200 (105 lines). `src/binary/convert.c`,
  `src/binary/decode.c`, `src/binary/encode.c` → HTTP 200 (present, not
  deep-read; roles inferred from `src/include/binary.h`).
- Headers: `src/include/fdw.h` (524 lines, deep-read), `src/include/binary.h`
  (155), `src/include/engine.h`, `src/include/server_version.h`,
  `src/include/internal.h`, `src/include/http.h`, `src/include/http_streaming.h`,
  `src/include/kv_list.h`, `src/include/version.h.in` → HTTP 200.
- `src/deparse.c` → HTTP 200 (5995 lines; structure + `custom_object_type`
  enum + `foreign_expr_walker`/`chfdw_is_foreign_expr` read via grep, NOT
  line-by-line — the per-function CH translations are characterized from the
  enum comments in `src/fdw.h:380-432`, tagged `[from-comment]` where beyond a
  declaration).

**Could NOT resolve (404):** `src/shippable.c` (functions `chfdw_is_builtin`/
`chfdw_is_shippable`/`chfdw_is_equal_op` are declared "in shippable.c" at
`src/fdw.h:356-360` but no such path exists — they live in another compiled
`.c`, unread; claims about shippability logic are `[inferred]` from the header).
`vendor/clickhouse-c/clickhouse.h` (git submodule, 404 on raw — the binary
driver's `chc_*` API is characterized from `src/include/binary.h` and call
sites, tagged `[inferred]` where it exceeds those). `src/binary/binary.h`,
`src/binary/{read,write,types,columns,protocol,block}.c`,
`src/{types,convert,query,scan,driver}.c` (all 404 — do not exist under those
names; the binary internals are `src/binary/{binary,connection,convert,decode,
encode}.c`). All non-`[from-README]`/`[from-comment]`/`[inferred]` claims are
`[verified-by-code]` against the fetched `.c`/`.h`.
