# pg_squeeze — online bloat removal by logical decoding + relfilenode swap (the pure-server answer to pg_repack)

> Ideology note produced by the `pg-extension-anthropologist` cloud routine.
> Repo: `cybertec-postgresql/pg_squeeze` @ branch `master`. All `file:line`
> cites below point into that repo (not `source/`), since this doc
> characterizes an *external* extension's divergence from core idioms. Cites
> verified against the files fetched on 2026-06-09 (see Sources footer). Read
> alongside `[[knowledge/ideologies/pg_repack]]`, the extension it explicitly
> sets out to replace.

## Domain & purpose

pg_squeeze "removes unused space from a table and optionally sorts tuples
according to a particular index (as if `CLUSTER` were executed concurrently with
regular reads / writes). In fact we try to replace `pg_repack`"
(`README.md:1-4`) `[from-README]`. It rebuilds a bloated table into a fresh,
compact copy while concurrent DML keeps running, then atomically swaps the new
storage in. The README is unusually explicit about its thesis versus pg_repack
(`README.md:5-15`) `[from-README]`: pg_squeeze (1) implements the functionality
**purely server-side** (pg_repack uses both server and client code), and (2)
"utilizes recent improvements of PostgreSQL" — specifically **background
workers** for unattended scheduling and **logical decoding instead of triggers**
to capture concurrent changes. So where pg_repack and pg_squeeze share a goal,
they make opposite bets on *how* to observe the concurrent write stream: triggers
+ a client driver (pg_repack) vs an in-process logical-decoding session +
bgworkers (pg_squeeze). That contrast is the whole reason to document it.

## How it hooks into PG

pg_squeeze requires `wal_level = logical`, at least one replication slot, and
`shared_preload_libraries = 'pg_squeeze'` (`README.md:INSTALL`) `[from-README]` —
three cluster-level prerequisites pg_repack does not impose, all consequences of
the logical-decoding + bgworker design. It is `relocatable = false`,
`schema = 'squeeze'` (`pg_squeeze.control:5-6`) and uses the modern
`PG_MODULE_MAGIC_EXT(.name = "pg_squeeze", .version = "1.9.2")` form
(`pg_squeeze.c:66`) `[verified-by-code]`.

The surface:

- **SQL entry point** `squeeze_table()` — `PG_FUNCTION_INFO_V1(squeeze_table)`
  (`pg_squeeze.c:317-320`), which calls `squeeze_table_impl` →
  `squeeze_table_internal` (`:369-392`), the function that runs an entire
  decoding-build-apply-swap cycle synchronously inside one call.
- **Two background-worker roles** — a *scheduler* worker that reads a config
  table and submits tasks, and *squeeze* workers that do the rebuild
  (`worker.c:39-47`, `am_i_scheduler` at `:47`) `[verified-by-code]`, coordinated
  through a shmem `WorkerData` slot array (`worker.c:96-119`,
  `worker_shmem_size` at `:182`) installed via the `shmem_request_hook`
  (`worker.c:194-212`) `[verified-by-code]`.

Cross-ref `[[knowledge/subsystems/replication]]`,
`[[knowledge/idioms/bgworker-and-parallel]]`,
`[[knowledge/idioms/catalog-conventions]]`,
`.claude/skills/replication-overview/SKILL.md`,
`.claude/skills/gucs-bgworker-parallel/SKILL.md`.

## Where it diverges from core idioms

### 1. It drives a logical-decoding session in-process — the extension *is* the output consumer, with no named output plugin

Logical decoding is normally consumed by a separate output-plugin `.so`
(`pgoutput`, `wal2json`, …) over a replication connection. pg_squeeze instead
acquires a slot and builds a `LogicalDecodingContext` *inside the worker's own
backend* and reads the change stream directly: `setup_decoding`
(`pg_squeeze.c:95-97, 1005-1066`) does `ReplicationSlotAcquire(...)`, validates
`MyReplicationSlot->effective_xmin`/`confirmed_flush`, captures `restart_lsn`, and
`XLogBeginRead(ctx->reader, restart_lsn)` (`:1054-1066`) `[verified-by-code]`,
then `decode_concurrent_changes(ctx, end_of_wal, ...)` (`:2415`, `:2894`) replays
the captured DML onto the new table. There is no registered output-plugin name —
pg_squeeze plays both the decoder and the apply side within `squeeze_table()`.
This is a markedly different use of `knowledge/subsystems/replication`
than logical *replication*: the WAL stream is consumed transiently, by the same
process that produced the build, purely to catch up changes that landed during
the copy. Cross-ref `[[knowledge/subsystems/replication]]`,
`[[knowledge/architecture/wal]]`.

### 2. The capture mechanism is WAL, not triggers — the central pg_repack divergence

