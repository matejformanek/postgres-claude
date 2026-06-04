# src/include/replication/logical.h

## Purpose

Coordinates logical decoding on the **publisher** side: defines
`LogicalDecodingContext`, the central object passed to every output-plugin
callback, plus the entry points used by walsender / SQL-decoding functions
(`pg_logical_slot_get_changes`, etc.) to create, advance, and tear down a
decoding session over a logical replication slot.

## Role in PG

- Sits **above** `reorderbuffer` (transaction reassembly), `snapbuild`
  (catalog-consistent snapshot), and `slot.h` (durable LSN bookkeeping).
- Sits **below** `output_plugin.h` (callback shapes filled in by the
  plugin: pgoutput, test_decoding, wal2json, …).
- Used by walsender (`CreateReplicationSlot`, `StartLogicalReplication`)
  and the SQL `pg_logical_*` family.
- The macro `LogicalDecodingLogLevel()` (`logical.h:175-176`) downgrades
  startup chatter from `LOG` to `DEBUG1` for foreground SQL callers so
  that peek/get functions don't spam `client_min_messages=NOTICE`
  sessions. `[from-comment]`

## Key types/struct fields

`LogicalDecodingContext` (`logical.h:33-115`) — heap-allocated in `context`
(its own MemoryContext, line 36):

- `slot` (line 39) — the `ReplicationSlot *` whose `restart_lsn`,
  `confirmed_flush`, and `effective_xmin` we advance.
- `reader`, `reorder`, `snapshot_builder` (lines 42-44) — the three
  in-memory stacks the decoder owns.
- `fast_forward` (lines 47-51) — when true, no output plugin is loaded;
  the context just walks WAL to advance the slot. Most fields below are
  unused in fast-forward mode.
- `callbacks`, `options` (lines 53-54) — frozen at
  `CreateInitDecodingContext` time from the plugin's `_PG_output_plugin_init`.
- `prepare_write`, `write`, `update_progress` (lines 64-66) — caller
  (walsender vs SQL) supplies these to drain `out`.
- `out` (line 71) — the per-callback `StringInfo` the plugin appends bytes
  to; flushed via `write`.
- `streaming` / `twophase` / `twophase_opt_given` (lines 86-101) —
  capability flags. The `_opt_given` split distinguishes "plugin
  registered all twophase callbacks" from "plugin asked for twophase via
  START_REPLICATION option". `[from-comment]`
- `accept_writes`, `prepared_write`, `write_location`, `write_xid`,
  `end_xact` (lines 106-111) — state machine for the writer.
- `processing_required` (line 114) — fast-forward decoders flip this when
  they see a change they can't skip.

Entry points:

- `CheckLogicalDecodingRequirements(bool repack)` (line 118) — verifies
  `wal_level >= logical`, db connected, not in recovery. `[verified-by-code]`
- `CreateInitDecodingContext` (line 120) — first-time slot creation;
  needs catalog snapshot, runs the plugin's `startup_cb`.
- `CreateDecodingContext` (line 129) — subsequent restarts from an
  existing slot's `restart_lsn`.
- `DecodingContextFindStartpoint` (line 136) — walks WAL until a
  consistent snapshot is reached; the noisy phase `LogicalDecodingLogLevel`
  guards.
- `LogicalConfirmReceivedLocation(lsn)` (line 144) — subscriber/client
  acknowledged up through `lsn`; advances `confirmed_flush_lsn`.
- `LogicalReplicationSlotCheckPendingWal`, `LogicalSlotAdvanceAndCheckSnapState`
  (lines 152-155) — used by slotsync / replication-slot management to
  reason about catch-up.

## Phase D notes

- The context owns its own `MemoryContext` (line 36); the plugin's
  per-callback work is expected to land in shorter-lived child contexts.
  Plugins that leak into `ctx->context` will grow without bound across a
  long-running stream. `[inferred]`
- `fast_forward` repurposes the same struct without a plugin loaded.
  Anyone adding new mandatory fields must check both creation paths
  (`CreateInitDecodingContext` allocates with plugin, `CreateDecodingContext`
  takes `fast_forward` arg).
- `LogicalConfirmReceivedLocation` mutates persistent slot state on the
  publisher side based on the subscriber's "flushed up to" feedback —
  this is the trust hinge for slot xmin retention.

## Potential issues

- [ISSUE-trust-boundary: `LogicalConfirmReceivedLocation(lsn)` (line 144)
  advances durable slot state from a client-supplied LSN. A misbehaving
  or compromised subscriber that lies about flushed position can either
  freeze WAL retention (never confirm) or, conversely, advance past data
  it hasn't actually durably applied. The first is a DoS (disk fill); the
  second is an integrity issue if the subscriber crashes and the slot has
  already released the bytes. (maybe)]
- [ISSUE-undocumented-invariant: header doesn't spell out that
  `LogicalDecodingContext` is per-walsender / per-SQL-function-call and
  must NEVER be shared across backends — the `slot` pointer is acquired
  exclusively via `ReplicationSlotAcquire`. Easy footgun for new
  contributors adding background-worker decoding. (maybe)]
- [ISSUE-stale-todo: `fast_forward` mode's "most of the following
  properties are unused" comment (lines 47-51) is asking for a
  refactor — there's no compile-time enforcement that fast-forward code
  paths don't touch `callbacks`/`options`. (maybe)]
- [ISSUE-state-transition: `accept_writes`, `prepared_write`, `end_xact`
  form an implicit state machine but there's no enum or assertion
  helper; reorder-buffer callbacks rely on plugins flipping these in the
  right order via `OutputPluginPrepareWrite`/`OutputPluginWrite`. A
  misbehaving plugin can wedge the context. (maybe)]
