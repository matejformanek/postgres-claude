# src/include/replication/walreceiver.h

## Purpose

Shared-memory contract for the **walreceiver** auxiliary process plus the
pluggable `WalReceiverFunctions` jump-table (filled in by
`libpqwalreceiver.so` at module load). Used both by the startup process
on a standby (to launch and steer a walreceiver) and by logical
replication apply workers (to talk libpq to a publisher).

## Role in PG

A standby spawns one walreceiver auxiliary process. It opens a libpq
connection to the primary (or upstream standby for cascading), starts a
replication stream (`START_REPLICATION ... PHYSICAL`/`LOGICAL`), and
flushes received WAL to `pg_wal/`. The startup process reads what
walreceiver writes and replays. Logical apply workers reuse the same
`WalReceiverFunctions` jump-table but open a *logical* replication
connection instead. See `knowledge/subsystems/replication.md`.

The header sits between two worlds: a shared-memory struct describing
walreceiver state to the rest of the cluster, and a per-process libpq
abstraction (`WalReceiverConn`, opaque to everyone except the
libpqwalreceiver loadable module).

## Key types/struct fields

- `WalRcvState` enum (lines 45-55) — STOPPED → STARTING → CONNECTING →
  STREAMING → WAITING → RESTARTING → STOPPING lifecycle. `walRcvStoppedCV`
  (line 73) is the ConditionVariable shutdown waiters block on.
  [verified-by-code]

- `WalRcvData` (lines 58-164) — the shared-memory control struct, one
  per cluster, pointed to by `extern WalRcvData *WalRcv` (line 166).
  Protected by `slock_t mutex` (line 148) for most fields; `writtenUpto`
  is `pg_atomic_uint64` (line 156) to allow lock-free read of the
  in-progress write boundary; `apply_reply_requested` is `sig_atomic_t`
  (line 163) for cross-process bool with no spinlock. [verified-by-code]

- `WalRcvData.conninfo[MAXCONNINFO]` (line 124, MAXCONNINFO=1024 line
  37) — the libpq connection string. Comment on line 122-123 is
  explicit: "initially set to connect to the primary, and later
  clobbered to hide security-sensitive fields". The flag
  `ready_to_display` (line 146) gates `pg_stat_wal_receiver` exposure so
  the raw, password-bearing form is never shown via SQL. [verified-by-code,
  confirmed in `source/src/backend/replication/walreceiver.c:222-281`
  where the original is memset to 0 then replaced by
  `walrcv_get_conninfo(wrconn)` output, which libpq returns with
  passwords obfuscated]

- LSN tracking trio: `receiveStart`/`flushedUpto`/`writtenUpto`
  (lines 87-97, 156) plus `latestChunkStart` (line 106) and primary's
  `latestWalEnd` (line 117). startup process compares `flushedUpto` vs
  `latestChunkStart` to detect lag. [verified-by-code]

- `WalRcvStreamOptions` (lines 168-193) — what the caller (apply worker
  or startup) passes when telling walreceiver-or-libpqwalreceiver to
  open a stream. Discriminated union `proto.physical` vs `proto.logical`
  (lines 175-192). `logical.proto_version` is the on-wire logical
  replication protocol version (advanced in newer PG releases for new
  message types like sequences, two-phase). [verified-by-code]

- `WalReceiverConn` (line 195-196) — opaque forward decl; the real
  struct lives in `src/backend/replication/libpqwalreceiver/libpqwalreceiver.c`
  and wraps a `PGconn *`. The function-pointer hooks (lines 228-432)
  are how the rest of the backend invokes libpq without linking it. The
  jump-table is materialized by `_PG_init` of `libpqwalreceiver.so`,
  loaded on demand via `load_file("libpqwalreceiver", false)`.
  [verified-by-code]

- `WalReceiverFunctionsType` (lines 413-432) plus the macro shims
  (lines 436-469) — every callsite spells `walrcv_connect(...)`,
  `walrcv_exec(...)` etc., which expand to `WalReceiverFunctions->...`.
  Macro-shim pattern lets non-libpq builds still compile.
  [verified-by-code]

- `walrcv_clear_result()` static inline (lines 471-487) — caller-side
  helper to free a `WalRcvExecResult` and its tuplestore/tupledesc/err.
  [verified-by-code]

- `walrcv_create_slot_fn` (lines 366-372) — note the `failover` bool
  (PG17+ failover slots, used by subscriptions to make slots survive
  publisher failover) and `two_phase` for prepared-xact decoding.
  [from-comment]

