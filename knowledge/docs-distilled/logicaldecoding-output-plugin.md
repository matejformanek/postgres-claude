---
source_url: https://www.postgresql.org/docs/current/logicaldecoding-output-plugin.html
fetched_at: 2026-06-13T19:50:00Z
anchor_sha: e18b0cb
distilled_by: pg-docs-miner (cloud routine)
docs_version: current (PG18)
primary: true
---

# Logical Decoding Output Plugins (internals ch. 49.6)

The callback ABI an output plugin (pgoutput, wal2json, test_decoding, …) must
implement. This is the C contract behind every logical-replication consumer.
Companion to `custom-rmgr.md` (`rm_decode`) and the `pgoutput` per-file docs.

## Non-obvious claims

- **Entry point:** export `_PG_output_plugin_init(OutputPluginCallbacks *cb)`,
  called when the shared library is loaded; it populates the callback struct.
  Type: `LogicalOutputPluginInit`. [from-docs]
- **`OutputPluginCallbacks` callback set** — grouped by what enables them: [from-docs]
  - **Always required:** `begin_cb`, `change_cb`, `commit_cb`.
  - **Basic optional:** `startup_cb` (slot create / stream start),
    `shutdown_cb`, `truncate_cb` (TRUNCATE ignored if unset), `message_cb`
    (logical messages), `filter_by_origin_cb` (origin filtering).
  - **Two-phase commit (required as a set if 2PC):** `begin_prepare_cb`,
    `prepare_cb`, `commit_prepared_cb`, `rollback_prepared_cb`; optional
    `filter_prepare_cb` (decode at PREPARE vs defer to COMMIT PREPARED).
  - **Streaming (required as a set if streaming):** `stream_start_cb`,
    `stream_stop_cb`, `stream_abort_cb`, `stream_commit_cb`, `stream_change_cb`;
    optional `stream_message_cb`, `stream_truncate_cb`.
  - **Streaming + 2PC together:** also need `stream_prepare_cb`.
- **`OutputPluginOptions`** set in `startup_cb`: `output_type` is
  `OUTPUT_PLUGIN_TEXTUAL_OUTPUT` (must be server-encoding-clean, storable in
  `text`) or `OUTPUT_PLUGIN_BINARY_OUTPUT` (arbitrary bytes); `receive_rewrites`
  asks for callbacks on heap-rewrite changes during certain DDL (needed by
  DDL-replication plugins). [from-docs]
- **Output-writing idiom** inside a callback:
  `OutputPluginPrepareWrite(ctx, last_write)` → append to `ctx->out`
  (a `StringInfo`) → `OutputPluginWrite(ctx, last_write)`. The `last_write`
  flag marks the callback's final write. [from-docs]
- **🔑 Catalog-access restriction.** A plugin may read only `pg_catalog` (plus
  user tables flagged `user_catalog_table = true`), and **only via the
  `systable_*` scan APIs — never `heap_*` directly**, because the decoder runs
  with a historic snapshot that the generic heap scan path doesn't honor. [from-docs]
- **No XID assignment allowed** in callbacks: no writes, no DDL, no
  `pg_current_xact_id()` — anything that would allocate a transaction id is
  forbidden. [from-docs]
- **Decode semantics the plugin can rely on:** concurrent txns delivered in
  **commit order**; aborted txns never delivered; successful savepoints folded
  into their containing txn; only changes already **flushed to disk** are
  decoded (so `synchronous_commit = off` can delay a COMMIT becoming visible to
  the decoder). [from-docs]
- **`filter_by_origin_cb`** is the cheap, early loop-breaker for
  bidirectional/cascading setups — filtering by origin here beats inspecting
  origin fields per-change later. [from-docs]

## Links into corpus

- Per-file: [[knowledge/files/src/backend/replication/logical/logical.c.md]]
  (callback dispatch / `LogicalDecodingContext`),
  [[knowledge/files/src/backend/replication/logical/decode.c.md]]
  (WAL→change decoding that feeds these callbacks),
  [[knowledge/files/src/backend/replication/logical/reorderbuffer.c.md]]
  (commit-order reassembly + streaming spill),
  [[knowledge/files/src/backend/replication/pgoutput]] (the in-core plugin),
  [[knowledge/files/src/backend/replication/logical/message.c.md]] (`message_cb` source).
- Idiom: [[knowledge/idioms/fmgr.md]] (the function-manager v1 calling style
  these callbacks share), [[knowledge/idioms/catalog-conventions.md]]
  (`user_catalog_table`, `systable_*`).
- Siblings: `knowledge/docs-distilled/logicaldecoding-explanation.md`,
  `knowledge/docs-distilled/logicaldecoding-streaming.md`,
  `knowledge/docs-distilled/custom-rmgr.md` (`rm_decode` is the producer side).
- Code anchor [unverified — not line-pinned this run]:
  `source/src/include/replication/output_plugin.h` (`OutputPluginCallbacks`,
  `OutputPluginOptions`).
