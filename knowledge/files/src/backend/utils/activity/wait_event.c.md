# `src/backend/utils/activity/wait_event.c`

- **Last verified commit:** `ef6a95c7c64`
- **Lines:** ~470
- **Source:** `source/src/backend/utils/activity/wait_event.c`

Wait-event reporting infra. Backends use `pgstat_report_wait_start(ev)`
before going to sleep/io/lock and `pgstat_report_wait_end()` after; this
writes a single uint32 into `MyProc->wait_event_info` that
`pg_stat_activity.wait_event` / `wait_event_type` reads.

Performance note from the file header: `*_wait_start/end` do **not**
check shmem availability — instead `MyProc` must already point to a
valid slot before the first call. Practical implication: never call
the reporters from startup paths that run before `InitProcess`.
[from-comment] (`wait_event.c:1-15`)

Categories (`WaitEventClass`): `LWLock`, `Lock`, `BufferPin`,
`Activity`, `Client`, `Extension`, `IPC`, `Timeout`, `IO`, `Injection`.
Specific events per category are auto-generated from
`wait_event_names.txt` via `generate-wait_event_types.pl`.

Custom wait events (PG17+): `WaitEventExtensionNew(name)` registers a
runtime-allocated wait-event id under the `Extension` class so
extensions don't need to claim a static slot. Names live in shmem.

## API

- `pgstat_report_wait_start(uint32 wait_event_info)`
- `pgstat_report_wait_end(void)`
- `pgstat_get_wait_event(uint32 wait_event_info)` →
  `(WaitEventClass, name)` for display.
