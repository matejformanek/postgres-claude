# pg_amqp — ideology / divergence-from-core notes

> Extension: `omniti-labs/pg_amqp` @ `master` (tree sha `240d477`). Control
> reports `default_version = '0.4.2'`, `module_pathname = '$libdir/pg_amqp'`,
> `relocatable = false`, `schema = amqp`
> `[verified-by-code: amqp.control:3-6]`. ~214★, C. One durable "how this
> diverges from core PG design" doc. All `file:line` cites point into the
> **pg_amqp tree** (`src/pg_amqp.c`, `sql/functions/functions.sql`,
> `sql/tables/tables.sql`, `amqp.control`, `Makefile`,
> `src/librabbitmq/amqp_socket.c`), **NOT** into PG `source/`.
> Confidence tags: `[verified-by-code]` `[from-README]` `[from-comment]`
> `[inferred]` `[unverified]`.
>
> **Sibling note:** read this against the other two "PG reaches OUT to the
> network" bridges in the corpus, [[knowledge/ideologies/pg_net]] and
> [[knowledge/ideologies/pgsql-http]]. All three perform an outbound,
> non-MVCC, non-WAL side effect from inside PG. They diverge on *when and
> where* the I/O happens:
> - **pgsql-http** — synchronous, blocking `libcurl` call **inline in the
>   calling backend**, effect happens mid-statement and is *not* tied to
>   commit (a ROLLBACK does not un-send the HTTP request).
> - **pg_net** — fully **asynchronous**: the SQL function only `INSERT`s a
>   queue row and returns an id; a shared background worker drives the
>   non-blocking I/O later.
> - **pg_amqp** — a third model neither of the above uses:
>   **synchronous-send-but-transactional**. `amqp.publish` *immediately*
>   writes the message to the broker socket from the calling backend
>   (blocking, like pgsql-http), BUT does so on an **AMQP server-side
>   transaction channel** (`tx_select`), and a `RegisterXactCallback` hook
>   issues `amqp_tx_commit` / `amqp_tx_rollback` to the broker at PG
>   COMMIT / ABORT. So the message *bytes* leave the backend during the
>   statement, yet the broker only *releases* them when the PG transaction
>   commits — and a PG ROLLBACK genuinely cancels delivery. This is the
>   one outbound bridge whose external effect honours PG transaction
>   semantics. `[verified-by-code: src/pg_amqp.c:96-137, 215-220, 349]`

## Domain & purpose

pg_amqp lets a SQL statement publish messages to an **AMQP 0-8 broker**
(RabbitMQ) directly from inside the backend
`[from-README: README.md:4-5]`. The user surface is four SQL-callable C
functions in the `amqp` schema — `amqp.publish`, `amqp.autonomous_publish`,
`amqp.exchange_declare`, `amqp.disconnect`
`[verified-by-code: sql/functions/functions.sql:1-72]` — plus one config
table, `amqp.broker`, holding broker coordinates
`[verified-by-code: sql/tables/tables.sql:1-9]`. The pitched use is
event-out-of-the-database: a trigger or stored proc fires
`SELECT amqp.publish(broker_id, 'amq.direct', 'foo', 'message')` and the
message lands on the broker if and only if the surrounding transaction
commits `[from-comment: sql/functions/functions.sql:63-71]`.

The interesting anthropology is the **transactional-delivery contract**.
Core PG's transaction machinery governs *local, WAL-logged, MVCC* state;
an AMQP publish is an external side effect with no rollback of its own.
pg_amqp bridges the two by leaning on a *second* transaction system — the
broker's own `tx.select` / `tx.commit` / `tx.rollback` channel mode — and
slaving it to PG's `XactCallback`. That single design choice drives nearly
every divergence below.

## How it hooks into PG

- **Load model.** Shared library loaded via
  `shared_preload_libraries = 'pg_amqp.so'` `[from-README: README.md:62]`,
  then `CREATE EXTENSION amqp` `[from-README: README.md:67]`. The single
  `_PG_init` does exactly one thing: `RegisterXactCallback(amqp_local_phase2,
  NULL)` `[verified-by-code: src/pg_amqp.c:135-137]`. See
  [[knowledge/idioms/guc-variables]] (load-timing) and
  [[knowledge/idioms/catalog-conventions]].
