# synchdb — a Debezium/JVM CDC engine hosted in a bgworker that applies a foreign change-stream INTO PostgreSQL

> Ideology note produced by the `pg-extension-anthropologist` cloud routine.
> Repo: `Hornetlabs/synchdb` @ branch `main`. 111★, C (+ an embedded Debezium
> Java engine built by Maven under `src/backend/debezium`). All `file:line`
> cites below point into the **synchdb** repo, NOT into PG `source/`, since this
> doc characterizes an *external* extension's divergence from core idioms. Cites
> verified against files fetched on 2026-06-29 (see Sources footer).
> Confidence tags: `[verified-by-code]` `[from-README]` `[from-comment]`
> `[inferred]` `[unverified]`.
> **Caveat on fetch scope:** I deep-read the C backend that owns the divergence
> story — `synchdb.c` (JNI bridge + bgworker + JVM + shmem + GUCs),
> `replication_agent.c` (the executor-vs-SPI apply path), and skimmed
> `format_converter.c` (JSON→Datum) and `debezium_event_handler.c`. The Java
> side (`src/backend/debezium/`, the `com.example.DebeziumRunner` class) was
> NOT fetched; claims about it rest on the C-side JNI method-signature lookups
> and the README. The GitHub `git/trees` API 403'd through the proxy, so paths
> were recovered from the `Makefile` `OBJS` list instead (see Sources).
>
> **Sibling note.** synchdb sits at the intersection of two existing corpus
> ideologies: it embeds a **whole JVM in the backend** like
> [[knowledge/ideologies/pljava]], but its *purpose* is **replication apply**
> like [[knowledge/ideologies/pglogical]]. Read it as "pljava's JVM-in-backend
> tax paid in service of pglogical's apply-worker job" — except the change
> source is not PG WAL at all; it is MySQL/SQL Server/Oracle, decoded by the
> Debezium connector framework running *inside* the JVM and handed to PG as a
> JSON batch over a JNI direct ByteBuffer.

## Domain & purpose

synchdb enables "fast and reliable data replication from multiple heterogeneous
databases into PostgreSQL" with no external middleware — PostgreSQL connects
directly to the source systems `[from-README]`. Supported sources are MySQL, SQL
Server, Oracle, and Openlog Replicator `[from-README]`. The mechanism: each
connector is a PG background worker that boots a JVM, instantiates the Debezium
embedded engine (a Java CDC framework) pointed at a source DB, polls Debezium for
batches of change events over JNI, converts each event's JSON into PG `Datum`s,
and applies it to a local table as an insert/update/delete. It performs an initial
snapshot followed by continuous CDC streaming `[from-README]`. Where
[[knowledge/ideologies/pglogical]] re-implements PG-native logical replication as
an extension, synchdb is the inverse problem: it is a *heterogeneous-source*
replication target where the entire decode side is a third-party Java framework,
so the extension's job is mostly *hosting that framework* and *marshalling its
output into the PG executor*.

## How it hooks into PG

- **Background workers, two tiers.** A static **leader/auto-launcher** worker is
  registered from `_PG_init` via `RegisterBackgroundWorker` (`bgw_function_name =
  "synchdb_auto_launcher_main"`), but only when synchdb is in
  `shared_preload_libraries` and `synchdb.synchdb_auto_launcher` is on
  `[verified-by-code: src/backend/synchdb/synchdb.c:3008-3020,4118-4121]`. Each
  connector then runs as a **dynamic** worker (`bgw_function_name =
  "synchdb_engine_main"`) launched by `RegisterDynamicBackgroundWorker` from the
  SQL-callable start functions
  `[verified-by-code: synchdb.c:4454-4459,4556-4561]`. Workers take
  `BGWORKER_SHMEM_ACCESS | BGWORKER_BACKEND_DATABASE_CONNECTION` and connect to
  the target DB (`BackgroundWorkerInitializeConnection`) before applying
  `[inferred from setup_environment + on_shmem_exit at synchdb.c:1823]`.

