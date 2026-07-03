---
source_url: https://www.postgresql.org/docs/current/recovery-config.html
fetched_at: 2026-07-03T20:47:00Z
anchor_sha: a5422fe3bd7e
distilled_by: pg-docs-miner (cloud routine)
docs_version: current (PG18)
primary: true
---

# recovery.conf → postgresql.conf (Appendix O)

The short appendix that explains **why** modern PG has no `recovery.conf` and uses
**signal files** instead. It's the migration/context note behind the
`standby.signal` / `recovery.signal` mechanism the whole physical-HA family
depends on. Explicitly relevant to `warm-standby-failover.md`, which notes the
old trigger-file path is gone.

## The change (PG12 removed recovery.conf)

- PG **≤ 11** configured archive recovery / streaming / PITR in a **separate
  `recovery.conf`** file; PG **12+** merged all of it into ordinary
  **`postgresql.conf`** parameters (settable via `ALTER SYSTEM`, `include`,
  reload, etc.). [from-docs]
- **A leftover `recovery.conf` now makes the server refuse to start** — it's a
  hard error, forcing the migration rather than silently ignoring the file.
  [from-docs]
- The old **`standby_mode = on`** parameter is replaced by the presence of a
  **`standby.signal`** file; targeted PITR is signaled by **`recovery.signal`**.
  The signal files are empty markers whose *presence* selects the mode; the
  startup process deletes the one it used when recovery ends. [from-docs] — see
  `knowledge/docs-distilled/continuous-archiving.md`,
  `knowledge/docs-distilled/warm-standby.md`.
- The old **`trigger_file` / `promote_trigger_file`** promotion path is
  deprecated/removed in favor of **`pg_ctl promote`** and the SQL
  **`pg_promote()`** function. [from-docs] — see
  `knowledge/docs-distilled/warm-standby-failover.md`.

## Why it matters for a hacker

- Any doc/tutorial that says "edit `recovery.conf`" or "set `standby_mode`" is
  **pre-12 and wrong** against the current tree. The recovery GUCs
  (`restore_command`, `recovery_target_*`, `primary_conninfo`, `primary_slot_name`,
  `archive_cleanup_command`, `recovery_end_command`, `recovery_min_apply_delay`)
  are all normal parameters now, living on `runtime-config-wal.md` (Archive
  Recovery / Recovery Target sections) and `runtime-config-replication.md`
  (Standby Servers section). [from-docs / inferred]
- Because they're normal GUCs, most take effect on **reload**; `primary_conninfo`
  / `primary_slot_name` changes restart the **walreceiver** to reconnect.
  [from-docs — noted on the config pages]

## Links into corpus

- `knowledge/docs-distilled/continuous-archiving.md` — `recovery.signal` +
  recovery-target GUCs in action.
- `knowledge/docs-distilled/warm-standby.md` — `standby.signal` continuous replay.
- `knowledge/docs-distilled/warm-standby-failover.md` — `pg_ctl promote` /
  `pg_promote()` replacing `promote_trigger_file`.
- `knowledge/docs-distilled/runtime-config-wal.md`,
  `.../runtime-config-replication.md` — where the merged GUCs now live.

## Citations

- All claims: source-URL anchor
  https://www.postgresql.org/docs/current/recovery-config.html (PG18, Appendix O).
- The list of which GUCs migrated is `[inferred]` from the appendix's pointers +
  the runtime-config pages; the appendix itself is short and mainly states the
  removal + signal-file replacement.