pg_repack installs an `AFTER` trigger + a log table on the target, and a client
process drains the log. pg_squeeze captures concurrent writes from the **WAL via
logical decoding**, so it adds no triggers, no log table, and no client round
trip; the "log" is the replication slot. The cost is the prerequisites in §How:
`wal_level = logical` cluster-wide and a slot budget. It also forces a
requirement pg_repack states differently: the table must have an **identity
index** (REPLICA IDENTITY DEFAULT/FULL via PK, or an explicit
`REPLICA IDENTITY USING INDEX`), because logical decoding needs the old-row key
to apply concurrent UPDATE/DELETEs to the new copy (`README.md:Register table`,
the PK/identity check at `pg_squeeze.c:458`) `[verified-by-code]`. Cross-ref
`[[knowledge/ideologies/pg_repack]]` (triggers + client), `pg_repack`'s log-table
drain vs pg_squeeze's slot drain — the cleanest A-vs-B in the ideologies set.

### 3. It reaches into a *static core function* by copying it out and paring it down

The final atomic swap is `swap_relation_files(r1, r2)` (`pg_squeeze.c:139,
3141`), whose header comment states it is "Derived from swap_relation_files() in
PG core, but removed anything we [don't need]" (`:3131-3141`) `[verified-by-code]`.
Core's `swap_relation_files` is `static` in `cluster.c` and not exported, so
pg_squeeze **re-implements it in the extension**: it opens `pg_class`, swaps
`relfilenode` + `reltablespace` + `reltoastrelid` between the two `Form_pg_class`
tuples under `RowExclusiveLock`, asserting matching `relpersistence`/`relam`
(`:3141-3185`) `[verified-by-code]`, and separately swaps each index's storage
(`:859-869`). This is a recurring extension-author tax the corpus has seen
elsewhere (cstore_fdw, pg_repack): the operation an extension needs lives behind
a `static` core boundary, so it gets duplicated into the extension and drifts
against core across versions. Cross-ref `[[knowledge/idioms/catalog-conventions]]`,
`[[knowledge/subsystems/access-heap]]` (relfilenode-swap is the same trick
`CLUSTER`/`VACUUM FULL` use to make a rebuild atomic).

### 4. A scheduler/worker pair makes maintenance unattended — VACUUM-FULL-like work without a maintenance window or a client

`VACUUM FULL`/`CLUSTER` take `AccessExclusiveLock`; pg_repack avoids that but
needs a client process to stay connected and drive the job. pg_squeeze pushes the
*whole* lifecycle into the server: a scheduler bgworker consults a config table
on a schedule and submits tasks; squeeze bgworkers pick them up and run
`squeeze_table()` (`worker.c:39-47`, `start_worker_internal` /
`scheduler_worker_loop` at `:161-167`) `[verified-by-code]`. The only
`AccessExclusiveLock` is the brief one for the catalog swap at the end. This is
the "recent improvements" payoff in the README — autonomous, client-less bloat
control. Cross-ref `[[knowledge/idioms/bgworker-and-parallel]]`,
`[[knowledge/ideologies/pg_cron]]` (another scheduler-bgworker extension; pg_cron
schedules arbitrary SQL, pg_squeeze schedules its own rebuild tasks).

## Notable design decisions (cited)

- **`pgstatapprox.c` is vendored in** (`pgstatapprox.c` in tree)
  `[verified-by-code]` — the scheduler uses an approximate bloat estimate to
  decide what to squeeze; this is the same `pgstattuple_approx` code the A12 sweep
  flagged for its fail-open VM trust (`knowledge/issues/pgstattuple.md`). So
  pg_squeeze inherits that "corrupt VM bits → wrong bloat estimate" caveat at its
  scheduling layer. Cross-ref `knowledge/issues/pgstattuple.md`.
- **The decode + build + apply + swap all run in one `squeeze_table()` call**
  (`pg_squeeze.c:392-869`) `[verified-by-code]` — it is not a long-lived
  replication consumer; the slot exists only for the duration of one rebuild, and
  `ReplicationSlotRelease()` (`:843`) drops the session before the swap. A crash
  mid-rebuild leaves the slot to be cleaned up, not a half-migrated table.
- **`replorigin` is used to filter pg_squeeze's own changes** — index changes are
  "not decoded … filtered out by their origin" (`pg_squeeze.c:2885`,
  `:2405-2415`) `[verified-by-code]`, so the apply loop doesn't re-capture the
  writes it is itself making to the new copy.
- **`relocatable = false`, fixed `schema = 'squeeze'`** (`pg_squeeze.control:5-6`)
  — its config tables and functions are schema-pinned, like pg_duckdb and unlike
  cstore_fdw.
- **`CheckTableNotInUse(rel, "squeeze_table()")`** (`pg_squeeze.c:998`) guards
  against squeezing a table with open cursors/refs, mirroring core's own
  rewrite guards.

## Links into corpus

- `[[knowledge/ideologies/pg_repack]]` — the head-to-head: same goal (online
  bloat removal / CLUSTER-without-the-lock), opposite mechanism (pg_repack =
  triggers + log table + client driver; pg_squeeze = logical decoding + slot +
  bgworkers, pure server-side).
- `[[knowledge/subsystems/replication]]` — pg_squeeze consumes a
  `LogicalDecodingContext` *in-process* with no named output plugin, a transient
  decode session per rebuild (`setup_decoding`, `decode_concurrent_changes`).
- `[[knowledge/idioms/bgworker-and-parallel]]` — the scheduler/squeeze worker
  pair + `shmem_request_hook` `WorkerData` slot array.
- `[[knowledge/idioms/catalog-conventions]]` + `[[knowledge/subsystems/access-heap]]`
  — `swap_relation_files` copied out of core's `static` function; relfilenode swap
  as the atomic-rebuild primitive.
- `[[knowledge/ideologies/pg_cron]]` — sibling scheduler-bgworker extension.
- `knowledge/issues/pgstattuple.md` — vendored `pgstatapprox.c` inherits the
  approximate-bloat / VM-trust caveat at the scheduling layer.
- `.claude/skills/replication-overview/SKILL.md`,
  `.claude/skills/gucs-bgworker-parallel/SKILL.md`.

## Anthropology takeaway

pg_squeeze is the corpus's cleanest "two extensions, one job, opposite means"
case. pg_repack answered "rebuild a table online" with the tools available
pre-logical-decoding (triggers + a client); pg_squeeze re-answers it with the
tools PostgreSQL grew afterward (logical decoding + dynamic bgworkers + the
`shmem_request_hook`), and the README frames itself explicitly as the successor.
**Phase-D relevance:** (a) `swap_relation_files` is yet another site where an
extension duplicates a `static` core function — the recurring "core's useful
internals aren't exported" pattern (cstore_fdw, pg_repack, hydra-columnar all hit
it); a survey of such copied-out statics is a concrete corpus deliverable. (b)
The in-process, no-named-plugin logical-decoding consumption is a usage pattern
worth a `knowledge/idioms` note: logical decoding as a *transient intra-backend
change-capture API*, not just a replication transport.

