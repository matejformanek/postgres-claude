# src/include/replication/output_plugin.h

## Purpose

**THE Logical Decoding Output Plugin Interface.** Defines the callback
table (`OutputPluginCallbacks`) that every logical-decoding output
plugin must populate, plus the `OutputPluginOptions` returned from the
startup callback, plus the well-known C symbol name
`_PG_output_plugin_init` that the backend uses to locate a plugin's
init function via `load_external_function`. Source pin
`4b0bf0788b066a4ca1d4f959566678e44ec93422`.

## Role in PG

This is the contract between core's logical decoding (the slot machine
+ snapbuild + reorderbuffer) and a loadable shared library that
translates decoded changes into a wire format. `pgoutput` (built into
the server), `test_decoding` (contrib), `wal2json` (third-party),
Debezium's decoderbufs, etc. all implement this interface. When a
walsender starts streaming a logical slot, it calls
`LoadOutputPlugin(callbacks, slot->data.plugin)`
(`backend/replication/logical/logical.c:726`) which does
`load_external_function(plugin, "_PG_output_plugin_init", false,
NULL)`. The `plugin` string is the NameData stored in the slot's
persistent data, set at slot creation time from the SQL caller's
second argument to `pg_create_logical_replication_slot(name, plugin)`.

## Key types/struct fields

- `OutputPluginOutputType` (lines 17-21) — `OUTPUT_PLUGIN_BINARY_OUTPUT`
  vs `OUTPUT_PLUGIN_TEXTUAL_OUTPUT`. The plugin chooses in its startup
  callback; affects whether libpq sends rows as text or binary.
  [verified-by-code]
- `OutputPluginOptions` (lines 26-30) — `output_type`, `receive_rewrites`
  (whether the plugin wants to see HEAP_REWRITE — i.e. cluster / VACUUM
  FULL — records). [verified-by-code]
- `LogicalOutputPluginInit` typedef (line 36) and exported
  `_PG_output_plugin_init` declaration (line 38) — the magic symbol
  name `load_external_function` looks up. Comment line 32-35: "Type of
  the shared library symbol _PG_output_plugin_init that is looked up
  when loading an output plugin shared library." [from-comment]
- `LogicalDecodeStartupCB` (line 47) — called once per slot start;
  receives `OutputPluginOptions *` for the plugin to fill in, plus
  `is_init` (true on slot creation). [verified-by-code]
- Standard txn callbacks (lines 55-102):
  `LogicalDecodeBeginCB`, `LogicalDecodeChangeCB` (per-row),
  `LogicalDecodeTruncateCB`, `LogicalDecodeCommitCB`,
  `LogicalDecodeMessageCB` (generic `pg_logical_emit_message` payload),
  `LogicalDecodeFilterByOriginCB` (the origin loop-avoidance gate),
  `LogicalDecodeShutdownCB`. [verified-by-code]
- Two-phase callbacks (lines 104-141): `filter_prepare_cb`,
  `begin_prepare_cb`, `prepare_cb`, `commit_prepared_cb`,
  `rollback_prepared_cb`. [verified-by-code]
- Streaming-of-in-progress-xact callbacks (lines 143-211):
  `stream_start_cb`, `stream_stop_cb`, `stream_abort_cb`,
  `stream_prepare_cb`, `stream_commit_cb`, `stream_change_cb`,
  `stream_message_cb`, `stream_truncate_cb`. [verified-by-code]
- `OutputPluginCallbacks` (lines 216-243) — the struct the plugin
  populates inside `_PG_output_plugin_init`. Core checks that at minimum
  `begin_cb`, `change_cb`, `commit_cb` are non-NULL
  (`logical.c:739-744`). [verified-by-code]
- I/O helpers (lines 246-248): `OutputPluginPrepareWrite`,
  `OutputPluginWrite`, `OutputPluginUpdateProgress`. The plugin must
  call PrepareWrite → emit bytes into `ctx->out` → Write to flush a
  message to the walsender's stream. [verified-by-code]

## Phase D notes (THE A6 ECHO)

