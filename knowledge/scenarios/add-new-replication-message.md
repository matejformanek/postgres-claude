---
scenario: add-new-replication-message
when_to_use: New logical-decoding `output_plugin` callback (with matching wire byte + subscriber handler) OR a new walsender command (replication-protocol verb parsed by `repl_gram.y` and dispatched by `exec_replication_command`).
companion_skills: ["replication-overview"]
related_scenarios: ["add-new-wal-record", "add-new-protocol-message"]
canonical_commit: 45fdc9738b3
last_verified_commit: e18b0cb7344
---

# Scenario — Add a new replication / logical-decoding message

## Scope — what's in / out

Two distinct surfaces live behind one "replication message" mental model.
Pick the surface up-front; the file sweep diverges from there.

**Surface A — new output-plugin callback** (e.g. `stream_start_cb`):
- A new function-pointer typedef + `OutputPluginCallbacks` struct slot
  in `replication/output_plugin.h` [verified-by-code
  `source/src/include/replication/output_plugin.h:216-243`].
- A `*_cb_wrapper` static in `logical.c` and assignment into the
  `ReorderBuffer` callback hook table during `StartupDecodingContext`
  [verified-by-code `source/src/backend/replication/logical/logical.c:212-250`].
- An `OutputPluginPrepareWrite` / `OutputPluginWrite` use inside the
  wrapper if the callback is supposed to emit bytes [verified-by-code
  `source/src/backend/replication/logical/logical.c:1260-1305`].
- The required vs optional decision (does failing to install it ERROR
  at runtime, or silently no-op?) — see streaming gate at
  `source/src/backend/replication/logical/logical.c:227-233`
  [verified-by-code].
- New `LOGICAL_REP_MSG_*` byte in `replication/logicalproto.h` enum
  [verified-by-code `source/src/include/replication/logicalproto.h:57-78`].
- `logicalrep_write_<x>` / `logicalrep_read_<x>` pair in
  `replication/logical/proto.c` [verified-by-code
  `source/src/backend/replication/logical/proto.c:1064-1100`].
- `logicalrep_message_type()` switch arm — used in apply-side error
  context [verified-by-code
  `source/src/backend/replication/logical/proto.c:1212-1260`].
- `pgoutput` implementation (`pgoutput_<x>`) + callback registration in
  `_PG_output_plugin_init` [verified-by-code
  `source/src/backend/replication/pgoutput/pgoutput.c:73-280,1841-1900`].
- Subscriber-side `apply_handle_<x>` + dispatch arm in
  `apply_dispatch()` [verified-by-code
  `source/src/backend/replication/logical/worker.c:3797-3897`].
- `LOGICALREP_PROTO_*_VERSION_NUM` bump — protocol-version lever; the
  subscriber requests a `proto_version` and the publisher must gate the
  new message behind it [verified-by-code
  `source/src/include/replication/logicalproto.h:40-45`].
- `test_decoding` mirror implementation (so the contrib smoke tests
  cover the new callback) [verified-by-code
  `source/contrib/test_decoding/test_decoding.c:93-146,769-790`].
- Subscription TAP test exercising end-to-end + `logicaldecoding.sgml`
  section.

**Surface B — new walsender command** (e.g. `READ_REPLICATION_SLOT`):
- New `K_<KEYWORD>` token + keyword rule in `repl_scanner.l` and
  `repl_gram.y` [verified-by-code
  `source/src/backend/replication/repl_scanner.l:134`,
  `source/src/backend/replication/repl_gram.y:62-82,114-126`].
- New parse-result Node (`<X>Cmd`) in `nodes/replnodes.h`
  [verified-by-code `source/src/include/nodes/replnodes.h:79-110`].
- Dispatch arm in `exec_replication_command()` `switch (cmd_node->type)`
  block [verified-by-code
  `source/src/backend/replication/walsender.c:2197-2270`].
- Handler function in `walsender.c` that sends the row description /
  data rows / `CommandComplete`.
