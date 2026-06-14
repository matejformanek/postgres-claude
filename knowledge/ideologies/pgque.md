# pgque — a message queue that achieves zero bloat by TRUNCATE-rotating event tables instead of deleting rows, ticked by an external scheduler

> Ideology note produced by the `pg-extension-anthropologist` cloud routine.
> Repo: `NikolayS/PgQue` @ branch `main`. All `file:line` cites below point into
> that repo (not `source/`), since this doc characterizes an *external*
> extension's divergence from core idioms. Cites verified against files fetched
> on 2026-06-13 (see Sources footer). PgQue is a pure-SQL/PL/pgSQL re-packaging
> of the Skype-era **PgQ** engine (`README.md:39-45`) `[from-README]`; the
> shipped artifact is one big `sql/pgque.sql` (~7100 lines) plus a small
> `sql/pgque-api/` layer (`send`/`receive`/`subscribe`) and an optional
> `sql/pgque-tle.sql` that wraps the same body for `pg_tle`. **Read alongside
> `[[knowledge/ideologies/pgmq]]`** — PgQue is a deliberate, advertised
> alternative to pgmq, contrasted at four named points below.

## Domain & purpose

PgQue is a "zero-bloat Postgres queue" — "the model is closer to Kafka (log)
than to ActiveMQ or RabbitMQ (task message queue). Shared event log, independent
per-consumer cursors, zero bloat under sustained load" (`README.md:3,18`)
`[from-README]`. Where pgmq gives SQS-style competing-consumer semantics, PgQue
gives a **shared event log** with one independent cursor per registered consumer:
every consumer sees every event (`README.md:102,114,128`) `[from-README]`. The
headline claim is the divergence worth documenting: most in-database queues
(pgmq, River, pg-boss, Que) use `SKIP LOCKED` + `UPDATE`/`DELETE`, which "turns
into dead tuples, VACUUM pressure, index bloat, and performance drift under
sustained load" (`README.md:61`) `[from-README]`. PgQue claims `n_dead_tup = 0`
across all `pgque.event_*` tables even under a pinned xmin horizon
(`README.md:431-438`) `[from-README]`. It reaches that by replacing per-row
deletion with **snapshot-based batching** + **TRUNCATE table rotation**
(`README.md:63`) `[from-README]` — the engineering core of this doc.

## How it hooks into PG

Like pgmq, it barely hooks at all — and the README brands it "the anti-extension"
(`README.md:47`) `[from-README]`. There is no `.c`, no `PG_MODULE_MAGIC`, no
`_PG_init`, no `shared_preload_libraries`, no `LANGUAGE C`; every routine is
`LANGUAGE plpgsql` or `sql` and the default install is a single transaction:
`\i sql/pgque.sql` or `psql --single-transaction -f sql/pgque.sql`
(`README.md:148-158`) `[from-README]`. It targets managed providers (RDS,
Aurora, Cloud SQL, AlloyDB, Supabase, Neon) precisely because nothing needs a
custom build or provider approval (`README.md:47`) `[from-README]`.

The runtime model is a fixed metadata schema plus per-queue data tables:

- `pgque.queue` — registry row per queue, carrying the rotation bookkeeping
  (`queue_cur_table`, `queue_ntables` default 3, `queue_rotation_period` default
  `'2 hours'`, `queue_switch_step1/step2`) (`sql/pgque.sql:95-122`)
  `[verified-by-code]`.
- `pgque.tick` — one row per tick, whose key column is
  `tick_snapshot pg_snapshot NOT NULL DEFAULT pg_current_snapshot()`
  (`sql/pgque.sql:136-146`) `[verified-by-code]`.
- `pgque.consumer` / `pgque.subscription` — name→id maps and per-consumer cursor
  state (`sub_last_tick`, `sub_next_tick`, `sub_batch`)
  (`sql/pgque.sql:61-67,169-184`) `[verified-by-code]`.
