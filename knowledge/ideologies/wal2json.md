# wal2json — a logical-decoding output plugin, not a `CREATE EXTENSION` extension

> Ideology note produced by the `pg-extension-anthropologist` cloud routine.
> Repo: `eulerto/wal2json` @ branch `master`. All `file:line` cites below point
> into that repo (not `source/`), since this doc characterizes an *external*
> module's relationship to core idioms. Cites verified against the files fetched
> on 2026-06-11 (see Sources footer). wal2json is a single C translation unit
> (`wal2json.c`, 3373 lines) plus a README — there is no `.c`/`.h` split and,
> notably, **no `.control` file at all**.

## Domain & purpose

wal2json turns the contents of the write-ahead log into JSON. It is "an output
plugin for logical decoding [with] access to tuples produced by INSERT and
UPDATE [and] UPDATE/DELETE old row versions ... depending on the configured
replica identity" (`README.md:6`) `[from-README]`. Downstream tools consume the
JSON either over the streaming replication protocol (a logical replication slot)
or through the SQL API (`pg_logical_slot_get_changes`). It is the
canonical change-data-capture (CDC) feed for the Debezium-style ecosystem, and
the most architecturally important thing about it for this corpus is what it is
*not*: it is **not a loadable SQL extension**. There is no `wal2json.control`,
no `CREATE EXTENSION wal2json`, no SQL objects installed. It is a `.so` whose
only job is to export one symbol that the logical-decoding machinery looks up by
name when you create a slot with `plugin = 'wal2json'`. Two wire formats coexist
in the one file: format version 1 emits "a JSON object per transaction"
(all tuples buffered into one object) and version 2 emits "a JSON object per
tuple" (`README.md:8-10`, `WAL2JSON_FORMAT_VERSION 2` at `wal2json.c:40`)
`[from-README]`.

## How it hooks into PG

There is no `.control` file and the SQL surface is empty; the entire integration
is the **output-plugin callback table**. `_PG_init` is a no-op
(`wal2json.c:226-229`) `[verified-by-code]` — wal2json does not install executor
/ planner / utility hooks, define GUCs, or request shmem. Instead it exports
`_PG_output_plugin_init(OutputPluginCallbacks *cb)`, marked `PGDLLEXPORT`
(`wal2json.c:53`), which the logical decoder calls to populate the callback
struct (`wal2json.c:232-253`) `[verified-by-code]`:

```
cb->startup_cb        = pg_decode_startup;     /* parse slot options, pick format */
cb->begin_cb          = pg_decode_begin_txn;   /* emit BEGIN (or nothing in v1) */
cb->change_cb         = pg_decode_change;       /* the workhorse: one row change  */
cb->commit_cb         = pg_decode_commit_txn;  /* emit COMMIT / flush v1 buffer   */
cb->shutdown_cb       = pg_decode_shutdown;
cb->filter_by_origin_cb = pg_filter_by_origin;  /* (>= 9.5) drop replicated-in rows*/
cb->message_cb        = pg_decode_message;      /* (>= 9.6) logical WAL messages   */
cb->truncate_cb       = pg_decode_truncate;     /* (>= 11) TRUNCATE                */
```

`pg_decode_startup` sets `opt->output_type = OUTPUT_PLUGIN_TEXTUAL_OUTPUT`
(`wal2json.c:329`) `[verified-by-code]` — the JSON is text, not a binary
protocol, so it is human-readable in `pg_recvlogical`. Each emitted chunk is
bracketed by the core helpers `OutputPluginPrepareWrite(ctx, true)` …
`OutputPluginWrite(ctx, true)` (`wal2json.c:850/885`, `:897/930`,
`:995/1003`, …) `[verified-by-code]`, which is the contract every output plugin
must follow to hand a string back to the walsender. Cross-ref
`[[knowledge/subsystems/replication]]` (the decoding framework that owns
these callbacks), `[[knowledge/architecture/wal]]` (the WAL these callbacks
re-materialize), and the `replication-overview` skill (output-plugin callback
list).

## Where it diverges from core idioms

### 1. No `.control`, no `CREATE EXTENSION` — loaded by name from a slot