- `protocol.sgml` entry under "Streaming Replication Protocol".
- `pg_hba.conf` `replication` keyword already covers it — no auth
  change needed.

**Out of scope:**
- Adding a brand-new physical replication wire message (libpq-level
  byte like `CopyData`) — that's
  [add-new-protocol-message.md](add-new-protocol-message.md). The
  *replication* protocol piggy-backs on the libpq protocol; a NEW
  CopyData payload type belongs there.
- New WAL record kind — [add-new-wal-record.md](add-new-wal-record.md).
  A new output-plugin callback usually does NOT need a new WAL record;
  it serializes existing reorder-buffer state.
- `walreceiver` (physical receiver) wire additions — same protocol
  family but separate code path under
  `src/backend/replication/libpqwalreceiver/`. The surface-A path
  covers logical decoding only.

## Pre-flight

- **Companion skills:** load `replication-overview`. Covers the
  walsender ↔ output-plugin ↔ reorder-buffer ↔ apply-worker pipeline
  and where messages enter/leave each stage.
- **Canonical commit:** `45fdc9738b3` — *Extend the logical decoding
  output plugin API with stream methods* (Tomas Vondra, 2020-09-23).
  Adds eight new callbacks (`stream_start_cb`, `stream_stop_cb`,
  `stream_abort_cb`, `stream_commit_cb`, `stream_change_cb`,
  `stream_message_cb`, `stream_truncate_cb`, `stream_prepare_cb`),
  their wrappers, wire bytes, pgoutput hooks, apply-worker handlers,
  proto-version gate, test_decoding mirrors, and docs — the most
  complete worked example of Surface A in tree. Read it end-to-end
  before starting [verified-by-code `git show 45fdc9738b3`].
- For Surface B, read `73292404370` — *Allow setting failover property
  in the replication command* — recent canonical example of
  extending `ALTER_REPLICATION_SLOT` parsing + dispatch [verified-by-code
  `git log --grep=ALTER_REPLICATION_SLOT`].
- **Common pitfalls (one-line each):**
  - Forgetting the proto-version bump → subscribers on older PG silently
    receive an unknown byte and `apply_dispatch` errors with
    `invalid logical replication message type "??? (%d)"`
    [verified-by-code `source/src/backend/replication/logical/worker.c:3893-3896`].
  - New callback added to the `OutputPluginCallbacks` struct but no
    wrapper assigned in `StartupDecodingContext` → reorder-buffer calls
    NULL [from-comment
    `source/src/backend/replication/logical/logical.c:235-242`].
  - Wrapper exists but doesn't go through `OutputPluginPrepareWrite` /
    `OutputPluginWrite` → output bytes are dropped silently [inferred
    from pattern at `source/src/backend/replication/logical/logical.c:1260-1305`].
  - Forgetting to mirror in `test_decoding` → the `contrib/test_decoding`
    regress suite still passes but covers nothing of the new path.
  - New walsender command rejected with `syntax error` even though the
    grammar rule is present → forgot the keyword in `repl_scanner.l`.

## File checklist (the FULL sweep)

Marked **(A)** = Surface A only (output-plugin callback). Marked **(B)**
= Surface B only (walsender command). Unmarked rows apply to both.

