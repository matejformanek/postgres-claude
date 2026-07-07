# WAL receiver loop — the WalReceiverMain inner cycle

The WAL receiver is the standby-side process that connects to a
primary's WAL sender and writes received WAL into the standby's
`pg_wal/`. It runs an inner loop: read message → dispatch by
type → write or apply protocol overhead → flush periodically →
report progress upstream. The loop's correctness invariants are
what guarantee the standby's WAL is byte-identical to the
primary's.

Anchors:
- `source/src/backend/replication/walreceiver.c:WalReceiverMain`
  [verified-by-code]
- `source/src/backend/replication/walreceiver.c:842
  XLogWalRcvProcessMsg` [verified-by-code]
- `knowledge/subsystems/replication.md` — surrounding
  replication subsystem
- `knowledge/idioms/crash-recovery-startup.md` — companion
  recovery flow

## The receiver process

`WalReceiverMain` is the entry point [verified-by-code
`walreceiver.c:154`]. The receiver is started by the startup
process when standby mode requires streaming WAL beyond what's
in the archive.

Lifecycle:
1. Started by startup process via shmem signal.
2. Establishes libpq connection to primary using
   `primary_conninfo` GUC.
3. Negotiates streaming start position
   (handshake via `WalReceiverFunctions`).
4. Enters the main read-message loop.
5. Exits on protocol error, network failure, or shutdown.

The receiver process is **independent of the startup process**
— they communicate via the WAL the receiver writes; the startup
process polls / waits on signals for fresh WAL.

## The message-receive loop

```c
while (running) {
    receive_message();
    XLogWalRcvProcessMsg(type, buf, len, tli);
    /* periodic: send feedback, flush */
}
```

[abstracted from `walreceiver.c:486`]

## Message dispatch

`XLogWalRcvProcessMsg(type, buf, len, tli)` switches on the
first byte of each message
[verified-by-code `walreceiver.c:842`]:

| Type byte | Meaning | Action |
|---|---|---|
| `'w'` | WAL data | Call `XLogWalRcvWrite(buf, len, recptr, tli)` |
| `'k'` | Keepalive | Reset timeout; respond if asked |
| `'X'` | Termination | Exit cleanly |

`'w'` messages carry a chunk of WAL — possibly a fragment of a
record or a whole record or multiple records. The receiver
treats them as opaque bytes; framing is the WAL reader's job
on the consumer side.

## The XLogWalRcvWrite path

[verified-by-code `walreceiver.c:913`]

```c
static void
XLogWalRcvWrite(char *buf, Size nbytes, XLogRecPtr recptr,
                TimeLineID tli);
```

For each chunk:

1. **Open the right WAL segment file** if not already.
2. **Write the bytes** at the offset `recptr` indicates.
3. **Update receive-position counter**.
4. **Mark dirty** so the periodic flush picks it up.

The write is unbuffered; the standard kernel page cache
handles it. The receiver's `recvFile` static carries the
current open segment.

## The flush + feedback cycle

Periodically (default ~10 seconds, configurable via
`wal_receiver_status_interval`):

1. **fsync** the receive file so far.
2. **Update `WalRcv->latestChunkStart`** so the startup
   process can read past where we've written.
3. **Send feedback** to the primary: "I have flushed up to
   LSN X."
4. The primary's WAL sender uses the feedback to advance the
   replication slot's `restart_lsn` and
   `confirmed_flush`.

The flush rate is a tunable; too frequent = waste; too rare =
primary's slot pins WAL longer than necessary.

## Hot-standby feedback (optional)

If `hot_standby_feedback = on`, the standby additionally
reports its **oldest snapshot xmin** to the primary. The
primary then pins its own xmin horizon to respect the standby
— preventing VACUUM from removing rows the standby's queries
might still want.

This is the standby's tradeoff: prevents query-cancellation
("snapshot too old"-style errors on the standby) at the cost
of bloat on the primary.

## The handshake and protocol negotiation

[from `walreceiver.c:174` initialization]

Before the main loop:

1. **Identify Timeline** — primary tells which timeline ID it's
   currently on.