Almost every other entry in `knowledge/ideologies/` is a `.so` + `.control` +
SQL install script reached through `CREATE EXTENSION`. wal2json has none of
that. The backend never runs a wal2json install script; the module becomes live
only when a logical slot names it (`pg_create_logical_replication_slot('s',
'wal2json')`), at which point the decoder `dlopen`s `$libdir/wal2json` and calls
`_PG_output_plugin_init`. So the "extension-development" checklist
(`.control` fields, `default_version`, upgrade scripts, `trusted`) is entirely
inapplicable — its versioning lives in `#define WAL2JSON_VERSION "2.6"`
(`wal2json.c:37`) and a *wire* `format_version` option, not in an
`ALTER EXTENSION ... UPDATE` chain. This is the cleanest example in the corpus
of "a PG plugin that is not a PG extension." Cross-ref
`.claude/skills/extension-development/SKILL.md` (the checklist that does *not*
apply here).

### 2. One giant `#if PG_VERSION_NUM` ladder instead of one source per release

Core extensions in-tree are compiled against exactly one server version.
wal2json instead ships a single file that compiles against PG 9.4 → 18 by
threading `#if PG_VERSION_NUM` around every API that shifted. The
output-plugin init guards `filter_by_origin_cb` behind `>= 90500`,
`message_cb` behind `>= 90600`, `truncate_cb` behind `>= 110000`
(`wal2json.c:244-252`); `PG_MODULE_MAGIC_EXT` (named-module form) is used on
`>= 180000` and the bare `PG_MODULE_MAGIC` below it (`wal2json.c:43-50`)
`[verified-by-code]`. Most strikingly, the progress-reporting call is wrapped in
a private `update_replication_progress()` shim whose **signature changes three
times across releases** — a documented comment explains the churn:
`OutputPluginUpdateProgress` gained, then changed, then regained a `skipped_xact`
parameter between PG 10, 15, and 16 (`wal2json.c:940-973`) `[from-comment]`. A
core module would simply track HEAD; an out-of-tree plugin that must run on six
server generations rebuilds that portability layer by hand.

### 3. Per-transaction memory discipline: a private AllocSet under `TopMemoryContext`, reset per change

A core decoding consumer leans on the reorder buffer's contexts. wal2json
instead creates its own `AllocSetContext` named `"wal2json output context"` as a
child of `TopMemoryContext` in `pg_decode_startup` (`wal2json.c:264-273`)
`[verified-by-code]`, and in the change callback switches into it, builds the
JSON, writes it out, then `MemoryContextReset(data->context)` before returning —
including on every early-out path (`wal2json.c:1784-1786`, `:1799-1801`,
`:1822-1824`) `[verified-by-code]`. Anchoring under `TopMemoryContext` (not the
per-call context) is deliberate: the plugin's `JsonDecodingData` must survive
for the life of the decoding session across thousands of change callbacks, while
the *per-row* scratch is freed by the reset. This is a textbook application of
the `memory-contexts` idiom in a callback that core calls in a tight loop.
Cross-ref `[[knowledge/idioms/memory-contexts]]`.

### 4. Replica-identity is a first-class correctness gate, surfaced as a `WARNING`

Logical decoding can only see old-row columns that replica identity preserves.
wal2json encodes this directly: for UPDATE and DELETE it bails out with
`elog(WARNING, "table \"%s\" without primary key or replica identity is
nothing")` when `!OidIsValid(relation->rd_replidindex) &&
relation->rd_rel->relreplident != REPLICA_IDENTITY_FULL`
(`wal2json.c:1795-1801`, `:1818-1824`) `[verified-by-code]`, and elsewhere
branches its key-emission on `relreplident == REPLICA_IDENTITY_DEFAULT`
(`wal2json.c:1895`, `:1927`, `:2526`). Rather than silently producing a change
row with no usable key, it drops the change and warns — pushing a schema
requirement (`ALTER TABLE ... REPLICA IDENTITY FULL` / a PK) onto the operator.
This is the same `rd_replidindex` contract core's own `pgoutput` honors, made
visible at the JSON boundary. Cross-ref
`[[knowledge/subsystems/replication]]`,
`[[knowledge/data-structures/heap-tuple-layout]]` (the old/new tuple pair the
callback receives).

### 5. Two parallel callback families (`*_v1` / `*_v2`) selected by an option, not two plugins

Because v1 is per-transaction and v2 is per-tuple, wal2json carries a complete
*second* set of begin/commit/change/message/truncate functions
(`pg_decode_*_v1` at `wal2json.c:164-182`, `pg_decode_*_v2` at `:184-205`)
`[verified-by-code]` and dispatches on `data->format_version` from inside the
registered top-level callbacks. v1 buffers all tuples and emits one object at
`commit`; v2 streams an object per row and optionally brackets the txn. Shipping
two whole emit strategies behind one option (rather than two plugins, or a
clean strategy interface) is a pragmatic divergence driven by the need to keep a
years-old wire format working while offering a streaming-friendlier one.

