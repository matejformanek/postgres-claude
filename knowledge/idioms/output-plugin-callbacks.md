# Output plugin callbacks — the logical-decoding consumer

An **output plugin** is a shared library (`.so`) that registers
a set of callbacks via `_PG_output_plugin_init`. The logical
decoder invokes those callbacks for every decoded transaction
event: begin → change (× N) → commit. Standard plugins include
`pgoutput` (built-in, used by logical replication) and
`wal2json` (community, JSON output). Writing a new output
plugin = implementing the callbacks and producing the desired
on-wire format.

Anchors:
- `source/src/include/replication/output_plugin.h:216-243` —
  OutputPluginCallbacks struct [verified-by-code]
- `source/src/include/replication/output_plugin.h:36-38` —
  LogicalOutputPluginInit + _PG_output_plugin_init
  [verified-by-code]
- `source/src/backend/replication/logical/logical.c` —
  callback invocation
- `knowledge/idioms/logical-decoding-snapshot.md` — companion
- `knowledge/idioms/replication-slot-advance.md` — companion
- `.claude/skills/replication-overview/SKILL.md` — companion

## The init entry point

[verified-by-code `output_plugin.h:36-38`]

```c
typedef void (*LogicalOutputPluginInit) (struct OutputPluginCallbacks *cb);

extern PGDLLEXPORT void
_PG_output_plugin_init(struct OutputPluginCallbacks *cb);
```

Every output plugin .so must export `_PG_output_plugin_init`.
The function populates the `cb` struct with function pointers
for each callback the plugin wants to handle.