| # | File | Why | Per-file doc | Companion skill |
|---|---|---|---|---|
| 1 | `src/include/replication/output_plugin.h` | **(A)** Add the `LogicalDecode<X>CB` typedef + new slot in `OutputPluginCallbacks` struct [verified-by-code `source/src/include/replication/output_plugin.h:216-243`]. Order in struct matters only for readability; runtime lookup is by field name. | [output_plugin.h.md](../files/src/include/replication/output_plugin.h.md) | replication-overview |
| 2 | `src/backend/replication/logical/logical.c` | **(A)** Three edits: (i) static `*_cb_wrapper` prototype near `begin_cb_wrapper` at line 62 [verified-by-code]; (ii) `ctx->reorder-><field> = <x>_cb_wrapper` in `StartupDecodingContext` near line 212 [verified-by-code `source/src/backend/replication/logical/logical.c:212-250`]; (iii) the wrapper body around line 1260 — `PG_TRY` / push error context / call `ctx->callbacks.<x>_cb` / `PG_END_TRY` [verified-by-code `source/src/backend/replication/logical/logical.c:1260-1305`]. Decide: required (`ereport(ERROR, "...output plugin does not define X")`) or optional (silently no-op). | [logical.c.md](../files/src/backend/replication/logical/logical.c.md) | replication-overview |
| 3 | `src/include/replication/reorderbuffer.h` | **(A)** If the new callback fires from inside `ReorderBufferCommit`/`ReorderBufferReplay` (i.e. is invoked by the reorder buffer, not by `decode.c` directly), add the matching `Rb<X>CB` typedef + `ReorderBuffer.<x>` field hook so the wrapper has somewhere to attach [verified-by-code grep `stream_start` in `source/src/include/replication/reorderbuffer.h`]. | [reorderbuffer.h.md](../files/src/include/replication/reorderbuffer.h.md) | replication-overview |
| 4 | `src/backend/replication/logical/reorderbuffer.c` | **(A)** Call site — where the reorder buffer decides "time to emit this kind of message" and invokes `rb-><x>(rb, txn, ...)`. For stream callbacks this is inside the in-progress-streaming branch [verified-by-code grep for `rb->stream_start` in `source/src/backend/replication/logical/reorderbuffer.c`]. | — | replication-overview |
| 5 | `src/include/replication/logicalproto.h` | **(A)** Add `LOGICAL_REP_MSG_<X> = '<char>'` enum value [verified-by-code `source/src/include/replication/logicalproto.h:57-78`]. Pick a single ASCII byte not already taken — readable characters preferred (uppercase for transactional, lowercase for the streamed/prepared variants by convention) [from-comment `source/src/include/replication/logicalproto.h:48-56`]. Also bump `LOGICALREP_PROTO_<X>_VERSION_NUM` (new constant) + `LOGICALREP_PROTO_MAX_VERSION_NUM` [verified-by-code `source/src/include/replication/logicalproto.h:40-45`]. Add `extern` decls for the new `logicalrep_write_<x>` / `logicalrep_read_<x>` pair. | [logicalproto.h.md](../files/src/include/replication/logicalproto.h.md) | replication-overview |
| 6 | `src/backend/replication/logical/proto.c` | **(A)** Implement `logicalrep_write_<x>(StringInfo out, ...)` (writes the message byte then payload via `pq_sendint*`/`pq_sendstring`) and the mirror `logicalrep_read_<x>(StringInfo in, ...)` [verified-by-code pattern `source/src/backend/replication/logical/proto.c:1064-1100`]. Also add an arm to `logicalrep_message_type()` returning a human-readable name [verified-by-code `source/src/backend/replication/logical/proto.c:1212-1260`]. | [proto.c.md](../files/src/backend/replication/logical/proto.c.md) | replication-overview |
| 7 | `src/backend/replication/pgoutput/pgoutput.c` | **(A)** Three edits: (i) static `pgoutput_<x>` declaration near line 73 [verified-by-code]; (ii) `cb-><x>_cb = pgoutput_<x>` in `_PG_output_plugin_init` near line 278 [verified-by-code `source/src/backend/replication/pgoutput/pgoutput.c:278-285`]; (iii) implementation calling `logicalrep_write_<x>` between `OutputPluginPrepareWrite` and `OutputPluginWrite` [verified-by-code `source/src/backend/replication/pgoutput/pgoutput.c:1841-1900`]. Gate emission on `data->protocol_version >= LOGICALREP_PROTO_<X>_VERSION_NUM` if the message is added in a later protocol version. | [pgoutput.c.md](../files/src/backend/replication/pgoutput/pgoutput.c.md) | replication-overview |
| 8 | `src/backend/replication/logical/worker.c` | **(A)** Two edits: (i) `apply_handle_<x>(StringInfo s)` function — reads payload via the new `logicalrep_read_<x>`, performs subscriber-side action; (ii) `case LOGICAL_REP_MSG_<X>:` arm in `apply_dispatch()` [verified-by-code `source/src/backend/replication/logical/worker.c:3797-3897`]. Mind the in-streaming vs out-of-streaming guard — many of the existing arms call `Assert(in_streaming)` or similar. | [worker.c.md](../files/src/backend/replication/logical/worker.c.md) | replication-overview |
| 9 | `src/backend/replication/logical/applyparallelworker.c` | **(A)** If the new message can flow through a parallel apply worker (transactional, large-txn streamed), the parallel-apply leader / worker IPC path may need parsing parity. Most stream-* arms route through `apply_dispatch` unchanged so no new code is needed, but re-read this file when streaming-mode involvement is non-obvious [verified-by-code `source/src/backend/replication/logical/applyparallelworker.c`]. | [applyparallelworker.c.md](../files/src/backend/replication/logical/applyparallelworker.c.md) | replication-overview |
| 10 | `contrib/test_decoding/test_decoding.c` | **(A)** Mirror the new callback so `make check` over the test_decoding suite exercises it. Pattern: static `pg_decode_<x>(...)`, registration in `_PG_output_plugin_init`, optional helper like `pg_output_<x>` for textual dump [verified-by-code `source/contrib/test_decoding/test_decoding.c:93-146,769-790`]. | — | replication-overview |
| 11 | `contrib/test_decoding/sql/<name>.sql` | **(A)** New SQL regress test (or extend an existing one like `stream.sql`) that creates a slot, advances it, and validates the textual output contains the new message [verified-by-code `source/contrib/test_decoding/sql/`]. | — | testing |
| 12 | `contrib/test_decoding/expected/<name>.out` | **(A)** Matching expected output. | — | testing |
| 13 | `src/test/subscription/t/<NNN>_<name>.pl` | **(A)** TAP test driving publisher → subscriber end-to-end with the new message in scope. Pattern: see `src/test/subscription/t/015_stream.pl` for streaming, `028_row_filter.pl` for filter callbacks [verified-by-code `source/src/test/subscription/t/`]. | — | testing |
| 14 | `src/backend/replication/repl_scanner.l` | **(B)** Add `<KEYWORD> { return K_<KEYWORD>; }` rule — case-insensitive by default at this point in the file [verified-by-code `source/src/backend/replication/repl_scanner.l:134`]. | [repl_scanner.l.md](../files/src/backend/replication/repl_scanner.l.md) | replication-overview |
| 15 | `src/backend/replication/repl_gram.y` | **(B)** Three edits: (i) `%token K_<KEYWORD>` declaration near line 62 [verified-by-code `source/src/backend/replication/repl_gram.y:62-82`]; (ii) new `%type <node> <cmd>` declaration; (iii) grammar rule producing `(Node *) makeNode(<X>Cmd)`; (iv) add `<cmd>` to the `command:` top-level alternation around line 114 [verified-by-code `source/src/backend/replication/repl_gram.y:114-126`]; (v) add the keyword to `ident_or_keyword:` if it should be usable as an option name [verified-by-code `source/src/backend/replication/repl_gram.y:424-446`]. | [repl_gram.y.md](../files/src/backend/replication/repl_gram.y.md) | replication-overview |
| 16 | `src/include/nodes/replnodes.h` | **(B)** Define the `<X>Cmd` struct — `NodeTag type` first, then command-specific fields [verified-by-code `source/src/include/nodes/replnodes.h:79-110`]. After editing, `gen_node_support.pl` regenerates `nodetags.h` + copy/equal/out (run `meson compile` to trigger). | — | replication-overview |
| 17 | `src/backend/replication/walsender.c` | **(B)** Two edits: (i) handler function declaration + body — sends `RowDescription` (`pq_beginmessage('T')`) followed by `DataRow` (`pq_beginmessage('D')`) frames then `CommandComplete` (`EndReplicationCommand`); (ii) new `case T_<X>Cmd:` arm in the `switch (cmd_node->type)` block inside `exec_replication_command` [verified-by-code `source/src/backend/replication/walsender.c:2197-2270`]. Pattern: see `ReadReplicationSlot` at line 511 + its dispatch arm at 2206. | [walsender.c.md](../files/src/backend/replication/walsender.c.md) | replication-overview |
| 18 | `doc/src/sgml/protocol.sgml` | **(A)** Section under "Logical Replication Message Formats" near line 6588 describing the byte-level layout of the new message [verified-by-code `source/doc/src/sgml/protocol.sgml:6588`]. **(B)** New `<varlistentry id="protocol-replication-<x>">` entry under "Streaming Replication Protocol" near line 2345 [verified-by-code `source/doc/src/sgml/protocol.sgml:2345-2515`]. | — | — |
| 19 | `doc/src/sgml/logicaldecoding.sgml` | **(A)** Add a "<X> Callback" sect2 mirroring "Stream Start Callback" at line 1270 [verified-by-code `source/doc/src/sgml/logicaldecoding.sgml:1270`]. Include the typedef signature, the "required vs optional" note, and what the wrapper passes. Also amend the callback-summary block at line 817 [verified-by-code `source/doc/src/sgml/logicaldecoding.sgml:817-850`]. | — | — |
| 20 | `src/test/subscription/t/<NNN>_proto_version.pl` (optional) | **(A)** If a proto-version bump fences off the new message, extend the existing proto-version compat TAP harness or add one — see `src/test/subscription/t/100_bugs.pl` for cross-version style. | — | testing |

