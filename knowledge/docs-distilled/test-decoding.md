---
source_url: https://www.postgresql.org/docs/current/test-decoding.html
fetched_at: 2026-06-28T00:00:00Z
anchor_sha: 4abf411e2328
distilled_by: pg-docs-miner (cloud routine)
docs_version: current (PG18)
primary: false
---

# Docs distilled — test_decoding (the logical-decoding output-plugin example)

`contrib/test_decoding` is the reference output plugin for the logical-decoding
API: it wires up **every** `OutputPluginCallbacks` member and emits a
human-readable text rendering of each change. It is not for production — it
backs the regression tests and lets you inspect decoded WAL via SQL. Read it as
the template for any custom output plugin. `[from-docs]`

## The full callback set (verified against source)

- `_PG_output_plugin_init(OutputPluginCallbacks *cb)` fills the struct at
  `source/contrib/test_decoding/test_decoding.c:131`. The wiring (`:133-151`)
  covers the complete surface: `startup_cb`, `begin_cb`, `change_cb`,
  `truncate_cb`, `commit_cb`, `filter_by_origin_cb`, `shutdown_cb`, `message_cb`,
  `filter_prepare_cb`, the 2PC callbacks (`begin_prepare_cb`, `prepare_cb`,
  `commit_prepared_cb`, `rollback_prepared_cb`), and the streaming (in-progress
  xact) callbacks (`stream_start_cb`, `stream_stop_cb`, `stream_abort_cb`,
  `stream_prepare_cb`, `stream_commit_cb`, `stream_change_cb`, plus
  stream_message/stream_truncate). `[verified-by-code]` This is the authoritative
  enumeration of what an output plugin *may* implement.

## How to drive it

- Create a slot bound to the plugin:
  `pg_create_logical_replication_slot('slot', 'test_decoding')`. `[from-docs]`
- Consume changes with `pg_logical_slot_get_changes()` (advances the slot) or
  `pg_logical_slot_peek_changes()` (non-consuming). Output is three columns:
  `lsn`, `xid`, `data`. `[from-docs]`
- Text rendering: `BEGIN` / `table public.data: INSERT: id[int4]:2 data[text]:'arg'`
  / `COMMIT`. Streaming mode emits `opening a streamed block for transaction TXN
  <xid>` … `closing a streamed block …`. `[from-docs]`

## Output options (passed to the slot-read functions)

- `include-xids`, `include-timestamp`, `skip-empty-xacts`, `include-rewrites`,
  `stream-changes` (enable in-progress streaming via the `stream_*` callbacks),
  among others. These options are parsed in `pg_decode_startup`. `[from-docs]`

## Links into corpus

- `[[knowledge/docs-distilled/logicaldecoding-output-plugin.md]]` — the callback
  contract test_decoding instantiates (the prose spec for each `*_cb`).
- `[[knowledge/docs-distilled/logicaldecoding-streaming.md]]` — the `stream_*`
  callback family for uncommitted xacts.
- `[[knowledge/docs-distilled/logicaldecoding-sql.md]]` — the
  `pg_logical_slot_get_changes`/`peek_changes` SQL interface used here.
- `[[knowledge/docs-distilled/logicaldecoding-example.md]]` — end-to-end walkthrough.
- Skills: `wal-and-xlog`, `replication-overview`.