- **Embedded JVM via the JNI Invocation API, one per connector worker.**
  `initialize_jvm()` builds a `JavaVMOption[]` (classpath → the Debezium engine
  jar, `-Xrs`, `-Xmx`, `-XX:MaxDirectMemorySize`, optional JMX/Prometheus agent
  flags) and calls `JNI_CreateJavaVM(&jvm, (void**)&env, &vm_args)` with
  `JNI_VERSION_10` `[verified-by-code: synchdb.c:1873-1967]`. `jvm`/`env` are
  static globals `[verified-by-code: synchdb.c:158-159]`. Identical structural
  move to [[knowledge/ideologies/pljava]] (dlsym'd `JNI_CreateJavaVM`, `-Xrs` to
  keep the JVM off PG's signals), but here the VM is started inside a *bgworker*
  per connector, not in a user backend per PL call.

- **The Debezium engine as a Java object reached by `FindClass` +
  `GetMethodID`.** `dbz_engine_init` does `FindClass(env,
  "com/example/DebeziumRunner")` then `AllocObject`
  `[verified-by-code: synchdb.c:716-746]`. The C side drives the engine entirely
  through reflective method handles: `startEngine`, `stopEngine`,
  `getChangeEvents` (`()Ljava/nio/ByteBuffer;`), `markBatchComplete`,
  `getConnectorOffset`/`setConnectorOffset`, `createOffsetFile`, `jvmMemDump`
  `[verified-by-code: synchdb.c:680-687,789,999-1007,1104-1118,2891-2901]`. Every
  Debezium config knob is pushed as a JNI setter on a `DebeziumRunner$MyParameters`
  object (`setBatchSize`, `setQueueSize`, `setSslmode`, … ~30 of them)
  `[verified-by-code: synchdb.c:246-639,957-1007]`.

- **GUCs (`synchdb.*`), defined in `_PG_init`.** ~25 `DefineCustom*Variable`
  calls including `synchdb.naptime`, `synchdb.dml_use_spi`,
  `synchdb.dbz_batch_size`, `synchdb.jvm_max_heap_size`,
  `synchdb.jvm_max_direct_buffer_size`, `synchdb.max_connector_workers`,
  `synchdb.error_handling_strategy` (enum), `synchdb.dbz_log_level` (enum), and a
  `PGC_POSTMASTER` `synchdb.synchdb_auto_launcher`
  `[verified-by-code: synchdb.c:3781-4096]`, closed by
  `MarkGUCPrefixReserved("synchdb")` `[verified-by-code: synchdb.c:4099]`.

- **The executor apply path (not WAL, not output-plugin).** The apply side calls
  `table_open` → `CreateExecutorState` → `ExecInitRangeTable` → `InitResultRelInfo`
  → build a virtual `TupleTableSlot` → `ExecSimpleRelationInsert` /
  `…Update` / `…Delete`
  `[verified-by-code: replication_agent.c:341-408,462-588,655-754]`. This is the
  same low-level table-modify entry point pglogical's heap apply backend uses
  ([[knowledge/ideologies/pglogical]] divergence #2), reached here from a foreign
  change stream rather than PG logical decoding.

- **SPI as the alternate apply backend and for all DDL/utility.** Gated by
  `synchdb.dml_use_spi`, DML can instead go through `spi_execute(pgdml->dmlquery,
  …)`; non-DML operations always go through SPI "regardless what
  synchdb_dml_use_spi is" `[verified-by-code: replication_agent.c:844-895]`.

Cross-ref [[knowledge/idioms/spi]], [[knowledge/idioms/guc-variables]],
[[knowledge/idioms/error-handling]],
`.claude/skills/bgworker-and-extensions/SKILL.md`,
`.claude/skills/extension-development/SKILL.md`.

## Where it diverges from core idioms

### 1. The "replication source" is a foreign DB decoded by a Java framework, not PG WAL — there is no logical-decoding output plugin at all

This is the structural inversion versus every other replication extension in the
corpus. pglogical and core pub/sub both decode PG's *own* WAL via the
logical-decoding output-plugin contract ([[knowledge/ideologies/pglogical]]
divergence #1). synchdb has **no** output plugin and reads **no** WAL: the change
stream originates in MySQL/SQL Server/Oracle and is produced by Debezium's
connector framework running inside the embedded JVM. The C extension is, in effect,
a *subscriber with a JVM-hosted decoder bolted to its front*. The entire "where do
changes come from" question — binlog/redo/CDC-table parsing, schema-history
tracking, snapshotting — lives in Java, opaque to PG; the C side only ever sees a
byte buffer of JSON events `[verified-by-code: synchdb.c:798-869]`.

### 2. A JVM per connector worker, started in a bgworker — and the JNI "one VM per process" constraint sidestepped by the fork/worker model

Like [[knowledge/ideologies/pljava]], synchdb embeds a full JVM
(`JNI_CreateJavaVM`, static `jvm`/`env`, `-Xrs`)
`[verified-by-code: synchdb.c:158-159,1901,1962]`. The hard JNI rule — a process
may create at most one JVM — is dodged the same way pljava dodges it: process
isolation. But synchdb's unit of isolation is a **dynamic background worker per
connector** rather than a user backend per session, so N connectors = N OS
processes = N independent JVMs, all under one postmaster. The VM is torn down at
worker shutdown with `(*jvm)->DestroyJavaVM(jvm)`
`[verified-by-code: synchdb.c:2771-2776]`, and at a snapshot→CDC engine swap the
worker calls `DetachCurrentThread` then `DestroyJavaVM`
`[verified-by-code: synchdb.c:2622-2623]` — i.e. it does recreate a JVM within one
worker's lifetime across the snapshot/stream boundary, tolerable only because the
first VM is fully destroyed first. Contrast pljava, which treats one-VM-per-session
as a terminal state (no in-session restart). Cross-ref
[[knowledge/ideologies/pljava]] divergence #1.

### 3. Change events cross the boundary as JSON in a JNI *direct ByteBuffer*, decoded by hand-rolled length-prefix framing

Rather than marshalling per-column `Datum`↔`jobject` through a type vtable
(pljava's `TypeClass`, [[knowledge/ideologies/pljava]] divergence #4), synchdb
moves an entire *batch* across the seam as one opaque buffer.
`getChangeEvents` returns a `java.nio.ByteBuffer`; the C side reads it with
`GetDirectBufferAddress` / `GetDirectBufferCapacity` (zero-copy into JVM-owned
direct memory, which is why `-XX:MaxDirectMemorySize` is a tunable GUC)
`[verified-by-code: synchdb.c:798-812,1903]`. The buffer is a custom wire format: a
leading tag byte (`'B'` = batch, `'K'` = control/ack), then `ntohl`-decoded
big-endian length-prefixed JSON event strings
`[verified-by-code: synchdb.c:816-899]`. Each JSON event is then handed to
`fc_processDBZChangeEvent` `[verified-by-code: synchdb.c:863-865]`, which turns the
JSON into PG values using `jsonb_in`/`jsonb_get_element` and per-column
`OidInputFunctionCall` `[verified-by-code: src/backend/converter/format_converter.c:693-694,4084;
replication_agent.c:387-390]`. The marshalling layer is thus **string-typed**
(values arrive as text and go through each column's type input function), not a
binary Datum coercion table — a deliberately simpler, looser seam than pljava's.

### 4. One PG transaction per Debezium batch, opened and committed inside the JNI polling routine

`dbz_engine_get_change` brackets an entire decoded batch in
`StartTransactionCommand()` / `PushActiveSnapshot(GetTransactionSnapshot())` …
`PopActiveSnapshot()` / `CommitTransactionCommand()`, looping the per-event apply
in between `[verified-by-code: synchdb.c:832-873]`. After commit it tells Debezium
the batch is durable via `markBatchComplete`
`[verified-by-code: synchdb.c:2891-2901]`, and connector offsets are persisted
through `getConnectorOffset`/`createOffsetFile` into a `pg_synchdb` metadata
directory created in `_PG_init` `[verified-by-code: synchdb.c:1104,2056-2071,4101-4115]`.
This batch=transaction, then-ack model is synchdb's at-least-once durability
boundary; it is materially different from pglogical, where transaction boundaries
come from the *source* commit records in the decoded stream
([[knowledge/ideologies/pglogical]] divergence #3 area). Here the source's
transaction structure is flattened into Debezium-sized batches.

### 5. Error bridging is *one-directional and lossy*: Java exception → `ExceptionDescribe` + `elog(WARNING)` + return -1, NOT a round-tripped error object

pljava's exception bridge is bidirectional and stateful — it round-trips a full
`ErrorData` (with SQLSTATE) through a Java `ServerException` and back
([[knowledge/ideologies/pljava]] divergence #2). synchdb does **not** attempt
this. Every JNI call is followed by the same flat pattern: `ExceptionCheck` /
`ExceptionOccurred` → `ExceptionDescribe` (print to stderr) → `ExceptionClear` →
`elog(WARNING, …)` → `return -1`, with the human-readable gist optionally stashed
in shmem via `set_shm_connector_errmsg`
`[verified-by-code: synchdb.c:690-694,724-742,799-805,1010-1014,1121-1125,2904-2908]`.
The Java exception type/SQLSTATE is discarded; the worker degrades to a warning and
a sentinel return code rather than re-raising a typed PG error. In the *other*
direction (PG error during apply), synchdb wraps each `synchdb_handle_insert/update/
delete` body in `PG_TRY()/PG_CATCH()` precisely so a PG `ereport(ERROR)` longjmp
does not kill the worker — the catch stores the message in shmem state so the user
"will have an idea what is wrong"
`[verified-by-code + from-comment: replication_agent.c:333-339]`. So the boundary is
handled, but asymmetrically and with deliberate information loss compared to pljava.
Cross-ref [[knowledge/idioms/error-handling]] (PG_TRY/PG_CATCH, ereport).

### 6. Threading: a multithreaded Debezium framework inside a single-threaded backend, with NO entry-policy machinery

A JVM running Debezium spawns many threads (connector tasks, Kafka-Connect-style
executors, GC, JIT). pljava confronts this with a GUC-tunable thread-entry policy
(`pljava.java_thread_pg_entry`, [[knowledge/ideologies/pljava]] divergence #6).
synchdb has **none**: the design relies on the C bgworker thread being the *only*
thread that ever calls into PG, with Debezium's threads confined to producing the
ByteBuffer that the single C thread then drains
`[inferred from synchdb.c:798-873 — all PG-touching code runs on the worker's main
thread]`. `-Xrs` keeps the JVM from stealing PG's signals
`[verified-by-code: synchdb.c:1901]`. The only `DetachCurrentThread` call is at VM
teardown `[verified-by-code: synchdb.c:2622]`. This is a simpler bet than pljava's
policy bitmask, and it holds only as long as the Java side never calls a JNI
callback into PG from a Debezium worker thread (which, by the pull-based
`getChangeEvents` design, it does not). Cross-ref `.claude/skills/locking/SKILL.md`
(PG's single-threaded-backend assumption).

### 7. Runtime `ShmemInitStruct` under `AddinShmemInitLock`, with no `shmem_request_hook`/`shmem_startup_hook`

`synchdb_init_shmem` allocates `SynchdbSharedState` plus a
`synchdb_max_connector_workers`-sized `ActiveConnectors[]` array via
`ShmemInitStruct` while holding `AddinShmemInitLock`, and creates its LWLock
tranche with `LWLockNewTrancheId()` + `LWLockRegisterTranche("synchdb")`
`[verified-by-code: synchdb.c:1269-1299]`. Notably there is **no**
`shmem_request_hook`/`RequestAddinShmemSpace` and no `shmem_startup_hook`
`[verified-by-code: grep of synchdb.c — none present]`; the shmem is grabbed
lazily from inside the worker's `setup_environment` rather than pre-reserved at
postmaster start the way the modern PG ≥ 15 convention (and pglogical's
`shmem_request_hook`, [[knowledge/ideologies/pglogical]]) prescribes. This works
because the worker can run with `BGWORKER_SHMEM_ACCESS` and `ShmemInitStruct`
tolerates first-or-attach, but it diverges from the documented hook discipline and
means the segment isn't accounted for at the postmaster's shmem-sizing time.
Cross-ref `.claude/skills/locking/SKILL.md`,
`.claude/skills/bgworker-and-extensions/SKILL.md`.

### 8. Connector secrets stored encrypted in a catalog table, decrypted at start via pgcrypto

The `.control` file `requires = pgcrypto` (and the SQL pulls in `oracle_fdw` for
the Oracle FDW snapshot path) `[from-README; verified-by-code: synchdb.control]`.
Connector connection info — including the source-DB password — is persisted and the
password is `pgp_sym_decrypt`'d with a user-supplied master key at engine-start /
FDW-snapshot time `[verified-by-code: synchdb--1.0.sql:331-389,3204,3348]`. This is a
credential-management concern core replication never has (a PG subscriber stores a
libpq conninfo string; it does not broker third-party-DB passwords), and it is why
synchdb takes a hard `pgcrypto` dependency. Cross-ref
[[knowledge/idioms/catalog-conventions]].

## Notable design decisions (with cites)

- **JVM options capped at a fixed 30-slot array.** `JavaVMOption options[30]` with
  a `/* ensure we do not exceed this max number of java options */` comment; JMX +
  SSL + exporter flags all draw from this pool
  `[verified-by-code + from-comment: synchdb.c:1877]`.
- **JVM init runs in a throwaway MemoryContext.** `initialize_jvm` switches into a
  dedicated `AllocSetContextCreate(TopMemoryContext, "JVMINIT", …)`, builds the
  `psprintf`'d option strings there, then deletes the context after
  `JNI_CreateJavaVM` returns `[verified-by-code: synchdb.c:1896-1897,1981-1982]` —
  the option strings only need to live across the VM-create call. Idiomatic PG
  memory-context hygiene applied to a very un-idiomatic payload. Cross-ref
  [[knowledge/idioms/memory-contexts]].
- **`-Xrs` to protect PG's signal handlers** `[verified-by-code: synchdb.c:1901]` —
  the same defensive flag pljava passes ([[knowledge/ideologies/pljava]]).
- **Engine-jar path is env-overridable** (`DBZ_ENGINE_DIR`), else
  `$pkglibdir/dbz_engine/<jar>` `[verified-by-code: synchdb.c:1879-1887]`.
- **Per-connector state machine in shmem**, polled in `main_loop` with
  `STATE_SYNCING`/`STATE_PAUSED` branches and a
  `WaitLatch(WL_LATCH_SET|WL_TIMEOUT|WL_EXIT_ON_PM_DEATH, …
  synchdb_worker_naptime, PG_WAIT_EXTENSION)` idle
  `[verified-by-code: synchdb.c:2727; from-README for the state view]`.
- **PG-major-version shims** around `ExecInitRangeTable` (the PG 18 signature gained
  a `bms_make_singleton(1)` permission-bitmap arg)
  `[verified-by-code: replication_agent.c:354-359]` — supports PG 16/17/18 per the
  README `[from-README]`.

## Links into corpus

- **JVM-in-backend sibling:** [[knowledge/ideologies/pljava]] — the closest
  structural twin for the embedding mechanics (`JNI_CreateJavaVM`, `-Xrs`, static
  `jvm`/`env`, one-VM-per-process). **Contrasts:** synchdb hosts a *CDC framework*
  to feed an apply loop, pljava hosts a *PL runtime* to execute user functions;
  synchdb's error bridge is one-directional and lossy (`ExceptionDescribe` +
  `elog(WARNING)`) vs pljava's bidirectional `ErrorData`↔`ServerException` round
  trip; synchdb crosses the seam as one JSON ByteBuffer per batch vs pljava's
  per-Datum `TypeClass` vtable; synchdb has no thread-entry policy (single-thread
  drains a buffer) vs pljava's `java_thread_pg_entry` GUC; synchdb uses a bgworker
  per connector vs pljava's user-backend per session.
- **Replication-apply sibling:** [[knowledge/ideologies/pglogical]] — both apply a
  change stream via the low-level table-modify entry points
  (`ExecSimpleRelationInsert/Update/Delete`) and both offer an SPI apply backend
  gated by a GUC (`synchdb.dml_use_spi` ↔ `pglogical.use_spi`). **Contrast:**
  pglogical decodes PG's own WAL through an output plugin; synchdb has no output
  plugin and no WAL — its source is a foreign DB decoded by Debezium. pglogical
  pre-reserves shmem via `shmem_request_hook`; synchdb allocates lazily under
  `AddinShmemInitLock`.
- **Idioms / skills:**
  - [[knowledge/idioms/spi]] — the executor-vs-SPI apply dispatch (#3
    apply, `replication_agent.c:844-895`) and `OidInputFunctionCall` per-column
    coercion. Core analogs: `src/backend/executor/spi.c`,
    `src/backend/executor/execReplication.c` (`ExecSimpleRelation*`).
  - [[knowledge/idioms/error-handling]] — the asymmetric Java↔PG boundary (#5),
    `PG_TRY/PG_CATCH` around apply.
  - [[knowledge/idioms/memory-contexts]] — the throwaway `JVMINIT` context.
  - [[knowledge/idioms/guc-variables]] — the ~25 `synchdb.*` GUCs +
    `MarkGUCPrefixReserved`.
  - [[knowledge/idioms/catalog-conventions]] — pgcrypto-encrypted connector
    secrets (#8).
  - `.claude/skills/bgworker-and-extensions/SKILL.md` — the static-leader +
    dynamic-per-connector worker model; `.claude/skills/locking/SKILL.md` — the
    `AddinShmemInitLock` + custom LWLock tranche, and the single-thread bet (#6, #7).

## Anthropology takeaway

synchdb is what you get when you point pljava's machinery (a JVM embedded in the
backend) at pglogical's job (apply a replicated change stream) — and then change
the *source* from PostgreSQL's own WAL to a foreign database. That last move is the
deepest divergence: there is no logical-decoding output plugin, no WAL, no
PG-native transaction structure on the inbound side; the entire decode half is a
third-party Java framework (Debezium) the C extension merely hosts and pumps. The
consequences ripple outward: the JVM tax (per-connector bgworker, `-Xrs`,
`DestroyJavaVM` on swap), a deliberately *loose* seam (whole-batch JSON in a direct
ByteBuffer, string-typed values through `OidInputFunctionCall`, a one-directional
lossy exception bridge) where pljava chose a tight one, a batch=transaction
durability boundary acked back to Debezium, and credential brokering via pgcrypto
that no PG-to-PG replication ever needs. Where pljava pays for fidelity (typed
errors, per-Datum coercion, thread policy), synchdb deliberately pays less, because
its contract with the foreign engine is "hand me JSON, I'll commit a batch and tell
you when it's durable." It is the corpus's clearest example of an extension that
treats an entire foreign runtime as a black-box change *producer* bolted onto a
hand-built PG apply loop.

## Sources

Fetched 2026-06-29 (branch `main`):

| URL | HTTP | Note |
|---|---|---|
| https://api.github.com/repos/Hornetlabs/synchdb/git/trees/main?recursive=1 | 403 | **GAP** — GitHub API blocked through the agent proxy; the `git/trees` manifest could not be read. Real paths were instead recovered from the `Makefile` `OBJS` list. |
| https://raw.githubusercontent.com/Hornetlabs/synchdb/main/README.md | 200 | architecture + supported sources + SQL functions |
| https://raw.githubusercontent.com/Hornetlabs/synchdb/main/Makefile | 200 | OBJS / MODULE_big / JDK include paths / Maven `build_dbz` |
| https://raw.githubusercontent.com/Hornetlabs/synchdb/main/synchdb.control | 200 | `requires = pgcrypto`, relocatable, `$libdir/synchdb` |
| https://raw.githubusercontent.com/Hornetlabs/synchdb/main/src/backend/synchdb/synchdb.c | 200 | 6239 lines; deep-read JNI/JVM/bgworker/shmem/GUC/exception regions |
| https://raw.githubusercontent.com/Hornetlabs/synchdb/main/src/backend/converter/format_converter.c | 200 | 5313 lines; skimmed JSON→jsonb→Datum conversion |
| https://raw.githubusercontent.com/Hornetlabs/synchdb/main/src/backend/converter/debezium_event_handler.c | 200 | 1824 lines; fetched, not deep-read |
| https://raw.githubusercontent.com/Hornetlabs/synchdb/main/src/backend/executor/replication_agent.c | 200 | 1748 lines; deep-read executor-vs-SPI apply path |
| https://raw.githubusercontent.com/Hornetlabs/synchdb/main/synchdb--1.0.sql | 200 | 3566 lines; pgcrypto password decrypt + connector SQL API |

**Fetch notes / gaps:**
- The GitHub `git/trees` API 403'd (proxy blocks `api.github.com`); raw.githubusercontent.com
  was reachable. Paths confirmed from the `Makefile` `OBJS` (`src/backend/synchdb/synchdb.o`,
  `src/backend/converter/{format_converter,debezium_event_handler}.o`,
  `src/backend/executor/replication_agent.o`).
- The **Java side was not fetched**: the Debezium engine lives under
  `src/backend/debezium/` (Maven, `build_dbz` target) as `com.example.DebeziumRunner`.
  All Debezium-internal behavior (binlog/redo parsing, snapshotting, the `MyParameters`
  builder, `getChangeEvents` framing on the Java side) is `[from-README]` or
  `[inferred]` from the C-side JNI method signatures, not read directly.
- `OraProtoBuf.pb-c.c`, `olr_client.c`, `netio_utils.c`, `olr_event_handler.c` (the
  `WITH_OLR=1` Openlog-Replicator path) were not fetched; OLR-specific cites above are
  from the `#ifdef WITH_OLR` blocks visible in `synchdb.c` only.
