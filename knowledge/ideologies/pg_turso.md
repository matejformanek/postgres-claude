# pg_turso — a Zig logical-decoding output plugin that POSTs decoded rows to Turso

> Ideology note produced by the pg-extension-anthropologist cloud routine.
> Repo: `tursodatabase/pg_turso` @ branch `main`, fetched 2026-07-02.
> **ARCHIVED / deprecated** — the README's first line is a deprecation banner
> ("no longer supported"), much like decoderbufs was long inactive. Fetched
> files: `README.md`, `build.zig`, `Makefile`, `src/main.zig` (367 lines),
> `src/util.zig` (381 lines), `extension/pg_turso.control`,
> `extension/pg_turso--1.0.sql`. `build.zig.zon` and any `pg_turso.control` at
> repo root are 404 (the control file lives under `extension/`); PG server
> headers are vendored via a git submodule (`postgres/`), not in this repo.

## Domain & purpose

`pg_turso` is a **logical-decoding output plugin** that replicates a Postgres
table (or a materialized view) to a Turso/libSQL (SQLite-lineage) database at
the edge [from-README]. It plugs into PG's logical decoding machinery exactly
like decoderbufs and wal2json — it exports `_PG_output_plugin_init` and fills
an `OutputPluginCallbacks` struct (`src/main.zig:49-75`) [verified-by-code] —
but two things make it unusual in the corpus at once: (1) it is written in
**Zig**, not C (sibling to pgzx), and (2) instead of emitting bytes back
through the walsender to a `pg_recvlogical`-style consumer, it opens an **HTTP
client inside the plugin and POSTs the decoded changes directly to an external
Turso endpoint** (`src/util.zig:300-326`) [verified-by-code]. A thin
SQL/PL-pgSQL extension layer on top of `pg_cron` automates pulling changes on a
schedule (`extension/pg_turso--1.0.sql:40-67`) [verified-by-code].

## How it hooks into PG

- **PG_MODULE_MAGIC, hand-rolled in Zig.** The C `PG_MODULE_MAGIC` macro is
  reimplemented as an exported `Pg_magic_func` returning a hand-filled
  `Pg_magic_struct`, with the version hardcoded to `150000` → PG 15
  (`src/main.zig:19-46`) [verified-by-code]. There is no C shim; the magic
  symbol is produced from Zig.
- **Output-plugin init.** `pub export fn _PG_output_plugin_init(cb:
  [*c]pg.OutputPluginCallbacks)` assigns `startup_cb`, `shutdown_cb`,
  `begin_cb`, `change_cb`, `commit_cb`, `truncate_cb`, and
  `filter_by_origin_cb` to Zig functions declared `callconv(.C)`
  (`src/main.zig:49-75`) [verified-by-code]. All the streaming / two-phase
  callbacks are left commented out and `ctx.streaming = false`
  (`src/main.zig:60-74`, `:139`) [verified-by-code].
- **@cImport of raw server headers.** Both source files do
  `@cImport({ @cInclude("postgres.h"); @cInclude("replication/logical.h");
  @cInclude("utils/memutils.h"); @cInclude("utils/builtins.h");
  @cInclude("utils/lsyscache.h"); })` (`src/main.zig:4-10`,
  `src/util.zig:2-8`) [verified-by-code] — the whole PG API surface is consumed
  through Zig's `translate-c`, with no curated wrapper module.
- **LOAD / slot model.** Activated as a logical replication plugin named
  `pg_turso` (matching the `.so`): `SELECT
  pg_create_logical_replication_slot('pg_turso_slot', 'pg_turso')` then
  `pg_logical_slot_get_changes(slot, NULL, NULL, 'url', …, 'auth', …,
  'table_name', …)` [from-README] (`extension/pg_turso--1.0.sql:16-22`)
  [verified-by-code]. `url`, `auth`/`token`, and `table_name` arrive as plugin
  options parsed in `startup_cb` (`src/main.zig:106-136`) [verified-by-code].