## Phases — suggested split for `pg-feature-plan`

1. **Phase 1 — typedef + wire byte + wrappers (Surface A) OR
   grammar + node + dispatch (Surface B).** Files A: 1, 2, 3, 4, 5
   (enum + version + decls only), 6. Files B: 14, 15, 16, 17 (with a
   stub handler that just sends `CommandComplete`). Phase-end check:
   `meson compile` clean. For A, decoding into an output plugin that
   ignores the new callback still works (optional callback) or errors
   with the chosen message (required). For B, the new walsender verb
   is parseable and dispatchable.

2. **Phase 2 — pgoutput + apply worker (A) / real handler body (B).**
   Files A: 7, 8, 9. Implement `pgoutput_<x>` (writer side) and
   `apply_handle_<x>` (reader side) with proto-version gating. Files
   B: 17 (fill handler body), data rows actually emitted. Phase-end
   check: a publication/subscription pair survives a round-trip
   exercising the new message; new walsender verb returns expected
   rowset against `psql "replication=database"`.

3. **Phase 3 — contrib mirror + tests + docs.** Files: 10, 11, 12,
   13, 18, 19, 20. Phase-end check: `meson test -C dev/build-debug
   --suite isolation` + `meson test -C dev/build-debug --suite
   subscription` + `meson test -C dev/build-debug --suite test_decoding`
   all green. `make -C doc/src/sgml` clean.