- `pgque.event_template` — parent table; each queue gets
  `pgque.event_<id>` inheriting it, with **three** physical data tables
  `pgque.event_<id>_0..2` that are rotated (`sql/pgque.sql:38-45,204-218`)
  `[verified-by-code]`. The critical column is
  `ev_txid xid8 NOT NULL DEFAULT pg_current_xact_id()` — kept as `xid8`
  specifically so `pg_visible_in_snapshot()` can be called on it
  (`sql/pgque.sql:208`) `[verified-by-code]`.

The modern API (`pgque-api/`) is a thin overload-and-delegate layer over PgQ
primitives: `receive()` wraps `next_batch` + `get_batch_events`, `ack()` is
`finish_batch`, `nack()` routes to retry or DLQ (`sql/pgque-api/receive.sql:28-77`)
`[verified-by-code]`; `send()` funnels every text/jsonb overload into one
`insert_event` (`sql/pgque-api/send.sql:104-143`) `[verified-by-code]`.

Cross-ref `[[knowledge/idioms/fmgr]]` (the C calling convention PgQue never
touches), the `extension-development` skill (control + SQL only).

## Where it diverges from core idioms

### 1. Pure SQL/PL/pgSQL, no C / `.so` / `_PG_init` — and a re-implementation of a former C extension

PgQ proper "depends on a C extension (`pgq`) and an external daemon (`pgqd`),
neither of which run on most managed Postgres providers" (`README.md:41`)
`[from-README]`. PgQue "rebuilds that battle-tested engine in pure PL/pgSQL"
(`README.md:43`) `[from-README]`. The install file annotates each transform from
the C-era original: `txid_current()` → `pg_current_xact_id()::text::bigint`,
`txid_snapshot` → `pg_snapshot`, and `queue_per_tx_limit` "removed (not supported
without C)" (`sql/pgque.sql:18-19`, `sql/pgque-tle.sql:104-111`)
`[verified-by-code]`. This is the same no-new-C pole as
`[[knowledge/ideologies/pgmq]]` and `[[knowledge/ideologies/index_advisor]]`,
but reached by *porting away from* C rather than never having it.

### 2. Zero bloat by TRUNCATE rotation over three inherited tables — not UPDATE-in-place, and the sharpest contrast with pgmq

This is the headline divergence. A queue's events live in three inheritance-child
tables `event_<id>_0..2`; only one is "current" at a time
(`sql/pgque.sql:38-45,99-100`) `[verified-by-code]`. `maint_rotate_tables_step1`
advances `queue_cur_table` to the next table modulo `queue_ntables` and empties
it with `TRUNCATE` — `execute 'lock table ' || tbl || ' nowait'` then
`execute 'truncate ' || tbl` (`sql/pgque.sql:931-947`) `[verified-by-code]`.
Because old events are dropped en masse by `TRUNCATE` (which resets the relation
to a new empty file, producing **no dead tuples**) rather than per-row `DELETE`,
the hot path never accumulates dead tuples — the `n_dead_tup = 0` claim
(`README.md:431-438`) `[from-README]`. Rotation only fires when the slowest
consumer has passed off the table: it computes `min(sub_last_tick)` across
subscriptions and bails (`return 0; -- skip rotation`) if that consumer's tick
snapshot xmin is still `<= queue_switch_step2` (`sql/pgque.sql:909-927`)
`[verified-by-code]`. A `pg_dump`'s `ACCESS SHARE` lock is detected via the
`LOCK ... NOWAIT` and rotation is skipped rather than blocked
(`sql/pgque.sql:938-947`) `[verified-by-code]`.

**Contrast with pgmq #1:** pgmq's `read` does
`UPDATE ... SET vt = ..., read_ct = read_ct + 1 ... RETURNING`
(`[[knowledge/ideologies/pgmq]]` §2) — every read writes a row, every
delete/archive removes one, so the live table churns dead tuples and pgmq must
ship aggressive autovacuum settings (`README.md:126`) `[from-README]`. PgQue's
read path writes **nothing** to the event tables; reclamation is a periodic
bulk `TRUNCATE` of a whole rotation table.

### 3. Batch visibility computed by diffing two transaction snapshots — MVCC repurposed as a queue cursor