2. **Start Replication** — standby asks to start at LSN X on
   timeline T.
3. **Identify System** — confirm the cluster identity matches.
4. **Slot negotiation** — if `primary_slot_name` is set, attach
   to that slot.

Mismatches (wrong cluster, wrong timeline) abort the
connection before any WAL is received.

## The Timeline ID

`TimeLineID` distinguishes the cluster's history-branches.
Promotion creates a new timeline; PITR rewinds may too. The
receiver must follow the timeline the primary advertises;
attempting to receive cross-timeline data corrupts the WAL.

`tli` is passed through every message; mismatches abort.

## Termination

The receiver exits on:
- Network error from libpq.
- Primary signaling end-of-WAL (uncommon).
- Postmaster signaling shutdown.
- Promotion (standby becoming primary).
- Connection-state corruption.

On exit, the startup process notices (via shmem state) and
either: re-launches the receiver to retry, or proceeds with
post-recovery if promoted.

## Reconnect with backoff

A network blip triggers receiver exit; startup process
re-launches after a brief delay (`wal_retrieve_retry_interval`,
default 5 seconds). The retry is bounded only by user
intervention; receiver re-connects indefinitely.

## Common review-time concerns

- **Don't buffer WAL writes in the receiver.** The startup
  process needs to see fresh bytes as they arrive.
- **Timeline correctness is critical.** Cross-timeline data
  = catastrophic corruption.
- **The feedback interval is a flush-rate knob.** Tune by
  measuring primary's slot-restart_lsn delay.
- **`hot_standby_feedback` is a bloat-vs-availability
  decision.** Document explicitly.
- **Connection-failure handling must be idempotent.** Re-
  starts can happen at any time.

## Invariants

- **[INV-1]** WAL bytes written are byte-identical to primary's
  WAL.
- **[INV-2]** Receiver follows ONE timeline at a time;
  mismatches abort.
- **[INV-3]** Periodic flush + feedback advance primary's
  slot.
- **[INV-4]** `hot_standby_feedback` pins primary's xmin.
- **[INV-5]** Receiver exit is followed by startup-process
  retry with backoff.

## Useful greps

- The main loop:
  `grep -n 'WalReceiverMain\|XLogWalRcvProcessMsg\|XLogWalRcvWrite' source/src/backend/replication/walreceiver.c | head -10`
- The message types:
  `grep -n "case '\(w\|k\|X\)'" source/src/backend/replication/walreceiver.c`
- The feedback path:
  `grep -RIn 'XLogWalRcvSendReply\|XLogWalRcvSendHSFeedback' source/src/backend/replication`



## Call sites
<!-- callsites:auto -->

*Auto-extracted from `source/<path>:<line>` cites in this doc's prose (bullets and free text).*
*Refresh via `scripts/populate-idiom-callsites.py` — edits inside this block are overwritten.*

| File | Line | Role |
|---|---:|---|
| [`src/backend/replication/walreceiver.c`](../files/src/backend/replication/walreceiver.c.md) | 842 | XLogWalRcvProcessMsg |
| [`src/backend/replication/walreceiver.c`](../files/src/backend/replication/walreceiver.c.md) | — | implementation |
| [`src/backend/replication/walreceiverfuncs.c`](../files/src/backend/replication/walreceiverfuncs.c.md) | — | shmem state + interlock with startup |

<!-- /callsites:auto -->

## Cross-references

- `knowledge/subsystems/replication.md` — surrounding
  replication subsystem.
- `knowledge/idioms/crash-recovery-startup.md` — startup
  process consumes the receiver's output.
- `knowledge/idioms/replication-slot-advance.md` — companion;
  feedback drives slot advance.
- `knowledge/idioms/wal-record-construction.md` — what the
  primary writes; what the receiver receives.
- `knowledge/idioms/xmin-horizon-management.md` — hot_standby_feedback
  pins primary's horizon.
- `.claude/skills/wal-and-xlog/SKILL.md` — WAL + replication
  contracts skill.
- `source/src/backend/replication/walreceiver.c` —
  implementation.
- `source/src/backend/replication/walreceiverfuncs.c` —
  shmem state + interlock with startup.
