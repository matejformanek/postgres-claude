# `src/include/storage/condition_variable.h`

- **Last verified commit:** `4b0bf0788b066a4ca1d4f959566678e44ec93422`
- **Lines:** 73

## Role

PG-native condition variable primitive — spinlock-protected
wakeup list (`proclist`), interruptible sleeps, DSM-safe (no
pointers in the struct itself). Used by walsender, walreceiver,
async-IO completion, parallel-query coordination, replication
slot signaling.

## Public API

[verified-by-code] `source/src/include/storage/condition_variable.h:28-71`

- `ConditionVariable { slock_t mutex; proclist_head wakeup; }`
  (lines 28-32)
- `ConditionVariableMinimallyPadded` — 16 or 32 byte pad to
  prevent cache-line crossings in arrays (lines 39-43)
- `ConditionVariableInit`
- `ConditionVariablePrepareToSleep` — optional, more efficient
  if a sleep is expected
- `ConditionVariableSleep(cv, wait_event_info)` — interruptible
- `ConditionVariableTimedSleep(cv, timeout_ms, wait_event_info)`
  — returns true on timeout
- `ConditionVariableCancelSleep` — required after exit
- `ConditionVariableSignal` (wake one),
  `ConditionVariableBroadcast` (wake all)

## Usage protocol

```c
ConditionVariablePrepareToSleep(cv);   // optional
for (;;)
{
    if (condition)
        break;
    ConditionVariableSleep(cv, WAIT_EVENT_FOO);
}
ConditionVariableCancelSleep();
```

[from-comment] lines 47-67.

## Invariants

- INV-1: **Spurious wakeups possible** — caller MUST re-check
  condition in the loop. [from-comment] line 51.
- INV-2: `ConditionVariableCancelSleep` MUST be called after
  exiting the loop, else the proc stays in the wakeup list and
  may receive stray signals. [from-comment] lines 53-54.
- INV-3: No pointers internally — safe in DSM. [from-comment]
  lines 13-14.
- INV-4: Mutex is a spinlock — interrupts must NOT fire while
  held (the spinlock rule from spin.h applies).

## Trust boundary (Phase D)

None directly — internal primitive. Misuse from extensions
(e.g. missing `CancelSleep`) leaks a proc onto the wakeup list
but doesn't escape the trust boundary.

## Cross-refs

- `knowledge/files/src/include/storage/spin.h.md` —
  underlying spinlock
- `knowledge/files/src/include/storage/proclist_types.h.md` (if
  exists) — wakeup list type
- `knowledge/files/src/include/storage/latch.h.md` (existing) —
  alternative wakeup mechanism

## Issues

None.
