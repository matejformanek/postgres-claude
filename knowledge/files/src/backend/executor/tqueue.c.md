# tqueue.c

- **Source:** `source/src/backend/executor/tqueue.c` (210 lines)
- **Last verified commit:** `ef6a95c7c64` (2026-06-01)
- **Depth:** deep-read (whole file)

## Purpose

Tuple-passing between parallel-worker backends via `shm_mq`. Two halves:

- **Worker side**: a `DestReceiver` (`TQueueDestReceiver`) that takes the
  worker's executor output rows and writes them as MinimalTuples into a
  shm_mq the leader is reading.
- **Leader side**: a `TupleQueueReader` that pulls MinimalTuples out of one
  worker's queue and hands them to the consumer node (Gather/GatherMerge).

[from-comment] `:3-12`

## Receiver

`CreateTupleQueueDestReceiver(shm_mq_handle*)` allocates a TQueueDestReceiver.
Its `receiveSlot` calls `ExecFetchSlotMinimalTuple` then `shm_mq_send`
(no-wait if the receiver is reading; blocks via CHECK_FOR_INTERRUPTS-aware
wait if the queue is full).

## Reader

`CreateTupleQueueReader(shm_mq_handle*)` — leader-side reader.
`TupleQueueReaderNext(reader, &done, &nowait)`:
- If `nowait`, returns NULL immediately if no row is ready (used by Gather
  for non-blocking probes when other workers have rows).
- Otherwise waits on the mq.
- On worker-detached → sets `*done = true` and returns NULL.
- Wraps the raw bytes back into a MinimalTuple in the reader's memory context.

## Why MinimalTuple and not heap tuple

MinimalTuples have no header / system columns / OID — smallest wire format.
Workers only ever send the "logical row" data; system columns of base tables
are projected away or carried as junk columns of the regular tuple body.

## Tags

- [verified-by-code] every function in the file.
- [from-comment] purpose statement.

## Synthesized by
<!-- backlinks:auto -->
- [subsystems/executor.md](../../../../subsystems/executor.md)
- [subsystems/optimizer.md](../../../../subsystems/optimizer.md)
- [idioms/parallel-gather-merge.md](../../../../idioms/parallel-gather-merge.md)

