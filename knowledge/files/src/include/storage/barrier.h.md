# `storage/barrier.h`

- **Source:** `source/src/include/storage/barrier.h` (46 lines)
- **Last verified commit:** `ef6a95c7c64` (2026-06-01)
- **Depth:** full-read

Process-synchronization Barrier API. See `barrier.c.md` for the
extensive top-of-file design discussion.

## Naming gotcha

> "For the header previously known as 'barrier.h', please include
> 'port/atomics.h', which deals with atomics, compiler barriers and
> memory barriers." `:16-20`.

`storage/barrier.h` is the **synchronization primitive** (pthread_barrier-
like). For **memory barriers** (`pg_memory_barrier`, `pg_read_barrier`,
…), use `port/atomics.h`. Easy confusion.

## Barrier struct

```c
typedef struct Barrier {
    slock_t            mutex;
    int                phase;
    int                participants;
    int                arrived;
    int                elected;        /* highest phase elected */
    bool               static_party;   /* assertions only */
    ConditionVariable  condition_variable;
} Barrier;
```

## API

- `BarrierInit(b, participants)` — 0 ⇒ dynamic mode.
- `BarrierArriveAndWait(b, wait_event_info)` — block until everyone
  arrives at this phase. Returns true to exactly one elected caller.
- `BarrierArriveAndDetach(b)` — arrive + leave, don't wait.
- `BarrierArriveAndDetachExceptLast(b)` — arrive + detach unless we're
  the last (used for "stay if you're the last; otherwise leave"
  patterns).
- `BarrierAttach(b)` — dynamic mode: bump participants; returns
  current phase (for fall-through resume).
- `BarrierDetach(b)` — leave; if we were holding up the phase, it
  advances now.
- `BarrierPhase(b)`, `BarrierParticipants(b)` — read-only.

## Primary consumers

- Parallel hash join (build-phase rendezvous).
- Any executor node that wants "wait until all workers finish phase X"
  semantics.
