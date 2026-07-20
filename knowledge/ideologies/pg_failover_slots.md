# pg_failover_slots — logical slots that survive a physical failover, via wire-vtable hijack

- **Repo:** github.com/EnterpriseDB/pg_failover_slots (branch `master`).
- **Fetched:** `README.md` (240 lines), `Makefile`, `pg_failover_slots.c`
  (1521 lines). There is **no** `.control` file and **no** SQL install script
  (see below).

## Domain & purpose

A logical replication slot lives only on the **primary**. When a physical
standby is promoted, the downstream logical subscribers' slots vanish, and the
new primary has already been free to recycle the WAL and advance `catalog_xmin`
that those subscribers still needed — an unrecoverable gap
(`README.md:3-11`). `pg_failover_slots` closes that gap by (1) **copying**
logical slots from primary to standby and keeping their positions in sync, (2)
**dropping** standby slots the primary no longer has, and (3) **holding back**
the primary's logical walsenders until the designated physical standbys have
durably flushed the same LSN — so a subscriber can never be ahead of the
failover target. This is a pre-PG-17 userspace backport of what core later
shipped natively as `synchronized_standby_slots` + slot sync.

## How it hooks into PG

It is a **pure `shared_preload_libraries` module** — `MODULE_big =
pg_failover_slots`, one object file, no `EXTENSION`/`.control`/SQL
(`Makefile:1-2`). `_PG_init` refuses to load outside preload
(`process_shared_preload_libraries_in_progress`, `pg_failover_slots.c:1432`).

Two mechanisms, on two node roles:

1. **A background worker on the standby.** `RegisterBackgroundWorker` with
   `bgw_start_time = BgWorkerStart_ConsistentState`, `bgw_restart_time = 60`,
   entry `pg_failover_slots_main` (`pg_failover_slots.c:1508-1516`). The worker
   connects to the primary (libpq, `SHLIB_LINK += $(libpq)`), reads its
   `pg_replication_slots`, and reproduces each matching slot locally by calling
   the **core slot API directly**: `ReplicationSlotCreate(... RS_EPHEMERAL)`,
   `ReplicationSlotReserveWal`, `LogicalConfirmReceivedLocation`,
   `ReplicationSlotMarkDirty` / `ReplicationSlotSave` / `ReplicationSlotPersist`
   (`synchronize_one_slot`, `pg_failover_slots.c:668-850`). Before persisting a
   freshly-created slot it blocks in `wait_for_primary_slot_catchup`
   (`:538`) until the standby's replay has actually reached the slot's
   `restart_lsn`/`catalog_xmin`, so a synced slot is never ahead of the data.

2. **Walsender output gating on the primary — by swapping the socket send
   vtable.** There is no core hook for "delay this walsender's output," so the
   module manufactures one:
   - It hooks `ClientAuthentication_hook` with `attach_to_walsender`
     (`pg_failover_slots.c:1519-1520`). That callback fires on every
     connection; when the new backend is a walsender (`am_db_walsender`) it
     does `OldPqCommMethods = PqCommMethods; PqCommMethods =
     &PqCommSocketMethods;` (`:1420-1423`) — replacing the process-global
     wire-protocol send vtable.
   - `PqCommSocketMethods` forwards every method to the saved originals except
     `putmessage_noblock` (`socket_putmessage_noblock`,
     `pg_failover_slots.c:1359-1385`): for a CopyData message (`'d'`) carrying a
     WAL record (`'w'`), it decodes the LSN out of the message bytes
     (`pg_ntoh64`) and calls `wait_for_standby_confirmation(lsn)` **before**
     letting the bytes go out on the socket.
   - `wait_for_standby_confirmation` (`:1191`) spins on `WaitLatch` until the
     physical standbys named in `standby_slot_names` have flushed past
     `commit_lsn` (or the `standby_slots_min_confirmed` quorum is met),
     re-reading config on SIGHUP and terminating the walsender on timeout
     (`:1300-1304`).

Config is eight GUCs registered in `_PG_init` (`pg_failover_slots.c:1436-1500`):
`standby_slot_names`, `standby_slots_min_confirmed`, `synchronize_slot_names`,
`drop_extra_slots`, `primary_dsn`, `worker_nap_time`, `maintenance_db`,
`version`. Slot filters are `key:value` (`name` / `name_like` / `plugin`)
parsed by a custom check-hook (`README.md:81-102`).