## Sources

Fetched 2026-06-09 (branch `master`):

- `https://api.github.com/repos/cybertec-postgresql/pg_squeeze/git/trees/master?recursive=1`
  @ 2026-06-09 → HTTP 200 (tree listing; README is `.md`, not `.rst`; no
  `concurrent.h`).
- `https://raw.githubusercontent.com/cybertec-postgresql/pg_squeeze/master/README.md`
  @ 2026-06-09 → HTTP 200 (15210 bytes).
- `https://raw.githubusercontent.com/cybertec-postgresql/pg_squeeze/master/pg_squeeze.control`
  @ 2026-06-09 → HTTP 200 (184 bytes).
- `https://raw.githubusercontent.com/cybertec-postgresql/pg_squeeze/master/pg_squeeze.h`
  @ 2026-06-09 → HTTP 200 (13082 bytes, skimmed).
- `https://raw.githubusercontent.com/cybertec-postgresql/pg_squeeze/master/pg_squeeze.c`
  @ 2026-06-09 → HTTP 200 (103373 bytes; squeeze_table, setup_decoding,
  swap_relation_files — cited regions deep-read, rest skimmed).
- `https://raw.githubusercontent.com/cybertec-postgresql/pg_squeeze/master/worker.c`
  @ 2026-06-09 → HTTP 200 (64815 bytes; scheduler/worker roles, shmem — skimmed).
- `https://raw.githubusercontent.com/cybertec-postgresql/pg_squeeze/master/concurrent.c`
  @ 2026-06-09 → HTTP 200 (22364 bytes, skimmed).

All cites are `[verified-by-code]` against the fetched `.c`/`.control` (entry
point, decoding setup + slot validation, `decode_concurrent_changes` apply,
`swap_relation_files` copied-from-core, worker roles + shmem hook, replorigin
filtering, module magic) except the pg_repack-comparison thesis, the
prerequisites narrative, and the identity-index rationale, which are
`[from-README]`. The change-apply internals (`concurrent.c`), the config/schedule
tables (`pg_squeeze--*.sql`), and `worker.c`'s task lifecycle were skimmed, not
deep-read; claims about *that* the scheduler reads a config table and *that* the
slot is transient rest on the call sites + README, tagged where they exceed a cite.
