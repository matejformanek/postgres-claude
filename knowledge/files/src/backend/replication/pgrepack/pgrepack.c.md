# `src/backend/replication/pgrepack/pgrepack.c`

- **Last verified commit:** `e18b0cb7344`
- **Lines:** ~305
- **Source:** `source/src/backend/replication/pgrepack/pgrepack.c`

Logical-decoding output plugin used internally by the PG18 `REPACK
(CONCURRENTLY)` command. Spills per-table row changes to a `BufFile`
so a follow-up worker can replay them onto the rewritten copy of
the table, while concurrent DML keeps running on the original.
[verified-by-code]

This is not a general-purpose plugin: `repack_startup` rejects any
caller that is not the REPACK worker process. [verified-by-code]

## API / entry points

- `_PG_output_plugin_init(cb)` (line 36) — installs the five
  callbacks below. [verified-by-code]
- `repack_startup(ctx, opt, is_init)` (line 47) — early bail if
  `!AmRepackWorker()` with `ERRCODE_FEATURE_NOT_SUPPORTED`. Allocates
  `RepackDecodingState`, creates a per-change memory context, sets
  `OUTPUT_PLUGIN_BINARY_OUTPUT`. Rejects any output-plugin options.
  [verified-by-code]
- `repack_shutdown` / `repack_begin_txn` / `repack_commit_txn` —
  empty bodies. Since the slot is held across the whole REPACK and
  we never use the SQL interface, there's no per-txn boilerplate
  needed. [verified-by-code]
- `repack_process_change(ctx, txn, relation, change)` (line 110) —
  the main callback. Asserts the change is for the table being
  repacked (other tables shouldn't decode through this plugin),
  then forwards to `repack_store_change` with INSERT /
  UPDATE_OLD / UPDATE_NEW / DELETE kinds. TRUNCATE hits the
  `Assert(false)` arm because REPACK relies on AccessExclusiveLock
  preventing concurrent TRUNCATE. [verified-by-code]
- `repack_store_change(ctx, relation, kind, tuple)` (line 190) —
  serialises one tuple to the `BufFile`. Handles
  external-indirect TOAST attributes specially: detoasts each one
  inline (since the indirect pointer references memory we don't
  control) and writes it after the heap tuple. [verified-by-code]

## On-disk spill format

- `kind` byte (`ConcurrentChangeKind`).
- `tuple->t_len` (uint32) + raw `tuple->t_data` (`t_len` bytes) —
  external-toast tag is preserved so the replay side can recover.
- `natt_ext` (uint32) — count of indirect-external attrs that
  follow.
- For each ext attr: full detoasted varlena. [verified-by-code]

## Notable invariants / details

- The plugin **does not call** `OutputPluginPrepareWrite` /
  `OutputPluginWrite`. The comment at line 86-92 explains: REPACK
  holds the slot for the entire operation, no SQL interface
  exists, the generic callback API is overkill. [from-comment]
- `change_cxt` is reset after each tuple via `MemoryContextReset`
  to bound per-call allocations during detoast.
  [verified-by-code]
- The single-tuple slot (`dstate->slot`) is lazily created on
  first need under `worker_cxt` and the worker's `ResourceOwner`;
  this is the only place memory-context juggling matters in this
  file. [verified-by-code]
- `Assert(VARATT_IS_EXTERNAL_ONDISK(varlen))` (line 274) — logical
  decoding never produces external-expanded datums; if seen, it's
  a bug elsewhere. [from-comment]

## Potential issues

- Line 176 — TRUNCATE protection relies entirely on the
  `AccessExclusiveLock` assumption in the comment. If a future
  patch relaxes TRUNCATE's lock level, `Assert(false)` would fire
  in cassert builds and silently miss the change otherwise.
  [ISSUE-undocumented-invariant: TRUNCATE-vs-REPACK protection is
  comment-only (maybe)]
- Line 64 — `dstate->change_cxt` is created under `ctx->context`
  but reset after each change. No matching `MemoryContextDelete`
  is visible in this file; presumably cleaned up when `ctx->context`
  itself is torn down. Worth verifying the plugin's overall
  cleanup path lives in `commands/repack.c`.
  [ISSUE-question: change_cxt lifetime crosses files (nit)]
- Snapshot management for the concurrent rewrite is NOT in this
  file — this plugin is purely the spill format. The
  snapshot-builder side (catalog snapshot vs. data snapshot for
  REPACK) lives in `commands/repack.c` and `replication/snapbuild.c`
  reaching points called via `commands/repack_internal.h`. Worth
  cross-checking when reviewing the PG18 REPACK commit.
  [ISSUE-question: where exactly is REPACK's data snapshot
  pinned? (maybe)]
