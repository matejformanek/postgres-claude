# `src/include/utils/wait_event.h`

**Pin:** `4b0bf0788b066a4ca1d4f959566678e44ec93422`

## Role

The wait-event reporting API. Each backend has a single `uint32 *
my_wait_event_info` pointer; the hot-path API is two inline
functions (`pgstat_report_wait_start` / `_end`) that atomically write
a 4-byte (class, event) code.

## Public API

[verified-by-code: lines 16-88]

- `pgstat_get_wait_event(info)` / `pgstat_get_wait_event_type(info)`
  — decode for display.
- Inline `pgstat_report_wait_start(info)` /
  `pgstat_report_wait_end()` — single 4-byte write through a
  `volatile uint32 *`; updates are atomic by virtue of being one
  aligned word [from-comment: lines 47-65].
- `pgstat_set_wait_event_storage` / `_reset_wait_event_storage` —
  redirect reporting to a different memory location (used by
  parallel workers so the leader can observe).
- Global: `uint32 *my_wait_event_info` [line 23].
- Extension API [lines 26-43]:
  `WaitEventExtensionNew(name)` — register an extension-class
  event (`PG_WAIT_EXTENSION` class).
  `WaitEventInjectionPointNew(name)` — register an
  injection-point event (`PG_WAIT_INJECTIONPOINT` class).
  Both return a `uint32 wait_event_info` usable with
  `pgstat_report_wait_start`.
- `GetWaitEventCustomNames(classId, &nwaitevents)` — enumerate
  registered extension events.

## Invariants

- **INV-ATOMIC-WRITE** [from-comment: lines 47-65] The 4-byte write
  to `*my_wait_event_info` is atomic; no lock needed. Validity
  before `MyProc` is initialized is guaranteed by pointing the
  global at local memory initially [from-comment: lines 62-64].
- **INV-PAIR** [inferred] Every `_start` must be followed by an
  `_end`. Mismatched pairs leave the backend showing a stale
  wait-event in `pg_stat_activity`.
- **INV-NO-TRACK-GUC** [from-comment: lines 58-61] Reporting is
  unconditional (no `track_activities` check); rationale is that
  the check would cost more than the report.
- **INV-NAME-COLLISION** [inferred] Extension and injection-point
  event names are interned in a shared dynamic hash; calling
  `WaitEventExtensionNew` with a previously-registered name returns
  the existing ID.

## Trust boundary (Phase D)

- Wait events are visible cross-role via `pg_stat_activity` (subject
  to the same `pg_read_all_stats` / role-owner check as the rest of
  the view). Class + name is generally non-sensitive but can leak
  the *shape* of a backend's work (e.g. "BufferRead" + activity
  text together suggest a sequential scan).
- Extension event names go into a process-wide shared hash; an
  extension can register tens of thousands of names — DoS-ish but
  bounded by available shared memory. No name-content validation
  (any UTF-8 string).
- `WaitEventInjectionPointNew` is in production builds, not just
  `USE_INJECTION_POINTS` — extensions can pre-register names that
  only fire when injection points are enabled.

## Cross-refs

- `utils/wait_classes.h` — class bit constants.
- `utils/wait_event_types.h` (generated from `wait_event_names.txt`)
  — built-in event enums.
- `utils/backend_status.h` — `PgBackendStatus` carries the
  surfaced view.

## Issues

- [ISSUE-DESIGN: `pgstat_report_wait_start` does not check
  `track_activities`; rationale is performance but means even when
  monitoring is "off", per-backend wait info is still written and
  cross-role-readable (low, design intent)] — lines 58-61.
- [ISSUE-API: extension event names are unbounded UTF-8; no length
  cap documented in header (low)] — line 42-44.