- **Also a fmgr function + a CREATE EXTENSION.** `turso_send(url, token, data)`
  is a `LANGUAGE C STRICT` function exported from the same `.so`
  (`src/main.zig:331-359`, `extension/pg_turso--1.0.sql:70-71`)
  [verified-by-code], and the control file declares `requires = 'pg_cron'`
  (`extension/pg_turso.control:6`) [verified-by-code].

## Where it diverges from core idioms

**Axis 1 — it's an output plugin, but ships SQL to an external target.**
Core output plugins (decoderbufs → protobuf, wal2json → JSON change objects)
call `OutputPluginPrepareWrite` / `OutputPluginWrite` to hand bytes back to the
walsender, which a consumer drains. `pg_turso` sets
`OUTPUT_PLUGIN_TEXTUAL_OUTPUT` (`src/main.zig:103`) [verified-by-code] but
**never writes to the output stream at all**: `change_cb` renders each change
into a literal SQL statement — `INSERT INTO t (…) VALUES (…)`,
`UPDATE t SET … WHERE <pk>=…`, `DELETE FROM t WHERE …` — via `print_insert` /
`print_update` / `print_delete` (`src/util.zig:69-295`) [verified-by-code], and
accumulates them in a per-txn JSON array. At `commit_cb` it wraps them as
`{"statements":[ "BEGIN", …, "COMMIT" ]}` and **POSTs that JSON over HTTP to the
Turso URL** synchronously, blocking the decoding process on the network round
trip (`src/main.zig:256-285`, `src/util.zig:300-326`) [verified-by-code]. So
the "wire format" is SQL-replayed-as-JSON against libSQL, not a change-event
schema for a downstream consumer — replication is done by re-executing DML on
the target, PK-keyed with `ON CONFLICT REPLACE` semantics on the Turso side
[from-README].

**Axis 2 — Zig across the C ABI, and semi-machine-translated.** Unlike a C
plugin, callbacks are Zig `export`/`callconv(.C)` functions; unlike pgrx/pgzx
(which wrap PG in curated, hand-written idiomatic bindings), pg_turso talks to
`@cImport`ed headers directly and a large fraction of the body is visibly
`translate-c` output kept verbatim — the `foreach` list walk carries the
comment "the idiom below comes straight from translate-c" (`src/main.zig:111`),
the varlena/TOAST macros are re-expanded by hand because translate-c mangled
them (`src/util.zig:328-374`), and `print_literal` is flagged "ported from
translate-c output and probably prints garbage for most of the types"
(`src/util.zig:45-47`) [from-comment].

**Memory — two allocators side by side.** Plugin-lifetime state (`PgTursoData`)
is `palloc0`'d and owns a child `AllocSetContextCreateInternal` context; the
change callback switches into it and `MemoryContextReset`s after each change
(`src/main.zig:100-101`, `:167`, `:252-253`) [verified-by-code]. Per-txn state
is lazily `MemoryContextAllocZero`'d on `ctx.context` and `pfree`'d at commit
(`src/main.zig:183`, `:283`) [verified-by-code]. But the JSON statement strings
and the HTTP client live in a **Zig `GeneralPurposeAllocator`
(`std.heap`)** entirely outside PG's MemoryContext regime
(`src/main.zig:91-92`, `src/util.zig:297-326`) [verified-by-code], freed by
hand at commit/shutdown (`src/main.zig:144-146`, `:279-281`) [verified-by-code]
— PG's contexts and Zig's allocator run in parallel across the same callbacks.

## Notable design decisions

- **Single-table filter, not a publication.** Every change is compared against
  the one `table_name` option and dropped if it doesn't match; the code notes
  "we should accept a list of tables" (`src/main.zig:82`, `:176-179`)
  [verified-by-code].
- **UPDATE keyed on the primary key.** The `WHERE` clause is built from
  `RelationGetIndexAttrBitmap(relation, INDEX_ATTR_BITMAP_PRIMARY_KEY)`, using
  old-tuple key values when present (`src/main.zig:219`, `src/util.zig:194-244`)
  [verified-by-code].
- **`relrewrite` handling for materialized views.** When
  `class_form.relrewrite != 0` it resolves the real relation name via
  `get_rel_name`, and sets `opt.receive_rewrites = true`, so a `REFRESH
  MATERIALIZED VIEW` replicates as data (`src/main.zig:104`, `:171`)
  [verified-by-code].
