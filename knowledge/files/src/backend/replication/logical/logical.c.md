# `src/backend/replication/logical/logical.c`

- **Last verified commit:** `ef6a95c7c64`
- **Lines:** 2220
- **Source:** `source/src/backend/replication/logical/logical.c`

## Purpose

Coordinates logical decoding for any consumer. Provides
`LogicalDecodingContext` lifecycle and wraps every output-plugin callback
so internal modules (reorderbuffer, snapbuild) can call uniformly while
errors are routed through `output_plugin_error_callback`. The two
builtin consumers are walsender (`StartLogicalReplication`) and the SQL
SRF interface (`logicalfuncs.c`). [from-comment] (`logical.c:10-25`)

## Spine functions

- `CheckLogicalDecodingRequirements` (`:111`) — gates: must have a DB
  connection, `wal_level >= replica`, logical decoding currently enabled
  (see `logicalctl.c`).
- `CreateInitDecodingContext` — create a *new* slot's context (does WAL
  reservation, finds startpoint).
- `CreateDecodingContext` — recreate a context against an existing slot
  to resume.
- `DecodingContextFindStartpoint` — drive decoding through enough WAL to
  reach `SNAPBUILD_CONSISTENT`.
- `DecodingContextReady` — has snapbuild reached consistent?
- `FreeDecodingContext` — teardown.
- `LogicalIncreaseXminForSlot` / `LogicalIncreaseRestartDecodingForSlot` /
  `LogicalConfirmReceivedLocation` — slot-side advancement APIs.
- `OutputPluginPrepareWrite` / `OutputPluginWrite` /
  `OutputPluginUpdateProgress` — the three callbacks an output plugin
  uses to emit data. (`output_plugin.h:246-248`)

## Callback wrappers

Every callback (begin/commit/change/truncate/message/prepare/
commit_prepared/rollback_prepared/stream_*) has a `*_wrapper` that:

1. Sets up an errcontext via `LogicalErrorCallbackState` so an output
   plugin's `ereport(ERROR)` is decorated with "during commit_cb / lsn
   X/Y" info (`:50-58`).
2. Switches into the ctx's memory context.
3. Calls the actual plugin callback (`ctx->callbacks.commit_cb` etc.).

These are passed to `reorderbuffer` via `ctx->reorder->{begin,commit,…}`
function-pointer fields.

## Plugin loading

`LoadOutputPlugin` (`:104`) uses `load_external_function` to dlopen the
plugin shared library and locate `_PG_output_plugin_init`. The plugin
fills in the `OutputPluginCallbacks` vtable.

## Two-phase awareness

`twophase` (set when plugin provides all 2PC callbacks),
`twophase_opt_given` (set when client requested 2PC in
START_REPLICATION). Both must be true to actually do 2PC decoding.
(`logical.h:88-101`) [from-comment]