Missing callbacks → that event is not delivered to the plugin
(it's still decoded, just dropped).

## The 8 base callbacks

[verified-by-code `output_plugin.h:218-225`]

```c
typedef struct OutputPluginCallbacks
{
    LogicalDecodeStartupCB      startup_cb;
    LogicalDecodeBeginCB        begin_cb;
    LogicalDecodeChangeCB       change_cb;
    LogicalDecodeTruncateCB     truncate_cb;
    LogicalDecodeCommitCB       commit_cb;
    LogicalDecodeMessageCB      message_cb;
    LogicalDecodeFilterByOriginCB filter_by_origin_cb;
    LogicalDecodeShutdownCB     shutdown_cb;
    ...
};
```

The most important:
- **`startup_cb(ctx, opt, is_init)`** — set output format (text
  vs binary), parse plugin options.
- **`begin_cb(ctx, txn)`** — start of decoded transaction.
- **`change_cb(ctx, txn, relation, change)`** — one
  INSERT/UPDATE/DELETE event.
- **`commit_cb(ctx, txn, commit_lsn)`** — end of transaction.
- **`shutdown_cb(ctx)`** — cleanup.

`truncate_cb` was added for TRUNCATE (no per-row events;
truncates a whole relation). `message_cb` for `pg_logical_emit_message`
client messages. `filter_by_origin_cb` to skip xacts originated
from a specific replication origin (loop prevention in
bidirectional logical replication).

## 2PC callbacks

[verified-by-code `output_plugin.h:228-233`]

```c
LogicalDecodeFilterPrepareCB   filter_prepare_cb;
LogicalDecodeBeginPrepareCB    begin_prepare_cb;
LogicalDecodePrepareCB         prepare_cb;
LogicalDecodeCommitPreparedCB  commit_prepared_cb;
LogicalDecodeRollbackPreparedCB rollback_prepared_cb;
```

For decoding PREPARE TRANSACTION / COMMIT PREPARED across the
WAL stream. Plugins can opt in by setting these; PG13+ supports
2PC-aware logical decoding.

`filter_prepare_cb` decides per-xact whether to decode at
prepare time vs only commit-time.

## Streaming callbacks

[verified-by-code `output_plugin.h:236-244`]

```c
LogicalDecodeStreamStartCB     stream_start_cb;
LogicalDecodeStreamStopCB      stream_stop_cb;
LogicalDecodeStreamAbortCB     stream_abort_cb;
LogicalDecodeStreamPrepareCB   stream_prepare_cb;
LogicalDecodeStreamCommitCB    stream_commit_cb;
LogicalDecodeStreamChangeCB    stream_change_cb;
LogicalDecodeStreamMessageCB   stream_message_cb;
LogicalDecodeStreamTruncateCB  stream_truncate_cb;
```

For **in-progress (streaming) transaction decoding** — large
transactions can spill the ReorderBuffer to disk; the streaming
flavor delivers changes mid-transaction so the subscriber can
start applying before commit. Requires PG14+ + the plugin to
declare `output_plugin_options.streaming = true` at startup.

## The decoded change struct

Passed to `change_cb`:

```c
typedef struct ReorderBufferChange
{
    XLogRecPtr     lsn;
    ReorderBufferChangeType action;  /* INSERT/UPDATE/DELETE/TRUNCATE */
    Oid            origin_id;
    union {
        struct {
            HeapTuple newtuple;
            HeapTuple oldtuple;
        } tp;
        /* ... TRUNCATE ... */
    } data;
} ReorderBufferChange;
```

The plugin walks the `newtuple` / `oldtuple`, uses the
historic catalog snapshot to look up column names + types, and
emits the desired output.

## OutputPluginPrepareWrite / OutputPluginWrite

[verified-by-code `output_plugin.h:246-248`]

```c
void OutputPluginPrepareWrite(LogicalDecodingContext *ctx, bool last_write);
void OutputPluginWrite(LogicalDecodingContext *ctx, bool last_write);
void OutputPluginUpdateProgress(LogicalDecodingContext *ctx, bool skipped_xact);
```

The plugin's I/O cycle:
1. Call `OutputPluginPrepareWrite` to reserve a write buffer.
2. Append to `ctx->out` (the StringInfo) — JSON / protobuf /
   text.
3. Call `OutputPluginWrite` to flush.

`last_write = true` on the final write of a logical message
to enable optimizations.

`UpdateProgress` for slot-advance signaling when emitting an
empty-effect transaction.

## pgoutput — the built-in plugin

[from `src/backend/replication/pgoutput/pgoutput.c`]

`pgoutput` produces the PG-native logical replication protocol
(used by SUBSCRIPTION). Encodes changes in a binary wire
format including:
- Message type byte (B / I / U / D / C / T / R / Y / O / M).
- Relation OID + tuple data.
- Optional column types (for first time / type changes).

The subscriber's apply worker parses pgoutput format directly.

## Writing a custom output plugin

Skeleton:

```c
#include "postgres.h"
#include "replication/output_plugin.h"

PG_MODULE_MAGIC;

static void my_startup(LogicalDecodingContext *ctx, OutputPluginOptions *opt, bool is_init) {
    opt->output_type = OUTPUT_PLUGIN_TEXTUAL_OUTPUT;
}
static void my_begin(LogicalDecodingContext *ctx, ReorderBufferTXN *txn) {
    OutputPluginPrepareWrite(ctx, false);
    appendStringInfoString(ctx->out, "BEGIN\n");
    OutputPluginWrite(ctx, false);
}
/* ... change_cb, commit_cb, shutdown_cb ... */

void _PG_output_plugin_init(OutputPluginCallbacks *cb) {
    cb->startup_cb  = my_startup;
    cb->begin_cb    = my_begin;
    cb->change_cb   = my_change;
    cb->commit_cb   = my_commit;
    cb->shutdown_cb = my_shutdown;
}
```

Compile as a shared library; `CREATE PUBLICATION` then use
`CREATE_REPLICATION_SLOT slot LOGICAL my_plugin`.

## Common review-time concerns

- **Missing callbacks** = silent event drop; plugin author
  must enumerate everything they care about.
- **Streaming requires opt-in** at startup + new callbacks.
- **2PC support requires opt-in**; older plugins still work.
- **Historic catalog access** — only SearchSysCache* etc.; no
  writes.
- **OutputPluginPrepareWrite/Write pairing** is mandatory.
- **plugin_options parse fail in startup_cb** = startup
  errors; client gets the error.

## Invariants

- **[INV-1]** `_PG_output_plugin_init` is the discovery
  entry; plugin populates the callbacks struct.
- **[INV-2]** Missing callbacks → event dropped.
- **[INV-3]** OutputPluginPrepareWrite → write to ctx->out →
  OutputPluginWrite pairing.
- **[INV-4]** Streaming + 2PC are opt-in via additional
  callbacks.
- **[INV-5]** Catalog access read-only; historic snapshot in
  effect.

## Useful greps

- The callbacks struct + init:
  `grep -n 'OutputPluginCallbacks\|_PG_output_plugin_init' source/src/include/replication/output_plugin.h | head -10`
- pgoutput implementation:
  `grep -n 'pgoutput_change\|pgoutput_begin' source/src/backend/replication/pgoutput/pgoutput.c | head -10`
- Invocation site:
  `grep -RIn 'startup_cb\|change_cb\|commit_cb' source/src/backend/replication/logical/logical.c | head -15`



## Call sites
<!-- callsites:auto -->

*Auto-extracted from `source/<path>:<line>` cites in this doc's prose (bullets and free text).*
*Refresh via `scripts/populate-idiom-callsites.py` — edits inside this block are overwritten.*

| File | Line | Role |
|---|---:|---|
| [`src/backend/replication/logical/logical.c`](../files/src/backend/replication/logical/logical.c.md) | — | callback invocation |
| [`src/backend/replication/pgoutput/pgoutput.c`](../files/src/backend/replication/pgoutput/pgoutput.c.md) | — | reference plugin |
| [`src/include/replication/output_plugin.h`](../files/src/include/replication/output_plugin.h.md) | 36 | LogicalOutputPluginInit + _PG_output_plugin_init |
| [`src/include/replication/output_plugin.h`](../files/src/include/replication/output_plugin.h.md) | 216 | OutputPluginCallbacks struct |

<!-- /callsites:auto -->

## Cross-references

- `knowledge/idioms/logical-decoding-snapshot.md` — supplies
  the historic catalog context.
- `knowledge/idioms/replication-slot-advance.md` — slot
  state drives slot-advance.
- `knowledge/idioms/walsender-state-machine.md` — walsender
  runs the decoder + plugin.
- `knowledge/idioms/replication-origin-tracking.md` —
  filter_by_origin_cb + origin id.
- `knowledge/idioms/prepare-transaction-2pc.md` — 2PC
  callbacks parallel.
- `knowledge/subsystems/replication.md` — replication
  overview.
- `.claude/skills/replication-overview/SKILL.md` — companion.
- `.claude/skills/extension-development/SKILL.md` — plugin
  packaging.
- `source/src/include/replication/output_plugin.h:216` —
  callbacks struct.
- `source/src/backend/replication/pgoutput/pgoutput.c` —
  reference plugin.