- **TRUNCATE → `DELETE FROM`.** Turso has no native TRUNCATE decode target, so
  each truncated relation is emitted as `DELETE FROM t`
  (`src/main.zig:303-312`) [verified-by-code].
- **Hardcoded type-OID switch.** `print_literal` branches on literal OIDs
  (int/float/numeric bare, bit as `B'…'`, bool as `true`/`false`,
  text/varchar/uuid/json/jsonb/timestamp quoted) and falls through to a
  hand-rolled escaper for everything else (`src/util.zig:16-65`)
  [verified-by-code]; README concedes only int and text were tested
  [from-README].
- **A test-assert on the hot path.** `send` ends with
  `std.testing.expect(req.response.status == .ok)` marked `FIXME: remove`
  (`src/util.zig:325`) [verified-by-code] — a unit-test primitive left in the
  production replication path.
- **Fixed 64 KiB per-statement buffer.** Each rendered statement uses a stack
  `[65536]u8`, flagged as a TODO for a small vector (`src/main.zig:189-190`)
  [verified-by-code].
- **Old Zig build API.** `build.zig` uses `std.build.Builder`
  (pre-0.11), vendors headers via `addIncludePath("postgres/src/include")`, and
  sets `linker_allow_shlib_undefined = true` so PG symbols resolve at load time
  (`build.zig:3`, `:22-24`) [verified-by-code]; README pins "zig development
  version 2023-06-20 or higher" [from-README].
- **Automation via pg_cron, pulling not pushing.** The SQL layer schedules
  `pg_logical_slot_get_changes` calls through `cron.schedule`, and migrates the
  target schema by generating a `CREATE TABLE` and shipping it with `turso_send`
  (`extension/pg_turso--1.0.sql:40-67`, `:94-112`) [verified-by-code].

## Links into corpus

- [[decoderbufs]] — the protobuf logical-decoding output plugin; closest
  structural sibling (same `OutputPluginCallbacks` shape), contrasting wire
  format (protobuf vs SQL-in-JSON) and delivery (walsender stream vs HTTP push).
- [[wal2json]] — the JSON output plugin; contrast its consumer-facing
  change-event JSON with pg_turso's replay-SQL-in-JSON-over-HTTP.
- [[pgzx]] — the other Zig-in-the-backend member of the corpus; contrast pgzx's
  curated hand-written bindings with pg_turso's raw `@cImport` + translate-c.
- [[pglogical]], [[pgactive]] — logical-replication siblings for the broader
  "ship WAL changes elsewhere" family.

## Sources

- `https://raw.githubusercontent.com/tursodatabase/pg_turso/main/README.md` — HTTP 200.
- `https://raw.githubusercontent.com/tursodatabase/pg_turso/main/build.zig` — HTTP 200.
- `https://raw.githubusercontent.com/tursodatabase/pg_turso/main/Makefile` — HTTP 200.
- `https://raw.githubusercontent.com/tursodatabase/pg_turso/main/src/main.zig` — HTTP 200. Primary source (init, callbacks, memory, `turso_send`).
- `https://raw.githubusercontent.com/tursodatabase/pg_turso/main/src/util.zig` — HTTP 200. Statement rendering, HTTP `send`, TOAST macros.
- `https://raw.githubusercontent.com/tursodatabase/pg_turso/main/extension/pg_turso.control` — HTTP 200.
- `https://raw.githubusercontent.com/tursodatabase/pg_turso/main/extension/pg_turso--1.0.sql` — HTTP 200.
- `https://raw.githubusercontent.com/tursodatabase/pg_turso/main/build.zig.zon` — HTTP 404 (no zon; pre-package-manager Zig).
- `https://raw.githubusercontent.com/tursodatabase/pg_turso/main/pg_turso.control` — HTTP 404 (control lives under `extension/`).
- `https://api.github.com/repos/tursodatabase/pg_turso/git/trees/main?recursive=1` — HTTP 403 (GitHub API access not enabled this session); file set probed via raw fetches.
