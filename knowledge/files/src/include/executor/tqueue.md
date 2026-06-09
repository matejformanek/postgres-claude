# `src/include/executor/tqueue.h`

**Pin:** `4b0bf0788b066a4ca1d4f959566678e44ec93422`

## Role

Tuple queue over `shm_mq` — bidirectional in principle, used for
parallel-worker → leader tuple streaming [from-comment: lines 3-4].
Implements both the producer side (a `DestReceiver`) and the
consumer side (a `TupleQueueReader`).

## Public API

[verified-by-code: lines 20-31]

```c
typedef struct TupleQueueReader TupleQueueReader;  /* opaque */

DestReceiver   *CreateTupleQueueDestReceiver(shm_mq_handle *);
TupleQueueReader *CreateTupleQueueReader(shm_mq_handle *);
void            DestroyTupleQueueReader(TupleQueueReader *);
MinimalTuple   TupleQueueReaderNext(TupleQueueReader *, bool nowait,
                                    bool *done);
```

`nowait=true` returns NULL with `*done=false` if no tuple is
currently ready; `*done=true` signals end-of-stream (writer detached).

## Invariants

- **INV-MIN-TUPLE** [verified-by-code: line 29] Tuples flow as
  `MinimalTuple` — caller materializes into a slot.
- **INV-PAIRED** [inferred] Each `shm_mq_handle` has one writer
  (DestReceiver) and one reader (TupleQueueReader). The
  implementation in `tqueue.c` serializes a `MinimalTuple` directly
  into the shm_mq's frame.
- **INV-TYPE-FALLBACK** [from `tqueue.c`, not visible here] Composite
  types containing transient typmods, OR types whose binary form is
  not portable, fall back to text-mode serialization on the wire.
  This is a Phase D-relevant detail — exposing values through
  type-output functions that may have side effects.

## Trust boundary (Phase D)

- **Leader-worker channel**: tuples cross from a parallel worker
  back to the leader through shared memory. Both sides run as the
  same OS user; the security boundary that matters is *snapshot
  identity*, not data confidentiality.
- **Text-fallback risk**: when binary serialization isn't safe (rare,
  but possible for composite types with transient typmods), the
  worker runs the type's text-output function. If that function is
  user-defined (custom type), the **worker** executes user code under
  the parallel-query restrictions (parallel-safe/restricted
  labelling). A function that lies about being parallel-safe and
  accesses session state can leak/corrupt across the worker boundary.
- **`shm_mq_handle` ownership**: tied to a parallel context's DSM;
  cleanup on worker exit is automatic via DSM-on-exit hooks
  installed in the parallel context.

## Cross-refs

- `storage/shm_mq.h` — backing transport.
- `tcop/dest.h` — `DestReceiver` abstraction.
- `executor/execParallel.h` — uses `tqueue` for worker output.
- `executor/nodeGather.h` / `nodeGatherMerge.h` — consumer side.

## Issues

- [ISSUE-PHASE-D: text-fallback path runs type output functions in
  the worker; combined with mis-labeled parallel-safe types this can
  leak session state across the worker/leader boundary (medium —
  same class as parallel-safety violations everywhere else)] —
  not visible in header; documented in `tqueue.c`.
