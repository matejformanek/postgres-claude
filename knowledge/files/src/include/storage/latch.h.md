# `storage/latch.h`

- **Source:** `source/src/include/storage/latch.h` (142 lines)
- **Last verified commit:** `ef6a95c7c64` (2026-06-01)
- **Depth:** full-read

Public latch API. The bulk of the file is the **wait-loop coding
pattern** comment (`:41-78`), which is required reading for any code
adding a latch-driven loop.

## Canonical pattern

```c
for (;;)
{
    ResetLatch(MyLatch);
    if (work_to_do)
        do_stuff();
    WaitLatch(MyLatch, WL_LATCH_SET | WL_EXIT_ON_PM_DEATH, ...);
}
```

`ResetLatch` *before* the work-check; otherwise a `SetLatch` arriving
between check and reset would be lost. The setter writes its flag
*before* calling `SetLatch` so the waiter's work-check sees it after
ResetLatch's memory barrier.

## Alternate pattern

`if (work_to_do) do_stuff(); WaitLatch(); ResetLatch();` — valid only
if the loop's termination condition is often satisfied on the first
iteration; otherwise it's an extra spurious wake.

**Never** place asynchronous-event checks between `WaitLatch` and
`ResetLatch` — race window. `:68-70`.

## Process latch convention

> "Use of the process latch (PGPROC.procLatch) is generally better
> than an ad-hoc shared latch for signaling auxiliary processes."
> `:80-84`.

Reason: every generic signal handler calls `SetLatch(MyLatch)` (the
process latch). Using a different latch precludes integrating with
those generic handlers.

## Latch struct (opaque-ish)

```c
typedef struct Latch {
    sig_atomic_t is_set;
    sig_atomic_t maybe_sleeping;
    bool         is_shared;
    int          owner_pid;
#ifdef WIN32
    HANDLE       event;
#endif
} Latch;
```

Defined in the header so it can be embedded in larger structs (e.g.
`PGPROC.procLatch`), but **callers should treat it as opaque** — only
use the public functions.

## See also

`waiteventset.h` — the underlying multi-event primitive. Long-lived
event sets are more efficient than `WaitLatch` / `WaitLatchOrSocket`.

## Synthesized by
<!-- backlinks:auto -->
- [data-structures/latch-waiteventset.md](../../../../data-structures/latch-waiteventset.md)

- [subsystems/storage-ipc.md](../../../../subsystems/storage-ipc.md)