- `walrcv_alter_slot_fn` (lines 380-383) — comment notes only `failover`
  and `two_phase` properties are mutable, mirroring the user-visible
  `ALTER_REPLICATION_SLOT` command. [from-comment]

## Phase D notes

**conninfo lifecycle (security-relevant):**

1. Startup process calls `RequestXLogStreaming(tli, recptr, conninfo,
   slotname, create_temp_slot)` (line 498-500), which `strlcpy`s the
   raw `primary_conninfo` (still containing `password=secret`) into
   `WalRcv->conninfo`. [verified-by-code at
   `source/src/backend/replication/walreceiverfuncs.c:311`]
2. Walreceiver process boots, reads the raw conninfo from shared memory
   into its own stack buffer, **memset's `walrcv->conninfo` to zero**,
   then replaces it with the obfuscated form returned by
   `walrcv_get_conninfo(wrconn)` (which libpq builds without the
   password). Only then is `ready_to_display` set to true. [verified-by-code
   at `source/src/backend/replication/walreceiver.c:222-281`]
3. `pg_stat_get_wal_receiver()` returns NULL for the conninfo column
   when `!ready_to_display`, so the raw-secret window is gated.
   [verified-by-code at `walreceiver.c:1489`]

The scrub is intentional and documented in the field comment
(lines 122-123). Window of exposure: between
`RequestXLogStreaming()` (raw conninfo written) and walreceiver's
post-connect memset (typically milliseconds, but if walreceiver crashes
before line 278 the raw conninfo persists in shared memory until the
next start). A core dump of the postmaster's shared memory during that
window would contain `primary_conninfo` plaintext.

**Server-version validation:** `walrcv_server_version_fn` (line 299)
returns `PQserverVersion()` from libpq, which is a numeric the primary
sends in startup packet. Apply workers and physical replication trust
this (e.g. `START_REPLICATION` syntax variants gated on version). A
malicious primary could lie, but the libpq protocol version negotiation
and `IDENTIFY_SYSTEM` cross-checks should catch gross mismatches.
[inferred]

**`walrcv_identify_system_fn`** (lines 284-285) returns the **primary's**
`system_identifier`. The standby compares it to its own (set at
`pg_basebackup` time) and aborts on mismatch. This is the only
identity-check against a malicious or wrong primary. The A4
`pg_basebackup` walmethods finding (server-supplied `wal_segment_size`,
`system_identifier` trusted) has a direct echo here: same
`system_identifier` consumed, no signed-ID, just byte equality.
[inferred]

**`MAXCONNINFO = 1024`** (line 37) is hard-coded; the XXX comment on
line 35 ("Should this move to pg_config_manual.h?") flags it as a
stale-todo. A 1024-byte conninfo cap is plenty for normal use but a
CONNECT-with-100-host-failover-list user might bump it.
[from-comment]

## Potential issues

- [ISSUE-secret-scrub: raw `primary_conninfo` lives in `WalRcv->conninfo`
  shared memory from `RequestXLogStreaming` until walreceiver's
  post-connect memset; a postmaster crash dump during the window leaks
  the password (maybe)]
- [ISSUE-trust-boundary: `walrcv_server_version_fn` and
  `walrcv_identify_system_fn` results are trusted byte-for-byte;
  only system_identifier mismatch causes abort, no signed handshake
  (maybe)]
- [ISSUE-stale-todo: `MAXCONNINFO=1024` with explicit XXX comment line
  35 questioning location of macro (low)]
- [ISSUE-undocumented-invariant: which `WalRcvData` fields are
  "self-written by walreceiver and readable without lock" is asserted
  in the struct comment (lines 36-39 of WalSnd, similar pattern here at
  lines 60-69) but not enumerated per-field — readers must trace
  `walreceiver.c` to know what's safe (low)]
- [ISSUE-state-transition: `WalRcvState` has 7 values and transitions
  are documented only in scattered call sites (`ShutdownWalRcv`,
  `WalRcvDie`, `RequestXLogStreaming`); no single diagram in header
  (low)]

## Cross-references

<!-- issues:auto:begin -->
- [Issue register — `include-replication`](../../../../issues/include-replication.md)
<!-- issues:auto:end -->

## Synthesized by
<!-- backlinks:auto -->
- [subsystems/replication.md](../../../../subsystems/replication.md)