## Likely reviewers
<!-- persona-reviewers:auto -->

*Personas whose Domain-ownership paths overlap this scenario's §Files. Reflect who might catch this on hackers-list.*
*Refresh via `scripts/build-persona-scenario-matrix.py`.*

| Persona | Overlapping path(s) |
|---|---|
| [`masahiko-sawada`](../personas/masahiko-sawada.md) | `src/backend/replication`, `src/include/replication` |
| [`peter-eisentraut`](../personas/peter-eisentraut.md) | `src/include`, `src/backend/replication` |
| [`heikki-linnakangas`](../personas/heikki-linnakangas.md) | `src/include` |
| [`nathan-bossart`](../personas/nathan-bossart.md) | `src/include` |

<!-- /persona-reviewers:auto -->

## Idioms invoked
<!-- idioms-invoked:auto -->

*Auto-derived from direct references + transitive file-overlap with idiom Call sites.*
*Refresh via `scripts/build-scenario-idiom-matrix.py`.*

| Idiom | Evidence |
|---|---|
| [`apply-handlers-insert-update-delete`](../idioms/apply-handlers-insert-update-delete.md) | shares files: `src/backend/replication/logical/proto.c`, `src/backend/replication/logical/worker.c` |
| [`apply-streaming-and-parallel`](../idioms/apply-streaming-and-parallel.md) | shares files: `src/backend/replication/logical/applyparallelworker.c`, `src/backend/replication/logical/worker.c` |
| [`apply-worker-loop`](../idioms/apply-worker-loop.md) | shares files: `src/backend/replication/logical/worker.c` |
| [`apply-worker-loop-and-dispatch`](../idioms/apply-worker-loop-and-dispatch.md) | direct reference |
| [`logical-decoding-snapshot`](../idioms/logical-decoding-snapshot.md) | direct reference |
| [`memory-context-slab-generation-bump`](../idioms/memory-context-slab-generation-bump.md) | shares files: `src/backend/replication/logical/reorderbuffer.c` |
| [`output-plugin-callbacks`](../idioms/output-plugin-callbacks.md) | direct reference |
| [`walsender-state-machine`](../idioms/walsender-state-machine.md) | direct reference |