**No whitelist. No validation. No registry.** The plugin name is
fed directly to `load_external_function` which calls
`load_external_function` → `find_in_dynamic_libpath` →
`internal_load_library` → `dlopen` on the `<plugin>.so` path resolved
against `dynamic_library_path` (default `$libdir`). Confirmed at
`source/src/backend/replication/logical/logical.c:730-731`:

```
plugin_init = (LogicalOutputPluginInit)
    load_external_function(plugin, "_PG_output_plugin_init", false, NULL);
```

The only constraint is that the resolved `.so` must export the C symbol
`_PG_output_plugin_init` (lines 38, 730-734) — every contrib module that
uses `PG_MODULE_MAGIC` exports `_PG_init` but NOT
`_PG_output_plugin_init`, so an attacker pointing at e.g. `pg_stat_statements`
gets `elog(ERROR, "output plugins have to declare the
_PG_output_plugin_init symbol")` rather than RCE — but ANY `.so`
anywhere in `dynamic_library_path` that DOES export that symbol will be
dlopen'd and have its `_PG_init` side effects run before the ERROR is
raised. The slot is created with the plugin name persisted even if the
subsequent load fails, so the bad name lives in `pg_replication_slots`
until dropped.

**Pg_upgrade carry-over (A6 finding).** Pg_upgrade reads the old
cluster's `pg_replication_slots.plugin` and calls
`pg_create_logical_replication_slot(name, plugin)` on the new cluster
with the verbatim string. There is no check that the named plugin
exists on the new cluster's filesystem at upgrade time; the failure
shows up only when a subscriber later tries to start decoding.

**Permission gate.** `CheckSlotPermissions` requires
`has_rolreplication(GetUserId())` — REPLICATION role attribute. Any
role with REPLICATION can call `pg_create_logical_replication_slot('x',
'arbitrary_string')` and trigger a dlopen of any `.so` in the dynamic
library path. The REPLICATION role attribute is documented for
streaming replication; its bundling with "trigger dlopen of arbitrary
plugin" is less prominently surfaced.

**Plugin callbacks run in the walsender backend.** The startup_cb /
change_cb / commit_cb all execute in the walsender process, with full
backend privileges (effectively a superuser-equivalent process for
filesystem and memory access). A buggy or malicious plugin owns the
walsender.

## Potential issues

- [ISSUE-trust-boundary: any role with REPLICATION can name ANY string
  as the plugin; `load_external_function` will `dlopen` any matching
  `.so` in `dynamic_library_path`. No whitelist. The required symbol
  `_PG_output_plugin_init` filters out most contrib libs, but
  `_PG_init` runs first so any `.so` side-effects fire even on the
  "wrong symbol" error path (sev=likely)]
- [ISSUE-wire-protocol: plugin name persisted in
  `pg_replication_slots.plugin` is carried verbatim by pg_upgrade to
  the new cluster (A6 finding); no validation that the named plugin
  exists at upgrade time — silent drift between clusters (sev=likely)]
- [ISSUE-undocumented-invariant: header doesn't say which callbacks
  are required vs optional; core's check (begin, change, commit
  required) lives only in `logical.c:739-744` (sev=unlikely)]
- [ISSUE-trust-boundary: plugin callbacks execute in the walsender
  process with backend privileges; a malicious or buggy `.so` can
  read arbitrary tables, files, and shared memory (sev=likely)]
- [ISSUE-state-transition: slot creation persists the plugin name
  BEFORE successful load — a failed `LoadOutputPlugin` leaves the
  slot in `pg_replication_slots` with the bad name, retaining WAL
  until manually dropped (sev=maybe)]
- [ISSUE-info-disclosure: `OutputPluginOptions.receive_rewrites` lets
  a plugin demand HEAP_REWRITE (cluster/VACUUM FULL) records — full
  table snapshots visible to the plugin (sev=unlikely)]

## Synthesized by
<!-- backlinks:auto -->
- [architecture/replication.md](../../../../architecture/replication.md)

## Appears in scenarios

<!-- scenarios:auto:begin -->

- [Scenario — Add a new replication / logical-decoding message](../../../../scenarios/add-new-replication-message.md)

<!-- scenarios:auto:end -->

## Cross-references

<!-- issues:auto:begin -->
- [Issue register — `include-replication`](../../../../issues/include-replication.md)
<!-- issues:auto:end -->