## Notable design decisions (cited)

- **`_PG_init` is empty** (`wal2json.c:226-229`) — all state is per-session,
  created in `pg_decode_startup` from slot options, so there is nothing to do at
  module load and no reason to require `shared_preload_libraries`.
- **Textual output** (`opt->output_type = OUTPUT_PLUGIN_TEXTUAL_OUTPUT`,
  `wal2json.c:329`) — JSON is emitted as text, readable directly via
  `pg_recvlogical`; the plugin never opts into binary output.
- **Origin filtering for loop avoidance** — `pg_filter_by_origin`
  (`wal2json.c:795`) lets a consumer drop changes that arrived via replication,
  with the parameter type itself renamed `RepOriginId` → `ReplOriginId` across
  versions (`wal2json.c:135-137`) — another point on the portability ladder.
- **Rich option surface parsed in `startup`** — dozens of booleans
  (`include_xids`, `include_timestamp`, `include_pk`, `numeric_data_types_as_string`,
  table/origin/message allow- and deny-lists) live in `JsonDecodingData`
  (`wal2json.c:63-107`) and are filled from the slot's option list, so behavior
  is per-slot, set at `START_REPLICATION` time, with no GUCs and no catalog.
- **`AssertVariableIsOfType(&_PG_output_plugin_init, LogicalOutputPluginInit)`**
  on pre-16 servers (`wal2json.c:236`) — a compile-time guard that the exported
  symbol still matches core's expected signature, the output-plugin analogue of
  the ABI assertions other extensions use against private core symbols.

## Links into corpus

- `[[knowledge/subsystems/replication]]` + `replication-overview` skill
  — the logical-decoding framework that owns the `OutputPluginCallbacks` table
  wal2json fills; the single most important cross-reference.
- `[[knowledge/architecture/wal]]` — wal2json re-materializes committed WAL as
  JSON; it is a *reader* of the durability stream other extensions (pg_squeeze,
  pglogical) also tap.
- `[[knowledge/ideologies/pglogical]]` — the other logical-replication entry in
  the corpus; pglogical ships a *named* output plugin too but is a full
  `CREATE EXTENSION` with workers and catalogs, the inverse of wal2json's
  "plugin-only, no extension" minimalism.
- `[[knowledge/idioms/memory-contexts]]` — the private AllocSet-under-
  TopMemoryContext + per-change reset pattern in a hot callback.
- `[[knowledge/data-structures/heap-tuple-layout]]` — the old/new `HeapTuple`
  pair and the `rd_replidindex` / `relreplident` replica-identity contract that
  gates UPDATE/DELETE emission.
- `.claude/skills/extension-development/SKILL.md` — the `.control` /
  `CREATE EXTENSION` checklist that pointedly does **not** apply to an
  output-plugin-only module; the contrast is the lesson.

## Sources

Fetched 2026-06-11 (branch `master`):

- `https://api.github.com/repos/eulerto/wal2json/git/trees/master?recursive=1`
  @ 2026-06-11 → HTTP 200 (tree listing; 68 blobs, confirmed no `.control`).
- `https://raw.githubusercontent.com/eulerto/wal2json/master/README.md`
  @ 2026-06-11 → HTTP 200 (511 lines; intro + format-version semantics read).
- `https://raw.githubusercontent.com/eulerto/wal2json/master/wal2json.c`
  @ 2026-06-11 → HTTP 200 (3373 lines; callback table, startup, change callback,
  version ladder, replica-identity gates deep-read; the per-format emit bodies
  and column-stringinfo helpers skimmed).

All structural cites (`_PG_output_plugin_init` table, empty `_PG_init`,
`output_type`, AllocSet creation + per-change reset, replica-identity WARNING
gates, the `#if PG_VERSION_NUM` ladder, `update_replication_progress` signature
churn) are `[verified-by-code]` against the fetched `wal2json.c`; the purpose,
v1/v2 wire-format framing, and CDC-consumer context are `[from-README]`
(`README.md:3-10`). The full v1/v2 tuple-serialization bodies
(`tuple_to_stringinfo`, `columns_to_stringinfo`, the SQL-API entry points) were
not line-by-line read.