<!-- /idioms-invoked:auto -->
## Pitfalls

- **Proto-version gate omission.** A subscriber connecting with an
  older `proto_version` request must NOT see the new byte. Gate
  emission on `data->protocol_version >= LOGICALREP_PROTO_<X>_VERSION_NUM`
  inside `pgoutput_<x>` [verified-by-code pattern
  `source/src/backend/replication/pgoutput/pgoutput.c` — search for
  `protocol_version >=`]. Failing this trips
  `apply_dispatch`'s default-arm `errcode(ERRCODE_PROTOCOL_VIOLATION)`
  on the subscriber [verified-by-code
  `source/src/backend/replication/logical/worker.c:3893-3896`].

- **Required-vs-optional callback semantics.** The streaming wrappers
  treat `stream_start_cb` / `stream_stop_cb` / `stream_abort_cb` /
  `stream_commit_cb` / `stream_change_cb` as required (`ereport(ERROR,
  "...does not define ...stream_start_cb")` at first invocation) but
  treat `stream_message_cb` / `stream_truncate_cb` as optional
  (silent no-op) [verified-by-code
  `source/src/backend/replication/logical/logical.c:1295-1305`]. The
  enabling check at line 227 considers ANY non-NULL streaming callback
  as "streaming requested", then per-call wrappers ERROR for the
  required ones — so an output plugin that installs only one streaming
  callback gets a confusing runtime error rather than a startup
  rejection. Decide your semantics deliberately.

- **`OutputPluginPrepareWrite` / `OutputPluginWrite` discipline.** Every
  wrapper that wants the underlying `ctx->out` buffer flushed to the
  client must bracket its `logicalrep_write_<x>` call between these two
  [verified-by-code `source/src/backend/replication/logical/logical.c:246-247`].
  Skipping `OutputPluginWrite` does NOT error — bytes just get
  overwritten by the next callback.

- **`logicalrep_message_type()` switch is exhaustive — no `default:`
  arm.** Adding a new `LOGICAL_REP_MSG_*` enum value without a matching
  arm produces a `-Wswitch` warning that the build promotes to error
  under `-Werror` [verified-by-code
  `source/src/backend/replication/logical/proto.c:1212-1265`].

- **`apply_dispatch()` default arm is the catch-all.** Conversely the
  apply-side switch DOES have a `default:` and ERRORs with
  `"invalid logical replication message type"` [verified-by-code
  `source/src/backend/replication/logical/worker.c:3893-3896`]. A
  message that escapes the proto-version gate lands here.