PgQue does not mark messages "claimed." A `tick` snapshots committed-xid state
(`tick_snapshot pg_snapshot DEFAULT pg_current_snapshot()`,
`sql/pgque.sql:140`). A consumer's batch is the set of events *committed between
its last tick snapshot and the next*: the generated batch query filters
`pg_visible_in_snapshot(ev.ev_txid, cur.tick_snapshot)
AND NOT pg_visible_in_snapshot(ev.ev_txid, last.tick_snapshot)`
(`sql/pgque.sql:420-421`) `[verified-by-code]`, with `[xmax1..xmax2]` range
bounds plus an `IN (...)` list for long-running transactions still in-flight at
the previous snapshot (the two optimizations documented at
`sql/pgque.sql:335-348,378-397`) `[verified-by-code]`. So "exactly-once per
consumer" is delivered by **set algebra over MVCC snapshots**, not by row locks
or a visibility-timeout column. The hard consequence surfaced in the README:
`send`, `tick`, and `receive` must be in *separate* transactions, because a tick
records a snapshot in which a same-xact `send` is still in-progress and would be
excluded forever (`README.md:325`) `[from-README]`. Cross-ref
`[[knowledge/architecture/mvcc]]`, `[[knowledge/idioms/locking-overview]]`.

### 4. `SKIP LOCKED` is *absent* from the hot path — it appears once, only in the experimental cooperative-consumer steal path

This is the inverse of pgmq, where `FOR UPDATE SKIP LOCKED` *is* the engine.
PgQue's send/tick/receive/ack flow uses plain `FOR UPDATE` on single metadata
rows for cursor bookkeeping (e.g. `next_batch`, `sql/pgque.sql:986,1541,1824`)
`[verified-by-code]`, never `SKIP LOCKED` — because consumers are not competing
for the same rows; each has its own cursor on the shared log. The **only**
`FOR UPDATE SKIP LOCKED` in the entire codebase is in the experimental
cooperative-consumer "work-stealing" path, where a live subconsumer steals a
dead peer's batch (`sql/pgque.sql:6262`,
`sql/pgque-api/cooperative_consumers.sql`) `[verified-by-code]`.

**Contrast with pgmq #2:** the README's own death-spiral framing
(`docs/images/death_spiral.gif`, "the failure mode PgQue avoids by construction",
`README.md:14`) `[from-README]` is aimed squarely at the `SKIP LOCKED` queue
class pgmq belongs to. PgQue's thesis is that `SKIP LOCKED` per-row claiming is
the *source* of the bloat, so it removes it from the hot path entirely.

### 5. No background worker of its own — ticking is outsourced to pg_cron (or pg_timetable, or you)

PgQ needed the `pgqd` daemon; PgQue needs *something* to call `pgque.ticker()`
periodically and ships no bgworker. The blessed driver is **pg_cron**:
`pgque.start()` raises if `pg_cron` is absent (`sql/pgque.sql:4245-4249`)
`[verified-by-code]` and schedules four jobs via `cron.schedule_in_database`:
ticker every `'1 second'`, retry every `'30 seconds'`, maint every `'30 seconds'`,
and rotate-step2 every `'10 seconds'` (`sql/pgque.sql:4268-4302`)
`[verified-by-code]`. Sub-second cadence inside pg_cron's 1-second minimum is
achieved by a procedure trick: `pgque.ticker_loop()` is a `PROCEDURE` (not a
function) so it can `COMMIT` between iterations, looping `pgque.ticker()` every
`tick_period_ms` (default 100 ms = 10 ticks/sec) within one slot, each tick in
its own transaction so the per-iteration xmin is released and rotation isn't
blocked (`sql/pgque.sql:4142-4205`) `[verified-by-code]`. `tick_period_ms` is
constrained to an exact divisor of 1000 in `[1..1000]`
(`sql/pgque.sql:3958-3963,4221-4228`) `[verified-by-code]`. Without pg_cron the
extension still installs; you must run `ticker()`/`maint()`/`maint_retry_events()`
yourself, and "PgQue does not deliver messages without a working ticker"
(`README.md:206-216`) `[from-README]`.

