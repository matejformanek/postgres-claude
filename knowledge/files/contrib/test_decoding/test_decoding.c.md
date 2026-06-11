# `contrib/test_decoding/test_decoding.c`

- **Last verified commit:** `e18b0cb7344`
- **Lines:** ~1004
- **Source:** `source/contrib/test_decoding/test_decoding.c`

The **reference / example output plugin** for PostgreSQL logical
decoding. Implements the full `OutputPluginCallbacks` surface
(startup, begin/commit, change, truncate, message, filter, prepare/2PC,
streaming) and renders each callback as human-readable text such as
`table public.foo: INSERT: id[integer]:1 …`. Backs both the
`test_decoding` regression suite (which exercises decoding behaviour
end-to-end) and the docs' examples of how to write an output plugin.
[verified-by-code] [from-comment]

## API / entry points

- `_PG_init` (test_decoding.c:123-127) — no-op; the comment notes
  other plugins can do init here. The plugin shape is determined
  by `_PG_output_plugin_init`. [verified-by-code]
- `_PG_output_plugin_init(OutputPluginCallbacks *cb)`
  (test_decoding.c:130-154) — wires every supported callback. Demos
  the full callback surface: `startup_cb`, `begin_cb`, `change_cb`,
  `truncate_cb`, `commit_cb`, `filter_by_origin_cb`, `shutdown_cb`,
  `message_cb`, two-phase callbacks (`filter_prepare_cb`,
  `begin_prepare_cb`, `prepare_cb`, `commit_prepared_cb`,
  `rollback_prepared_cb`), and the streaming callbacks
  (`stream_*`). [verified-by-code]
- `pg_decode_startup` (test_decoding.c:158-276) — parses the
  output_plugin_options list. Recognises:
  - `include-xids` (default true)
  - `include-timestamp` (default false)
  - `force-binary` (selects `OUTPUT_PLUGIN_BINARY_OUTPUT` if true)
  - `skip-empty-xacts` (default false)
  - `only-local` (default false)
  - `include-rewrites` (mapped to `opt->receive_rewrites`)
  - `stream-changes` (gates streaming on a per-subscription basis
    via `ctx->streaming &= enable_streaming`).
  Unknown options error out. [verified-by-code]
- `pg_decode_shutdown` (test_decoding.c:280-286) — frees the
  TestDecodingData->context via `MemoryContextDelete`.
  [verified-by-code]
- `pg_decode_begin_txn` / `pg_decode_commit_txn` (test_decoding.c:
  290-346) — emit `BEGIN <xid>` / `COMMIT <xid>` lines, optionally
  defer the BEGIN until first change when `skip-empty-xacts` is set.
  [verified-by-code]
- `pg_decode_change` (test_decoding.c:602-687) — the meat. Switches
  on `change->action` (`INSERT` / `UPDATE` / `DELETE`), renders
  `quote_qualified_identifier(nsname, relname)` followed by the
  tuple_to_stringinfo output. Resets `data->context` after each
  change to bound memory. [verified-by-code]
- `pg_decode_truncate` (test_decoding.c:689-742) — same but for
  TRUNCATE; lists all relations and the truncate flags
  (`restart_seqs`, `cascade`).
- `pg_decode_message` (test_decoding.c:744-766) — renders logical
  messages (pg_logical_emit_message). Prints the raw bytes.
- 2PC callbacks (test_decoding.c:348-460) — `begin_prepare`,
  `prepare`, `commit_prepared`, `rollback_prepared` emit lines like
  `PREPARE TRANSACTION 'gid', txid 123`. `filter_prepare` returns
  true for any GID containing `_nodecode` — the documented
  filtering example. [verified-by-code] [from-comment]
- Streaming callbacks (test_decoding.c:768-1004) — `stream_start`,
  `stream_stop`, `stream_abort`, `stream_prepare`, `stream_commit`,
  `stream_change`, `stream_message`, `stream_truncate`. In streaming
  mode the per-row tuple data is **deliberately not displayed** —
  comment at 911-915 explains: changes may abort later, users
  shouldn't see uncommitted data, so only the bookkeeping is emitted.
  [verified-by-code] [from-comment]
- `print_literal` / `tuple_to_stringinfo` (test_decoding.c:481-597)
  — type-aware rendering. Numeric / bool / bit types unquoted /
  reformatted; everything else single-quoted with SQL escaping.
  TOAST handling: external-on-disk TOASTed datums in
  unchanged-key positions render as `unchanged-toast-datum`
  (line 585). [verified-by-code]

## Notable invariants / details

- Memory discipline: `data->context` is a child of `ctx->context`
  (test_decoding.c:167-169) used as scratch in `pg_decode_change`
  and `pg_decode_truncate`. Reset after each change keeps usage
  bounded. Per-txn allocations (TestDecodingTxnData) live in
  `ctx->context` and are pfree'd on commit/abort/stream_commit
  (lines 329, 891). [verified-by-code]
- Streaming is **off by default** even if the subscriber asked for
  it; `ctx->streaming &= enable_streaming` (test_decoding.c:275)
  means the plugin must opt in explicitly with
  `stream-changes=on`. [verified-by-code]
