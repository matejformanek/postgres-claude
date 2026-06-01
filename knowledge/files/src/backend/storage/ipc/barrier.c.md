# `storage/ipc/barrier.c`

- **Source:** `source/src/backend/storage/ipc/barrier.c` (333 lines)
- **Header:** `source/src/include/storage/barrier.h`
- **Last verified commit:** `ef6a95c7c64` (2026-06-01)
- **Depth:** read

## Purpose

Process synchronization barriers, both **static** (fixed participants
known up front, like `pthread_barrier_t`) and **dynamic** (participants
join/leave at runtime, like Java's `Phaser`). [from-comment] `:9-78`.

Despite the filename, this file does **not** define memory barriers
(those are in `port/atomics.h` as `pg_memory_barrier()` and friends).
"Barrier" here is the synchronization primitive: N processes pile up
at `BarrierArriveAndWait` until all N have arrived, then all proceed.

## Note: file misnomer

`barrier.h` is small (46 lines) and only contains the `Barrier`
struct definition + the operations. The unrelated memory-barrier
intrinsics live in `port/atomics.h`. Don't confuse the two.

## API (header `barrier.h`)

- `BarrierInit(b, participants)` — `participants=0` ⇒ dynamic mode.
- `BarrierAttach(b)` — dynamic: bump participant count, returns
  current phase. Caller must do a `switch (phase)` fall-through to
  catch up.
- `BarrierDetach(b)` — dynamic: drop out; if you were holding up the
  current phase, it now advances without you.
- `BarrierArriveAndWait(b, wait_event_info)` — block until everyone
  arrives; returns true to exactly one "elected" participant (useful
  for "one of you write the result file").
- `BarrierArriveAndDetach(b, …)` — leave right after arriving (no wait).
- `BarrierPhase(b)` — read-only check of current phase.

## Implementation sketch

Uses a `ConditionVariable` + spinlock-protected counters. When the
last participant arrives at a phase, it broadcasts on the CV, bumps
the phase, and lets everyone proceed.

## Cross-references

- Primary consumer: parallel-aware executor nodes (parallel hash
  join uses it for build-phase synchronization).
- `condition_variable.c` — the wait primitive used.

## Open questions

The "elected participant" semantic (`BarrierArriveAndWait` returning
true to exactly one caller) — verifies the typical pattern of "one
worker finalizes" but I did not trace which executor nodes rely on
that election. `[unverified]`.

## Synthesized by
<!-- backlinks:auto -->
- [subsystems/storage-ipc.md](../../../../../subsystems/storage-ipc.md)