- **The four C functions** are declared `LANGUAGE C IMMUTABLE` (publish /
  autonomous_publish / exchange_declare) and `IMMUTABLE STRICT` (disconnect),
  each `PG_FUNCTION_INFO_V1`
  `[verified-by-code: sql/functions/functions.sql:12-13, 22-23, 41-42, 60-61;
  src/pg_amqp.c:244, 356, 362, 368]`. `IMMUTABLE` on a function with an
  external network side effect is itself a divergence (see #5). See
  [[knowledge/idioms/fmgr]].
- **`amqp.broker` config table** — `broker_id serial`, `host`, `port`
  (default 5672), `vhost`, `username`, `password`, PK `(broker_id, host,
  port)` `[verified-by-code: sql/tables/tables.sql:1-9]`. Marked for
  dump via `pg_extension_config_dump` so user-entered broker rows survive
  `pg_dump` of an extension-owned table
  `[verified-by-code: sql/tables/tables.sql:11-12]`. The C side reads it
  with SPI at connect time (see #3).
- **Vendored librabbitmq.** A full AMQP client library
  (`src/librabbitmq/`, MPL-licensed, ~11 `.c`/`.h` files) is committed
  in-tree and compiled into the same `.so` via PGXS `MODULE_big`
  `[verified-by-code: Makefile:12-16]`. No external link dependency; the
  socket, framing, and protocol code all run inside the backend process
  `[verified-by-code: src/librabbitmq/amqp_socket.c:23-84]`.
- **Build = PGXS** (`include $(PGXS)`), with the install SQL assembled by
  `cat`-ing `sql/tables/*.sql` + `sql/functions/*.sql` into
  `sql/amqp--$(EXTVERSION).sql` at build time
  `[verified-by-code: Makefile:19-31]`. `@extschema@` placeholders are
  substituted by `CREATE EXTENSION`. Versioned upgrade scripts live in
  `updates/*--*.sql` `[verified-by-code: Makefile:24]`.

## Where it diverges from core idioms

### 1. Transactional message delivery via XactCallback + broker-side tx channel — the headline

pg_amqp's defining move: `amqp.publish` is **not** a fire-and-forget send,
and (correcting a common assumption) it is **not** a PG-side in-memory
buffer flushed at commit either. The message bytes are written to the
broker *immediately* inside the calling statement via `amqp_basic_publish`
`[verified-by-code: src/pg_amqp.c:331-336]` — but on **channel 2**, which
is opened in AMQP transaction mode at connect time via `amqp_tx_select`
`[verified-by-code: src/pg_amqp.c:209-220]`. Each publish on channel 2
increments `bs->uncommitted` `[verified-by-code: src/pg_amqp.c:348-349]`.
The broker holds those messages pending until told to commit.

The PG transaction boundary is bridged by the registered callback
`amqp_local_phase2(XactEvent, void*)`:
- on `XACT_EVENT_COMMIT`, for each broker with `uncommitted > 0` it calls
  `amqp_tx_commit(bs->conn, 2, ...)` — releasing the buffered messages on
  the broker `[verified-by-code: src/pg_amqp.c:100-113]`;
- on `XACT_EVENT_ABORT`, it calls `amqp_tx_rollback(bs->conn, 2, ...)` —
  the broker **discards** the pending messages, so a PG ROLLBACK truly
  cancels delivery `[verified-by-code: src/pg_amqp.c:114-127]`;
- `XACT_EVENT_PREPARE` is a no-op — two-phase commit is explicitly
  unsupported `[verified-by-code: src/pg_amqp.c:128-131]`.

This is a genuine ideological inversion of the sibling bridges: core PG
offers no hook to make an *external* effect atomic with a local commit, and
pgsql-http / pg_net both deliberately decouple the effect from commit.
pg_amqp instead delegates atomicity to a *second* transaction manager (the
broker) and yokes the two commit points together at `XACT_EVENT_COMMIT`.
The seam is visible and lossy: the tx_commit to the broker happens *after*
PG has already committed locally, so if `amqp_tx_commit` fails the code can
only `elog(WARNING, "amqp could not commit tx mode ...")` and drop the
connection — the PG transaction is already durable
`[verified-by-code: src/pg_amqp.c:105-110]`. It is best-effort
post-commit, not a true distributed commit. The function comment is candid:
"Under certain circumstances, the AMQP commit might fail. In this case, a
WARNING is emitted" `[from-comment: sql/functions/functions.sql:63-71]`.
Cross-ref core's `RegisterXactCallback` / `XactEvent` in
`src/backend/access/transam/xact.c`.

`amqp.autonomous_publish` is the escape hatch: it publishes on **channel 1**
(a plain, non-tx channel) so the message is sent unconditionally,
irrespective of PG transaction state — a deliberate bypass of #1
`[verified-by-code: src/pg_amqp.c:362-366, 287; from-comment:
sql/functions/functions.sql:15-18]`.

### 2. A persistent broker-connection cache living in process-global state across the whole backend lifetime

Connection state is a hand-rolled singly-linked list rooted at a **static
global** `HEAD_BS`, not a MemoryContext-scoped structure
`[verified-by-code: src/pg_amqp.c:83]`. Each `struct brokerstate` (broker
id, `amqp_connection_state_t conn`, raw `sockfd`, `uncommitted` /
`inerror` counters, list `next`) is allocated in **`TopMemoryContext`** so
it outlives any query, transaction, or portal
`[verified-by-code: src/pg_amqp.c:73-81, 145-149]`. A connection, once
established, "live[s] until the PostgreSQL backend terminated"
`[from-comment: sql/functions/functions.sql:25-30]`. There is no shared
memory and no background worker — the cache is strictly per-backend
process-local. This is the opposite of core's discipline where almost all
state is context-scoped and reclaimed at transaction or query end; here the
TCP connection and its broker-side tx channel must persist *precisely
because* they straddle statements and transactions (a single backend may
publish across many transactions over one long-lived broker socket). See
[[knowledge/idioms/memory-contexts]] (the `TopMemoryContext` /
process-global escape from the normal context hierarchy).

### 3. Broker connection config lives in a regular SQL table, read via SPI on the connect path

Rather than GUCs or a config file, broker coordinates live in the
`amqp.broker` *table* `[verified-by-code: sql/tables/tables.sql:1-9]`. On
the first publish to a broker id, `local_amqp_get_bs` opens an SPI
connection and runs a literal `SELECT host, port, vhost, username, password
FROM amqp.broker WHERE broker_id = %d ORDER BY host DESC, port`
`[verified-by-code: src/pg_amqp.c:151-163]`. Multiple rows for one
`broker_id` are treated as **failover hosts**: the code round-robins via
`bs->idx = (bs->idx + 1) % SPI_processed` and, on a connect failure,
`goto retry`s to the next row until `tries` is exhausted
`[verified-by-code: src/pg_amqp.c:164-237]`. Two consequences worth
flagging: (a) the broker id is interpolated into the SQL with `snprintf`
`%d` — safe only because it is an `int32` arg, not text
`[verified-by-code: src/pg_amqp.c:159-162; inferred]`; (b) config is
MVCC-versioned and dump/restore-safe (#How-it-hooks), which a GUC would
not be. Pulling network endpoints out of a *queried table* on the I/O hot
path — SPI inside a publish — is itself unusual; core subsystems that need
endpoints (e.g. postgres_fdw) read them from catalog options, not a
user-DML table re-queried per (re)connect. See
[[knowledge/idioms/catalog-conventions]] and [[knowledge/idioms/fmgr]]
(SPI usage).

### 4. Blocking socket I/O to an external broker inside the backend, with only a coarse SO_*TIMEO and no CHECK_FOR_INTERRUPTS

The vendored librabbitmq talks to the broker over a plain blocking TCP
socket. `amqp_open_socket` does a non-blocking `connect` with a `poll`
bounded by a 2-second timeout, then **switches the socket back to blocking**
and sets `SO_RCVTIMEO` / `SO_SNDTIMEO` to that same 2 s
`[verified-by-code: src/librabbitmq/amqp_socket.c:42-83; src/pg_amqp.c:168,
189]`. After connect, all framing reads/writes are blocking `read`/`write`
on that fd `[verified-by-code: src/librabbitmq/amqp_socket.c:99-101]`.
There is **no** `CHECK_FOR_INTERRUPTS()`, no `WaitLatchOrSocket`, and no
integration with PG's interrupt / statement-timeout machinery anywhere on
the publish path `[verified-by-code: grep of src/pg_amqp.c found no
CHECK_FOR_INTERRUPTS / WaitLatch]`. So a slow or half-dead broker blocks
the backend for up to the socket timeout per syscall, uninterruptible by
`pg_cancel_backend` or `statement_timeout`. Contrast pg_net's whole reason
for existing (a non-blocking reactor in a background worker) and even
pgsql-http (which at least exposes libcurl timeout GUCs). This is the
classic "synchronous external I/O in a backend" footgun the bridge family
is defined by, with pg_amqp at the rawest end (hand-vendored blocking
sockets, fixed 2 s timeout, no cancel point). `[verified-by-code]` for the
socket setup; `[inferred]` for the user-visible "uninterruptible" symptom.

### 5. Functions marked `IMMUTABLE` despite a network side effect; errors degrade to WARNING + reconnect, never ERROR

`amqp.publish` is declared `IMMUTABLE`
`[verified-by-code: sql/functions/functions.sql:60-61]` — a volatility lie:
the function has an external, non-deterministic side effect (a network
publish) and is the antithesis of immutable. `IMMUTABLE` permits the
planner to fold/cache calls, which for a publish is semantically wrong; the
choice appears to be for call-site convenience (usable in more contexts)
rather than correctness `[inferred]`. On the error side, the divergence is a
philosophy: when the broker is down or a publish fails, the code never
`ereport(ERROR)`. It instead `elog(WARNING, ...)`, sets `bs->inerror`,
tears down the connection, and on the *first* failure transparently
reconnects and retries once (`once_more` / `goto redo`)
`[verified-by-code: src/pg_amqp.c:339-347, 190-237]`. A persistent failure
just returns `false` from the SQL function
`[verified-by-code: src/pg_amqp.c:345-353]`, and the comment warns the
caller that even a `true` return is not a delivery guarantee because "AMQP
publish is asynchronous" `[from-comment:
sql/functions/functions.sql:70-71]`. This soft-failure stance (never abort
the user's transaction because the broker hiccupped) is a deliberate
inversion of PG's normal "raise an ERROR and roll back" reflex. The
`inerror` flag is also drained lazily at the *next* commit/abort:
`amqp_local_phase2` disconnects any `inerror` broker before processing
`uncommitted` `[verified-by-code: src/pg_amqp.c:101-103, 115-117]`. See
[[knowledge/idioms/error-handling]] (WARNING vs ERROR elevel choice).

## Notable design decisions (with cites)

- **Two channels, two roles.** Channel 1 is the plain channel used for
  `exchange_declare` and `autonomous_publish`; channel 2 is the
  tx-mode channel used for transactional `publish`. Both are opened
  eagerly at connect `[verified-by-code: src/pg_amqp.c:203-220]`.
- **Reconnect-once-then-give-up.** The retry logic only retries on the
  non-tx case or first failure (`channel == 1 || bs->uncommitted == 0`),
  so it won't silently re-send messages already accepted into an open
  broker tx `[verified-by-code: src/pg_amqp.c:340]` — a correctness
  guard against double-delivery.
- **Defaults baked into C, not the table.** Missing `host`/`vhost`/
  `username`/`password` fall back to `localhost` / `/` / `guest` / `guest`
  in C `[verified-by-code: src/pg_amqp.c:176-184]`.
- **`autonomous_publish` predates SQL autonomous txns.** It is "autonomous"
  only in the sense of bypassing the XactCallback (channel 1), not a true
  PG autonomous transaction `[verified-by-code: src/pg_amqp.c:362-366;
  from-comment: sql/functions/functions.sql:15-18]`.
- **`exchange_declare` warns against `auto_delete`.** Because an
  unexpected error triggers disconnect/reconnect, an auto-delete exchange
  would vanish — the comment tells users to leave it `false`
  `[from-comment: sql/functions/functions.sql:44-47]`.
- **`text` payload via `VARDATA_ANY` macro.** The `set_bytes_from_text`
  macro reads `PG_GETARG_TEXT_PP` + `VARDATA_ANY` / `VARSIZE_ANY_EXHDR`,
  pointing the `amqp_bytes_t` *directly into* the detoasted datum (no copy)
  `[verified-by-code: src/pg_amqp.c:56-62]` — fine because the publish
  consumes it synchronously before the datum is freed.
- **Old extension, old conventions.** `#ifdef PG_MODULE_MAGIC`, K&R-style
  implicit-int function params (`local_amqp_get_a_bs(broker_id)` with no
  type) `[verified-by-code: src/pg_amqp.c:64-66, 139-140, 151-152,
  238-239]`; targets PostgreSQL ≥ 9.1 `[from-README: README.md:64]`.

## Links into corpus

- [[knowledge/ideologies/pg_net]] — async-background-worker outbound bridge.
  **Contrast:** pg_net decouples the effect from the transaction entirely
  (queue row + worker); pg_amqp couples it *to* the transaction via the
  broker tx channel + XactCallback (#1).
- [[knowledge/ideologies/pgsql-http]] — synchronous-blocking-in-backend
  outbound bridge (libcurl). **Contrast:** pgsql-http's effect is *not*
  cancelled by ROLLBACK; pg_amqp's is (#1). Both share the blocking-I/O-in-a-
  backend footgun (#4), but pgsql-http exposes timeout GUCs and pg_amqp
  hard-codes a 2 s socket timeout.
- [[knowledge/ideologies/pgmq]] — the *inbound* counterpart: a message queue
  built entirely from SQL objects, no network egress. Structural foil to the
  whole egress-bridge family.
- [[knowledge/idioms/memory-contexts]] — the `TopMemoryContext` process-global
  connection cache (#2), an escape from the normal context hierarchy.
- [[knowledge/idioms/fmgr]] — `PG_FUNCTION_INFO_V1`, `PG_GETARG_*`, the
  `VARDATA_ANY` text-arg macro, and SPI-from-C on the connect path (#3).
- [[knowledge/idioms/error-handling]] — the WARNING-not-ERROR soft-failure
  stance and reconnect-once retry (#5).
- [[knowledge/idioms/catalog-conventions]] — the `amqp.broker` config table +
  `pg_extension_config_dump` (#3, How-it-hooks).
- [[knowledge/idioms/guc-variables]] — referenced only to note pg_amqp does
  *not* use GUCs for config (it uses a table instead, #3).
- Core analogs in prose: `RegisterXactCallback` / `XactEvent`
  (`XACT_EVENT_COMMIT` / `_ABORT` / `_PREPARE`) in
  `src/backend/access/transam/xact.c` — the exact registration `_PG_init`
  uses (#1); SPI machinery in `src/backend/executor/spi.c` (#3).

## Sources

| URL | HTTP |
|---|---|
| https://api.github.com/repos/omniti-labs/pg_amqp/git/trees/master?recursive=1 | 200 |
| https://raw.githubusercontent.com/omniti-labs/pg_amqp/master/amqp.control | 200 |
| https://raw.githubusercontent.com/omniti-labs/pg_amqp/master/README.md | 200 |
| https://raw.githubusercontent.com/omniti-labs/pg_amqp/master/Makefile | 200 |
| https://raw.githubusercontent.com/omniti-labs/pg_amqp/master/META.json | 200 |
| https://raw.githubusercontent.com/omniti-labs/pg_amqp/master/doc/amqp.md | 200 |
| https://raw.githubusercontent.com/omniti-labs/pg_amqp/master/sql/functions/functions.sql | 200 |
| https://raw.githubusercontent.com/omniti-labs/pg_amqp/master/sql/tables/tables.sql | 200 |
| https://raw.githubusercontent.com/omniti-labs/pg_amqp/master/src/pg_amqp.c | 200 |
| https://raw.githubusercontent.com/omniti-labs/pg_amqp/master/src/librabbitmq/amqp_socket.c | 200 |

**Fetch notes / substitutions:**
- `master` branch resolved on the first try (no `main` fallback needed); tree
  sha `240d477`. No 404s encountered.
- The repo is **PGXS / old-style**, not meson. There is **no `.sql.in` /
  `.control.in`** — the install SQL is *generated* by `cat`-ing
  `sql/tables/*.sql` + `sql/functions/*.sql` into
  `sql/amqp--0.4.2.sql` at `make` time `[verified-by-code: Makefile:19-22]`,
  so the shipped install script does not exist in the source tree; the two
  fragment files were read instead. `@extschema@` placeholders are resolved
  by `CREATE EXTENSION`.
- **librabbitmq is vendored in-tree** under `src/librabbitmq/` (MPL-licensed,
  ~11 files) and compiled into the same `.so` via `MODULE_big`
  `[verified-by-code: Makefile:12-16]`. Only `amqp_socket.c` was read
  line-by-line (for the socket-I/O / timeout / blocking-mode claims in #4);
  the framing (`amqp_framing.c`), table (`amqp_table.c`), and connection
  (`amqp_connection.c`) internals were **not** read — claims about
  `amqp_tx_commit` / `amqp_basic_publish` / `amqp_tx_select` semantics rest
  on the call sites in `src/pg_amqp.c` plus the AMQP 0-8 protocol meaning of
  those method names `[verified-by-code]` for the calls, `[inferred]` for the
  broker-side effect.
- **Prompt correction:** the prompt described messages as "buffered [in PG]
  and flushed at COMMIT". The code shows a different mechanism — messages are
  sent to the broker *immediately* via `amqp_basic_publish` on a **broker-side
  transaction channel** (`tx_select`), and the XactCallback issues
  `amqp_tx_commit` / `amqp_tx_rollback` to the *broker* at PG commit/abort. The
  buffering lives on the broker, not in PG memory
  `[verified-by-code: src/pg_amqp.c:209-220, 331-336, 100-127]`.