**Contrast with pgmq #3:** pgmq needs *no* external scheduler — visibility
timeouts expire on their own clock and re-deliver lazily on the next `read`
(`[[knowledge/ideologies/pgmq]]` §2). PgQue trades that self-driving property for
the zero-bloat snapshot model, and pays for it with a hard external-scheduler
dependency and a tick-period delivery latency (median ~52 ms at the 100 ms
default, `README.md:77,89`) `[from-README]`. The rotation step1/step2 split is
itself a two-transaction requirement: step2 stamps the txid only after step1
committed and is "called in separate transaction" (`sql/pgque.sql:974-988`,
scheduled as a distinct 10-second job) `[verified-by-code]`.

### 6. A second install path: `pg_tle` packaging instead of filesystem `.control`/`.sql`

PgQue ships an opt-in path that registers it as a *real* `CREATE EXTENSION`
target without a filesystem `.control`/`.sql` pair. `sql/pgque-tle.sql` calls
`pgtle.install_extension('pgque', '0.2.0', <description>, <body>)` where the
entire ~7000-line install script is passed as a dollar-quoted **string literal**
(`sql/pgque-tle.sql:84-88` onward) `[verified-by-code]`; the user then runs
`create extension pgque`. This is a genuine divergence from the classic
extension model: the SQL "lives" inside a `pgtle.available_extensions()` catalog
row rather than `$SHAREDIR/extension/`, which is why it works on managed
providers that forbid filesystem access. The README is explicit about the
trade: pg_tle gives `pg_extension` membership, `alter extension pgque update`,
and `drop extension pgque cascade`, but "pg_tle is itself a C extension preloaded
via `shared_preload_libraries`, which is the dependency the default install
avoids" (`README.md:220-224`) `[from-README]`. The TLE wrapper also version-gates
re-registration (raises if a different version is already registered, since
"pg_tle has no managed upgrade path between unrelated registrations",
`sql/pgque-tle.sql:60-82`) `[verified-by-code]`.

### 7. LISTEN/NOTIFY push wakeups injected into the ticker

Each `pgque.ticker()` variant emits
`perform pg_notify('pgque_' || i_queue_name, i_tick_id::text)` after recording a
tick (`sql/pgque.sql:688,793,5190`) `[verified-by-code]` — annotated as a "PgQue
transformation: LISTEN/NOTIFY wakeup (not in original PgQ)". Consumers
`LISTEN pgque_<queue_name>` to be woken on the next tick rather than polling
(`sql/pgque-additions/notify.sql:1-12`) `[verified-by-code]`. Because the NOTIFY
channel is `'pgque_' || queue_name`, `create_queue()` rejects names whose channel
would exceed Postgres's 63-byte identifier limit (`sql/pgque.sql:256-257,1456-1462`)
`[verified-by-code]`. The README flags the global 8 GiB NOTIFY SLRU as a
high-tick-rate caveat (`README.md:198`) `[from-README]`. This mirrors pgmq's
LISTEN/NOTIFY push (`[[knowledge/ideologies/pgmq]]` §6) but is driven by the tick
clock rather than a per-insert constraint trigger.

## Notable design decisions (cited)

- **Producer/consumer roles are siblings, not parent/child.** `pgque_reader`
  (consume) and `pgque_writer` (produce) are independent; `pgque_admin` is a
  member of both, and an app that both produces and consumes must be granted
  both explicitly (`README.md:248-254`) `[from-README]`. The API files enforce
  this with explicit `revoke ... from public` + per-role grants and a
  deny-by-default second pass (`sql/pgque-api/send.sql:329-362`,
  `sql/pgque-api/receive.sql:154-159`) `[verified-by-code]`.
- **`send` text vs jsonb overloads with a deliberate resolution rule.** Untyped
  literals resolve to `send(text, text)` (no canonicalization, key order
  preserved, NUL-bytes rejected by `text`); `::jsonb` opts into validation +
  canonical storage; both store into `ev_data TEXT`
  (`sql/pgque-api/send.sql:13-29`) `[verified-by-code]` — overload-and-delegate
  to one `insert_event`, like pgmq's `send` funnel.
