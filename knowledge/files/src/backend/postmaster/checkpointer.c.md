# checkpointer.c

- **Source:** `source/src/backend/postmaster/checkpointer.c` (1550 lines)
- **Last verified commit:** `ef6a95c7c64` (2026-06-01)
- **Depth:** read (top comment + key functions)

## Purpose

Singleton aux process introduced in PG 9.2 that owns ALL checkpoints —
automatic (time-driven via `checkpoint_timeout`), backend-requested (filled
WAL segments → backends signal), and shutdown checkpoints. Also serves as
the central **fsync forwarding** target: backends ship their pending fsync
requests to the checkpointer's queue so a single process handles them.
[from-comment] `:5-11`

## Shutdown protocol (load-bearing)

- `SIGINT` → execute shutdown checkpoint.
- After that, `SIGUSR2` → exit(0).
- **All backends must be stopped before `SIGINT` or `SIGUSR2` is issued** —
  postmaster ensures this via the `PostmasterStateMachine` ordering.
  [from-comment] `:13-16`
- `SIGQUIT` → abort (emergency).
- Unexpected exit = crash; postmaster sees we have lost the fsync queue and
  triggers a full crash-restart. [from-comment] `:21-26`

## Shared-memory protocol (ckpt counters)

Backends watch for their checkpoint request to complete via counters in
shmem under `ckpt_lck` spinlock: at checkpoint start the checkpointer reads
+ clears flags and increments `ckpt_started`; on completion it increments
`ckpt_done`. Backends compare snapshots of these counters before/after
their request. [from-comment] `:74-92`

## Key entry points

| Symbol | Role |
|---|---|
| `CheckpointerMain` | aux main loop — calls `AuxiliaryProcessMainCommon`, sigsetjmp wrapper, loops calling `CreateCheckPoint(flags)` on demand |
| `RequestCheckpoint` | backend-side; sets flags + signals checkpointer |
| `CheckpointWriteDelay` | called from inside `CreateCheckPoint` to pace writes |
| `ForwardSyncRequest` | backend-side; enqueue an fsync request to checkpointer |
| `AbsorbSyncRequests` | checkpointer-side; drain the queue |
| `CompactCheckpointerRequestQueue` | dedup the queue |
| `CheckpointerShmemInit` | reserve shmem |

## Interactions

- WAL: invokes `CreateCheckPoint` in `access/transam/xlog.c`.
- Sync: implements the request side of `storage/sync/sync.c`'s pending-ops.
- Postmaster: receives PM signals via flags.
- Header: `postmaster/bgwriter.h` historically held some checkpointer
  prototypes too — modern code lives in `postmaster/bgwriter.h` and
  `storage/checkpointer.h` (or inline in `xlog.h`).

## Synthesized by
<!-- backlinks:auto -->
- [subsystems/optimizer.md](../../../../subsystems/optimizer.md)
- [idioms/checkpoint-coordination.md](../../../../idioms/checkpoint-coordination.md)