- **Walsender command must respect transaction state.** The dispatch
  block calls `PreventInTransactionBlock(true, cmdtag)` for
  `BASE_BACKUP`, `START_REPLICATION`, `TIMELINE_HISTORY` [verified-by-code
  `source/src/backend/replication/walsender.c:2216,2248,2265`]. Decide
  per-command whether yours belongs in that set.

- **Synchronization traps:**
  - `output_plugin.h` `OutputPluginCallbacks` field ↔ `logical.c`
    wrapper assignment in `StartupDecodingContext` ↔ `pgoutput.c`
    `_PG_output_plugin_init` registration ↔ `test_decoding.c` mirror.
    Four files must agree on the callback name.
  - `logicalproto.h` `LOGICAL_REP_MSG_<X>` enum ↔ `proto.c`
    `logicalrep_write_<x>`/`read_<x>` + `logicalrep_message_type` arm
    ↔ `worker.c` `apply_dispatch` arm. Three files must agree on the
    byte.
  - `logicalproto.h` `LOGICALREP_PROTO_<X>_VERSION_NUM` ↔ `pgoutput.c`
    emission gate ↔ `MAX_VERSION_NUM` constant update. Three sites.
  - `repl_gram.y` token ↔ `repl_scanner.l` keyword ↔ `replnodes.h`
    `<X>Cmd` struct ↔ `walsender.c` `T_<X>Cmd` dispatch. Four files
    for Surface B.

## Verification (exact test invocations)

```bash
# Build (forces bison + gen_node_support.pl)
meson compile -C dev/build-debug

# Subscription end-to-end TAP
meson test -C dev/build-debug --suite subscription

# Isolation (catches concurrent-decoding races)
meson test -C dev/build-debug --suite isolation --test logical-decoding

# test_decoding contrib regress (Surface A mirror)
meson test -C dev/build-debug --suite test_decoding

# Recovery (replay path under load)
meson test -C dev/build-debug --suite recovery

# Walsender command smoke (Surface B):
psql "dbname=postgres replication=database" -c "<NEW_COMMAND> ..."

# Logical decoding smoke (Surface A):
psql -c "SELECT pg_create_logical_replication_slot('s', 'test_decoding');"
psql -c "SELECT data FROM pg_logical_slot_get_changes('s', NULL, NULL);"
```

New tests this scenario expects to ship:
- `contrib/test_decoding/sql/<name>.sql` + `expected/<name>.out`
  (Surface A only).
- `src/test/subscription/t/<NNN>_<name>.pl` (Surface A — end-to-end
  through pgoutput + apply worker).

## Cross-refs

- Companion skills: `.claude/skills/replication-overview/SKILL.md`,
  `.claude/skills/wal-and-xlog/SKILL.md` (only if the new path triggers
  a WAL change, which it usually doesn't).
- Related scenarios:
  [add-new-wal-record.md](add-new-wal-record.md) — if the new behavior
  needs to be replayed during crash recovery (not just decoded), you
  need a WAL record too.
  [add-new-protocol-message.md](add-new-protocol-message.md) — for
  libpq-level wire additions; logical-replication messages ride inside
  `CopyData` frames carved out by that layer.
- Idioms: `knowledge/idioms/output-plugin-callbacks.md` (callback
  contract + wrapper pattern), `knowledge/idioms/walsender-state-machine.md`
  (command dispatch + ps display + `EndReplicationCommand` discipline),
  `knowledge/idioms/apply-worker-loop-and-dispatch.md`,
  `knowledge/idioms/logical-decoding-snapshot.md`.
- Subsystems: `knowledge/subsystems/replication.md`,
  `knowledge/subsystems/include-replication.md`.
- Issues: `knowledge/issues/replication.md` (if present — protocol
  evolution + version-gate hazards).
- Reference patch (canonical_commit): `git -C source show
  45fdc9738b3` — *Extend the logical decoding output plugin API with
  stream methods* (Surface A, the eight `stream_*_cb` callbacks).
  Surface B reference: `git -C source show 73292404370` —
  `ALTER_REPLICATION_SLOT` extension.