- **`nack` re-queries the canonical event from the batch** rather than trusting
  caller-supplied composite fields, to stop a consumer forging DLQ rows (fix
  #98), and `event_dead()` is idempotent via `ON CONFLICT` (fix #104)
  (`sql/pgque-api/receive.sql:80-139`) `[verified-by-code]` — a security-conscious
  divergence from a naive "trust the row you were handed" API.
- **Retry/DLQ are first-class tables**, not visibility-timeout re-delivery: the
  README explicitly contrasts "Built-in retry with backoff" and "Built-in dead
  letter queue" against pgmq's `⚠️ partial` (`README.md:103-104,113`)
  `[from-README]`; `nack` routes to `event_retry` (delayed re-insert) or
  `event_dead` past `queue_max_retries` (default 5)
  (`sql/pgque-api/receive.sql:100-136`) `[verified-by-code]`.
- **Ticks deliberately kept "big."** `maint_rotate_tables_step1` keeps stale
  `pgque.tick` rows for one extra rotation period on purpose — "we want the
  pgque.tick table to be big, to avoid Postgres accidentally switching to
  seqscans" and to allow rewinding consumers for disaster recovery
  (`sql/pgque.sql:957-967`) `[verified-by-code]`.

## Links into corpus

- `[[knowledge/ideologies/pgmq]]` — **the mandatory contrast.** Same no-new-C
  pole, opposite queue model: pgmq = competing consumers via
  `FOR UPDATE SKIP LOCKED` + `UPDATE`/`DELETE` (dead tuples, autovacuum tuning);
  PgQue = shared log via two-snapshot diff + `TRUNCATE` rotation (zero dead
  tuples, external tick). pgmq self-drives on visibility timeouts; PgQue needs
  pg_cron.
- `[[knowledge/ideologies/pg_cron]]` — the scheduler PgQue depends on for
  ticking and maintenance; `pgque.start()` schedules four jobs via
  `cron.schedule_in_database` and raises if pg_cron is absent. PgQue is a clean
  example of extension-composing-extension (cf. pgmq → pg_partman).
- `[[knowledge/idioms/locking-overview]]` — the `SKIP LOCKED` idiom PgQue
  *avoids* in the hot path (using plain `FOR UPDATE` on metadata rows), present
  only in the experimental coop-consumer steal path. The most instructive
  cross-reference for "what core idiom did this extension reject."
- `[[knowledge/architecture/mvcc]]` — `pg_current_snapshot()` /
  `pg_visible_in_snapshot()` / `pg_snapshot_xip()` repurposed as the batch-cursor
  primitive; `ev_txid xid8` exists solely to feed `pg_visible_in_snapshot`.
- `[[knowledge/idioms/catalog-conventions]]` — table inheritance for rotation,
  `pg_extension` probes for pg_cron, and the `pg_tle` `available_extensions()`
  catalog as an alternative to `$SHAREDIR/extension/`.
- `[[knowledge/architecture/wal]]` — tick cadence is a continuous-WAL trade-off
  the README tunes around (idle backoff toward `ticker_idle_period`).
- `.claude/skills/extension-development/SKILL.md` — PgQue + pgmq together bracket
  the minimal-surface end of the spectrum, and PgQue adds the `pg_tle` packaging
  variant as a third install model alongside PGXS and meson.

## Anthropology takeaway

PgQue is the corpus's cleanest case of an extension whose entire identity is a
**rejection of one core idiom in favor of another**: it discards
`FOR UPDATE SKIP LOCKED` per-row claiming — the mechanism pgmq and most
SQL-on-Postgres queues are built on — because that mechanism's by-product is dead
tuples, and substitutes (a) `TRUNCATE`-based rotation of three inherited event
tables for reclamation and (b) a two-snapshot `pg_visible_in_snapshot` diff for
per-consumer batch visibility. The sharpest single divergence is mechanism #2/#3:
reclamation is a bulk `TRUNCATE` of a whole rotation table gated on the slowest
consumer's snapshot xmin (`sql/pgque.sql:909-947`), so the hot path never writes
a dead tuple — the inverse of an `UPDATE`/`DELETE` queue. The sharpest
pgmq-vs-PgQue contrast follows directly: **pgmq claims rows with `FOR UPDATE SKIP
LOCKED` and reclaims with per-row `DELETE`/archive (churning dead tuples,
requiring tuned autovacuum), while PgQue never locks the event rows at all —
each consumer reads its slice by snapshot-diff and reclamation happens by
`TRUNCATE` rotation, trading pgmq's self-driving visibility timeouts for a hard
pg_cron tick dependency and ~half-a-tick delivery latency.** For Phase-D /
review work, two things are worth flagging: the `EXECUTE format(...)` dynamic-SQL
batch query (`sql/pgque.sql:405-436`) is a candidate for the same injection-audit
lens applied to pgmq's dynamic DDL; and the `pg_tle` install path means a "is
this a real extension?" check must consult `pgtle.available_extensions()`, not
just `$SHAREDIR/extension/` — a packaging divergence the corpus had not yet
recorded.

## Sources

Fetched 2026-06-13 (branch `main`):

- `https://raw.githubusercontent.com/NikolayS/PgQue/main/README.md`
  @ 2026-06-13 → HTTP 200 (34064 bytes; full read — model, comparison table,
  install paths, tick-rate, pg_tle, roles, benchmarks).
- `https://raw.githubusercontent.com/NikolayS/PgQue/main/sql/pgque.sql`
  @ 2026-06-13 → HTTP 200 (259935 bytes; the full install script — tables,
  snapshot-diff batch query, rotation step1/step2, ticker/ticker_loop, start(),
  pg_notify injection. Read in sections, not line-by-line.).
- `https://raw.githubusercontent.com/NikolayS/PgQue/main/sql/pgque-api/send.sql`
  @ 2026-06-13 → HTTP 200 (15549 bytes; send/send_batch/subscribe overloads +
  grants).
- `https://raw.githubusercontent.com/NikolayS/PgQue/main/sql/pgque-api/receive.sql`
  @ 2026-06-13 → HTTP 200 (6373 bytes; receive/ack/nack, DLQ routing, role
  split).
- `https://raw.githubusercontent.com/NikolayS/PgQue/main/sql/pgque-api/cooperative_consumers.sql`
  @ 2026-06-13 → HTTP 200 (39676 bytes; experimental subconsumer / work-steal
  path — skimmed for the lone `SKIP LOCKED` site).
- `https://raw.githubusercontent.com/NikolayS/PgQue/main/sql/pgque-tle.sql`
  @ 2026-06-13 → HTTP 200 (263705 bytes; `pgtle.install_extension` wrapper around
  the full body — read the registration header, body is the same as pgque.sql).
- `https://raw.githubusercontent.com/NikolayS/PgQue/main/sql/pgque-additions/notify.sql`
  @ 2026-06-13 → HTTP 200 (419 bytes; documents the pg_notify post-transform).
- `https://raw.githubusercontent.com/NikolayS/PgQue/main/docs/README.md`
  @ 2026-06-13 → HTTP 200 (1599 bytes; docs index — confirms tutorial/reference/
  concepts structure).

All cites are `[verified-by-code]` against the fetched `pgque.sql` /
`pgque-api/*.sql` / `pgque-tle.sql` (table layout, TRUNCATE rotation gate,
two-snapshot batch diff, ticker_loop COMMIT trick, cron.schedule_in_database,
pg_notify injection, pg_tle install_extension wrapper, role grants) except the
zero-bloat/no-dead-tuple benchmark claims, the Kafka-vs-SQS framing, the
managed-provider list, the latency numbers, and the PgQ heritage, which are
`[from-README]`. The `benchmark/`, `docs/*.md` (beyond the index),
`blueprints/SPECx.md`, the client libraries, and the uninstall scripts were not
read.
