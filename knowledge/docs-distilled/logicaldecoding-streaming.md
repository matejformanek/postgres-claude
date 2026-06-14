---
source_url: https://www.postgresql.org/docs/current/logicaldecoding-streaming.html
fetched_at: 2026-06-13T19:51:00Z
anchor_sha: e18b0cb
distilled_by: pg-docs-miner (cloud routine)
docs_version: current (PG18)
primary: true
---

# Streaming of Large In-Progress Transactions (internals ch. 49.9)

How logical decoding stops buffering an unbounded transaction in memory and
starts shipping it before COMMIT. The reorder-buffer spill/stream policy lives
here. Companion to the output-plugin chapter's `stream_*` callback set.

## Non-obvious claims

- **Trigger is memory, not size-of-one-txn:** when the *total* decoded change
  volume across all in-progress txns exceeds **`logical_decoding_work_mem`**, the
  decoder picks the **largest top-level transaction by memory footprint** and
  either streams it (if the plugin supports streaming) or spills it to disk. [from-docs]
- **Streaming does not eliminate spilling.** Even with streaming enabled, a txn
  can still spill to disk when the threshold trips mid-tuple — e.g. a TOAST insert
  arrived but the corresponding main-table insert hasn't been decoded yet, so no
  complete tuple is available to stream. [from-docs] Non-obvious gotcha for anyone
  reasoning about disk usage from `logical_decoding_work_mem` alone.
- **Required streaming callbacks (set):** `stream_start_cb`, `stream_stop_cb`,
  `stream_change_cb`, `stream_commit_cb`, `stream_abort_cb`. Optional:
  `stream_message_cb`, `stream_truncate_cb`. With 2PC also: `stream_prepare_cb`
  (+ `commit_prepared_cb` / `rollback_prepared_cb` at finalization). [from-docs]
- **Block structure:** changes arrive in `stream_start_cb` … `stream_stop_cb`
  *blocks*, possibly many blocks per transaction (interleaved with other txns'
  blocks), terminated by exactly one of `stream_commit_cb` / `stream_prepare_cb`
  / `stream_abort_cb`. [from-docs]
- **Consumer reassembly contract:** buffer changes within each start/stop block,
  flush/ack on `stream_stop_cb`, finalize on commit/prepare, and on
  `stream_abort_cb` **discard the buffered state for that txn**. Despite early
  shipping, **changes are still applied in commit order** — same consistency
  guarantee as non-streaming mode. The win is reduced apply lag on big txns. [from-docs]

## Links into corpus

- Per-file: [[knowledge/files/src/backend/replication/logical/reorderbuffer.c.md]]
  (the spill/stream decision + `logical_decoding_work_mem` accounting lives here),
  [[knowledge/files/src/backend/replication/logical/logical.c.md]]
  (stream callback dispatch),
  [[knowledge/files/src/backend/replication/logical/worker.c.md]]
  (apply-side handling of streamed txns),
  [[knowledge/files/src/backend/replication/logical/applyparallelworker.c.md]]
  (parallel apply of streamed txns).
- Siblings: `knowledge/docs-distilled/logicaldecoding-output-plugin.md`
  (callback ABI), `knowledge/docs-distilled/logicaldecoding-explanation.md`.
- Code anchor [unverified — not line-pinned this run]:
  `source/src/backend/replication/logical/reorderbuffer.c`.