## Where it diverges from core idioms

- **It rewrites the wire-protocol send path from an extension.** Overwriting
  the global `PqCommMethods` vtable to interpose on every walsender CopyData
  frame (`pg_failover_slots.c:1421-1385`) is a reach far past the extension
  ABI — it depends on the exact CopyData/`'w'`-message byte layout and on
  `PqCommMethods` being a swappable global. This is the single most invasive
  hook in the corpus that still loads into an **unmodified** server (contrast
  [[knowledge/ideologies/spock]], which needs *patched core* to reach similar
  facilities). It also abuses `ClientAuthentication_hook` — an
  authentication-time hook — purely as a "walsender just started" trigger,
  ignoring the `status` argument.
- **A standby process mutates replication-slot shared state.** Core treats
  slots as owned by the node that created them; here a bgworker on the standby
  calls `ReplicationSlotCreate/Acquire/Persist` and takes
  `ReplicationSlotControlLock` in `LW_EXCLUSIVE`
  (`pg_failover_slots.c:797-804`) to publish slots the standby never opened a
  decoding session for. See [[knowledge/subsystems/replication]] and
  [[knowledge/idioms/replication-slot-advance]] for the invariants this leans
  on.
- **No catalog, no SQL surface.** Unlike almost every other extension in the
  corpus, its entire interface is GUCs + the `pg_replication_slots` view;
  there is nothing to `CREATE EXTENSION`. Observability of "is the standby
  ready?" is the indirect *"slot present and `active=false`"* signal
  (`README.md:28-60`).
- **Ordering physical-before-logical is a policy core did not have.** The
  whole `standby_slot_names` feature invents a happens-before edge between two
  replication streams that vanilla PG (pre-17) keeps independent.

## Notable design decisions

- **Fail-safe on the sync side, fail-closed on the gating side.** Slot sync
  refuses to persist a slot that would be ahead of standby replay
  (`wait_for_primary_slot_catchup`, `:538`), so a promoted standby's slots are
  always *behind-or-equal* — safe. The output gate, conversely, will
  `proc_exit(0)` the walsender on confirmation timeout
  (`pg_failover_slots.c:1300-1304`) rather than risk letting a subscriber
  overtake the failover target.
- **`IsBinaryUpgrade` early-out** (`pg_failover_slots.c:1503`) skips worker
  registration during `pg_upgrade`, where slot machinery must stay quiet.
- **Version-portable by `#if PG_VERSION_NUM`.** The `PQcommMethods` struct
  shape, `ReplicationSlotCreate` arity, and the ProcessUtility-adjacent paths
  are all bracketed for PG 11–18 (`socket_startcopyout` etc. only exist
  `< 140000`, `pg_failover_slots.c:1386-1400`).

## Links into corpus

- [[knowledge/subsystems/replication]] — slot lifecycle, `catalog_xmin`,
  `hot_standby_feedback` this module depends on.
- [[knowledge/architecture/replication]] — physical vs logical stream model
  that this glues together.
- [[knowledge/ideologies/spock]] — sibling EDB/pgEdge replication tech; Spock
  reaches the same failover-slot facilities but via *patched core*, whereas
  pg_failover_slots stays in `shared_preload_libraries`.
- [[knowledge/ideologies/pg_auto_failover]], [[knowledge/ideologies/pgactive]] —
  neighbouring HA/replication extensions for the "how much does it reach into
  core" spectrum.
- [[knowledge/idioms/background-worker-startup]] — the
  `RegisterBackgroundWorker` + `bgw_start_time` pattern used here.
- [[knowledge/idioms/guc-variables]] — the list-GUC check/assign-hook pattern
  (`check_standby_slot_names`, `pg_failover_slots.c:216`).

## Sources

- `https://raw.githubusercontent.com/EnterpriseDB/pg_failover_slots/master/README.md`
- `https://raw.githubusercontent.com/EnterpriseDB/pg_failover_slots/master/pg_failover_slots.c`
- `https://raw.githubusercontent.com/EnterpriseDB/pg_failover_slots/master/Makefile`

Confidence: `[verified-by-code]` for the vtable swap, bgworker registration,
slot-API calls, and GUC set; `[from-README]` for the operational
"standby ready" semantics.