- Sub-txn abort handling: `pg_decode_stream_abort` chases
  `rbtxn_get_toptxn(txn)` so per-subtxn aborts can read the toptxn's
  output_plugin_private (test_decoding.c:833-841). The pfree of
  txndata only happens when `rbtxn_is_toptxn(txn)`. [verified-by-code]
  [from-comment]
- DELETE on a table with no REPLICA IDENTITY emits
  `(no-tuple-data)` (test_decoding.c:671). UPDATE with old_tuple
  NULL means PK didn't change; with old_tuple non-NULL the old PK
  is rendered as `old-key:`. [verified-by-code] [from-comment]
- `filter_by_origin_cb` (test_decoding.c:462-471) implements the
  `only-local` knob — returning true skips changes originating from
  any remote replication origin. [verified-by-code]
- Output type can be **binary** (force-binary=on), which then
  emits the same text into ctx->out — the "binary" flag really just
  toggles the wire type indicator. Test cases use it to verify the
  binary path of the streaming protocol. [verified-by-code]
- This plugin has no GUC of its own; everything is per-slot via
  output_plugin_options. The package's GUC `wal_level = logical`
  is enforced by core, not here. [verified-by-code]

## Potential issues

- test_decoding.c:166. `palloc0_object(TestDecodingData)` lives in
  the wrong context if `ctx->context` is short-lived — but
  `ctx->context` is the per-decoding-session context (logical.c
  lifetime), so this is fine. Worth a comment for new plugin
  authors copying this code. [ISSUE-undocumented-invariant: ctx
  ownership not obvious to copy-paste authors (nit)]
- test_decoding.c:518. `SQL_STR_DOUBLE(ch, false)` is the standard-
  conforming-strings macro; with `false` the macro doesn't account
  for backslash escaping in non-standard mode. Output may not round-
  trip cleanly through a `standard_conforming_strings = off`
  subscriber — but in 2026 nobody runs with that. [ISSUE-style:
  legacy mode unsupported (nit)]
- test_decoding.c:680. The default branch is `Assert(false)`; in a
  non-assert build an unknown `change->action` silently emits
  whatever ctx->out already accumulated, producing partial output.
  Logical-decoding adds new change types over releases (e.g.,
  REORDER_BUFFER_CHANGE_INTERNAL_*). [ISSUE-correctness: partial
  output on unknown action in release builds (nit)]
- test_decoding.c:765. `appendBinaryStringInfo(ctx->out, message,
  sz)` for non-transactional messages dumps raw bytes including
  NULs into the textual output. The test framework expects this
  (binary roundtrip), but consumers that treat ctx->out as a
  C-string mid-message will truncate. The test's pg_recvlogical
  uses length-prefixed framing, so this is fine in practice but
  surprising. [ISSUE-undocumented-invariant: text output may
  contain embedded NULs (nit)]
- test_decoding.c:184-273. The option parser uses repeated
  `strcmp(elem->defname, …)` — adding a new option requires
  touching this long if-else chain. Compare auto_explain's
  approach. [ISSUE-style: long if-else option parser (nit)]
- test_decoding.c:329-330. `pfree(txndata)` in `pg_decode_commit_txn`
  but no analogous pfree in commit-prepared / rollback-prepared
  branches (lines 400-443). The txn-data for prepared txns is
  allocated in `pg_decode_begin_prepare_txn` (line 353) and never
  freed; relies on context reset at txn end. Mostly cosmetic since
  `ctx->context` is reset, but inconsistent with the commit branch.
  [ISSUE-leak: 2PC txndata not pfree'd; relies on context cleanup
  (nit)]
- test_decoding.c:759. `txndata->xact_wrote_changes = true` for
  transactional messages — but the prior `txndata` deref at line
  755 happens BEFORE the `if (transactional)` check is processed,
  so a non-transactional message with `txn == NULL` would crash. In
  practice the decoder always provides txn for transactional=true
  cases, so the conditional at line 752 guards it. Fragile but
  correct. [ISSUE-correctness: subtle null-deref-by-ordering (nit)]
- test_decoding.c:171. `MemoryContextAllocZero(ctx->context, …)` for
  TestDecodingTxnData in `pg_decode_begin_prepare_txn` mirrors
  begin_txn but begin_prepare can be called without a matching
  prepare (if filter_prepare returns true mid-decode). In that path
  the txndata leaks until ctx context reset. [ISSUE-leak: filter-
  prepare race window (maybe)]

## Cross-references

- `knowledge/issues/test_decoding.md` — per-extension issue register
  (create from template if absent).
- `source/src/backend/replication/logical/logical.c` — the
  LogicalDecodingContext / OutputPluginCallbacks framework this
  plugin implements.
- `source/src/include/replication/output_plugin.h` — callback
  signatures.
- `knowledge/subsystems/replication-logical.md` (if present) for
  the broader decoding pipeline.
- Companion tests: `contrib/test_decoding/sql/*.sql` +
  `contrib/test_decoding/specs/*.spec`.
