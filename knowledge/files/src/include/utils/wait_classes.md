# `src/include/utils/wait_classes.h`

**Pin:** `4b0bf0788b066a4ca1d4f959566678e44ec93422`

## Role

Defines wait-event *class* IDs — the high byte of a 32-bit wait-event
code. The low 3 bytes pick a specific event within the class
[see `wait_event.h`].

## Public API

[verified-by-code: lines 18-27]

```c
#define PG_WAIT_LWLOCK         0x01000000U
#define PG_WAIT_LOCK           0x03000000U
#define PG_WAIT_BUFFER         0x04000000U
#define PG_WAIT_ACTIVITY       0x05000000U
#define PG_WAIT_CLIENT         0x06000000U
#define PG_WAIT_EXTENSION      0x07000000U
#define PG_WAIT_IPC            0x08000000U
#define PG_WAIT_TIMEOUT        0x09000000U
#define PG_WAIT_IO             0x0A000000U
#define PG_WAIT_INJECTIONPOINT 0x0B000000U
```

Class ID `0x02000000U` is intentionally absent (historically held
the merged `LOCK_EXTENSION` slot before reorganization).

## Invariants

- **INV-MASK** [inferred] Class occupies bits 31..24; event-id
  occupies bits 23..0 — gives 2^24 events per class.
- **INV-EXTENSION-SHARED** [verified-by-code: line 23 +
  `wait_event.h:42`] `PG_WAIT_EXTENSION` is one class shared by ALL
  loaded extensions; collisions on event names are resolved by the
  shared-dynamic-hash registry in `wait_event.c`.

## Trust boundary (Phase D)

- Class IDs are visible in `pg_stat_activity.wait_event_type` cross-
  role — same as `wait_event.h`. They're informational and don't
  carry sensitive content beyond "this backend is doing IO" etc.

## Cross-refs

- `utils/wait_event.h` — per-class event enums.
- `utils/wait_event_types.h` (generated) — full event taxonomy.

## Issues

- [ISSUE-DOC: `0x02` gap is not commented; future readers may
  wonder if they can claim it (low)] — line 19-20 gap.
