# pg_incremental — incremental batch processing as pure SQL-callable C driven by pg_cron, where "exactly once" is bought by tracking progress in the same transaction as the command and computing a safe watermark from lock-waiting rather than snapshots

> Ideology note produced by the `pg-extension-anthropologist` cloud routine.
> Repo: `CrunchyData/pg_incremental` @ branch `main`. All `file:line` cites below
> point into that repo (not `source/`), since this doc characterizes an
> *external* extension's divergence from core idioms. Cites verified against
> files fetched on 2026-07-12 (see Sources footer). Read alongside
> `[[knowledge/ideologies/pg_ivm]]` (incremental view maintenance the
> trigger/rewriter way — the synchronous sibling), `[[knowledge/ideologies/pipelinedb]]`
> (continuous queries via a private bgworker tree — the maximal counterpart),
> `[[knowledge/ideologies/pg_cron]]` (its hard runtime dependency and scheduler),
> and `[[knowledge/ideologies/pg_partman]]` / `[[knowledge/ideologies/mimeo]]`
> (the other "scheduled maintenance via SQL + cron" extensions).

## Domain & purpose

pg_incremental is "a simple extension that helps you do fast, reliable,
incremental batch processing in PostgreSQL" (`README.md:3`) `[from-README]`. The
problem it targets: given an append-only stream of events (IoT, time series, or
files landing in object storage), process *only the new data* — build summary
tables, export ranges, or ingest files — with the guarantee that "all new events
are processed successfully exactly once, even when queries fail" (`README.md:5`)
`[from-README]`. The user defines a **pipeline** = a name + a parameterized SQL
command + a schedule; pg_incremental runs the command periodically, binding `$1`
and `$2` to the boundaries of the new work. Three pipeline types exist
(`README.md:73-77`) `[from-README]`, dispatched on a one-`char` type tag
`'s'`/`'t'`/`'f'` (`include/crunchy/incremental/pipeline.h:3-7`)
`[verified-by-code]`:

- **Sequence pipelines** — `$1`,`$2` are a safe `bigint` range of sequence
  values (`ExecuteSequenceRangePipeline`, `src/sequence.c:90`).
- **Time interval pipelines** — `$1`,`$2` are the start/end (exclusive) of a
  passed time window as `timestamptz` (`ExecuteTimeIntervalPipeline`,
  `src/time_interval.c:101`).
- **File list pipelines** — `$1` is one file path (`text`), or a `text[]` batch,
  from a list function (`ExecuteFileListPipeline`, `src/file_list.c:111`).

The design's own framing is explicitly minimalist: "While there are much more
sophisticated approaches … like incremental materialized views or logical
decoding-based solutions, they come with many limitations … We felt the need for
a simple, fire-and-forget tool" (`README.md:25`) `[from-README]`. That is the
whole ideology — it deliberately declines the machinery `[[knowledge/ideologies/pg_ivm]]`
and `[[knowledge/ideologies/pipelinedb]]` build, and substitutes plain SQL,
pg_cron, and one clever watermark trick.

## How it hooks into PG

**No `_PG_init`, no background worker, no planner/executor/utility hook.** The
entire backend surface is a handful of `PG_FUNCTION_INFO_V1` SQL-callable C
functions (`src/pipeline.c:33-39`) `[verified-by-code]` — `create_*_pipeline`,
`execute_pipeline`, `reset_pipeline`, `drop_pipeline`, `skip_file` — wired to SQL
via `LANGUAGE C … 'MODULE_PATHNAME'` (`pg_incremental--1.0.sql:53-122`)
`[verified-by-code]`. There is nothing resident in shared memory; a pipeline
"runs" only when someone calls `execute_pipeline`. This is the fmgr-composition
end of the extension spectrum (`[[knowledge/idioms/fmgr]]`), the opposite of
pipelinedb's process tree.

**pg_cron is the scheduler, injected as a hard runtime dependency.** At create
time, if a `schedule` is given, the extension runs `SELECT cron.schedule($1,$2,$3)`
through SPI (`ScheduleCronJob`, `src/cron.c:26-49`) `[verified-by-code]`, first
erroring if pg_cron is absent: `get_extension_oid("pg_cron", missingOk)` →
`ERRCODE_OBJECT_NOT_IN_PREREQUISITE_STATE` with hint "Run CREATE EXTENSION
pg_cron; or pass schedule := NULL" (`src/cron.c:20-24`) `[verified-by-code]`. The
scheduled command is literally `call incremental.execute_pipeline('<name>')`
(`GetCronCommandForPipeline`, `src/pipeline.c:637-640`) `[verified-by-code]`;
the job name is `pipeline:<name>` (`src/pipeline.c:627-629`). Default cadence is
every minute (`* * * * *`, `pg_incremental--1.0.sql:57`) `[verified-by-code]`.
So pg_incremental **registers cron jobs rather than running its own bgworker** —
verified: there is no `RegisterBackgroundWorker` call anywhere in the tree. See
`[[knowledge/ideologies/pg_cron]]`.

**Catalog tables live in a hand-created `incremental` schema.** The install
script does `CREATE SCHEMA incremental` and five bookkeeping tables:
`pipelines` (name PK, type char, owner oid, source_relation regclass, command),
plus per-type state tables `sequence_pipelines`, `time_interval_pipelines`,
`file_list_pipelines`, and `processed_files` — each `references … on delete
cascade` back to `pipelines` (`pg_incremental--1.0.sql:1-51`) `[verified-by-code]`.
Note the mismatch worth flagging: the control file declares `schema = pg_catalog`,
`relocatable = false` (`pg_incremental.control`) `[verified-by-code]`, yet every
object is explicitly qualified into `incremental.*` by the script, so the
`pg_catalog` schema setting is effectively vestigial `[inferred]`.

**All internal state I/O is SPI.** Every bookkeeping read/write is
`SPI_connect()` → `SPI_execute_with_args()` → `SPI_finish()` (e.g.
`InsertPipeline`, `src/pipeline.c:402-410`; `ReadPipelineDesc`,
`src/pipeline.c:452-489`) `[verified-by-code]`. Cross-ref `[[knowledge/idioms/spi]]`.
The command validation path is separate: at create time `ParseQuery` runs
`pg_parse_query` + `pg_analyze_and_rewrite_fixedparams` with the two typed params
so a broken command fails at definition, not at 3am (`src/query.c:16-42`,
called from `src/pipeline.c:111,178,267`) `[verified-by-code]`.

**Privilege model: superuser for bookkeeping, caller for the command.** Writes to
the `incremental.*` tables escalate via
`GetUserIdAndSecContext` → `SetUserIdAndSecContext(BOOTSTRAP_SUPERUSERID,
SECURITY_LOCAL_USERID_CHANGE)` and restore afterwards (`src/pipeline.c:380-381,412`)
`[verified-by-code]`, so an unprivileged owner can maintain a pipeline without
owning its state tables. But the pipeline command itself runs under the caller's
identity with the per-pipeline saved `search_path` re-applied
(`ExecutePipeline` restores `search_path` in a `NewGUCNestLevel`/`AtEOXact_GUC`
frame, `src/pipeline.c:521-548`) `[verified-by-code]`. Mutation is gated by
`EnsurePipelineOwner` (superuser or `ownerId == GetUserId()`, else
`ERRCODE_INSUFFICIENT_PRIVILEGE`, `src/pipeline.c:502-511`) `[verified-by-code]`.
(A stale comment at `src/pipeline.c:450` says "we do not switch user" directly
below code at `:431-432` that *does* switch to superuser — a comment/code
mismatch `[verified-by-code]`.)

### The safe watermark — how it decides what is safe to process

This is the technical heart, and it does **not** use `GetOldestXmin`,
`pg_current_snapshot`, `txid_*`, or logical decoding. Each pipeline type computes
its range with a coarse, lock-based technique:

- **Sequence.** `GetSequenceNumberRange` selects `last_processed_sequence_number
  + 1` as the start and `pg_catalog.pg_sequence_last_value(sequence_name)` as the
  tentative end, taking `FOR UPDATE` on the pipeline's own state row
  (`src/sequence.c:195-202`) `[verified-by-code]`. Then `PopSequenceNumberRange`
  calls `WaitForLockers(tableLockTag, ShareLock, true)` on the *source table*
  (`src/sequence.c:151-159`) `[verified-by-code]` — it blocks until every
  in-flight writer that holds `RowExclusiveLock` on the table has committed or
  aborted. The load-bearing assumption is stated in-comment: "writers will only
  insert sequence numbers that were obtained after locking the table"
  (`src/sequence.c:141-142`) `[from-comment]`. After that wait, no uncommitted
  transaction can still own a sequence value `<= rangeEnd`, so the range is
  provably closed. This is the Citus Data blog technique the author references
  (`README.md:127`) `[from-README]`.
- **Time interval.** The tentative end is
  `date_bin(time_interval, now() - min_delay, '2001-01-01')` — the floor of
  (now − `min_delay`) to an interval boundary (`src/time_interval.c:271-279`)
  `[verified-by-code]`; the start is `last_processed_time`, again `FOR UPDATE`.
  If the pipeline was created with a `source_table_name`, it does the same
  `WaitForLockers(..., ShareLock, true)` on that table
  (`src/time_interval.c:233`) `[verified-by-code]`, which is only sound "if the
  timestamp is generated by the database using now() and assuming no large clock
  jumps" (`README.md:218`) `[from-README]`.
- **File list.** The "watermark" is a relational set-difference: the list
  function's output `LEFT JOIN incremental.processed_files … WHERE proc.path IS
  NULL` (`src/file_list.c:408-415`) `[verified-by-code]`. New files are whatever
  the list function returns that is not yet recorded processed.

In all three, the pipeline command runs under a freshly pushed snapshot,
`PushActiveSnapshot(GetTransactionSnapshot())` (`src/sequence.c:108`,
`src/time_interval.c:182`, `src/file_list.c:172,262`) `[verified-by-code]`, so it
observes the just-committed writers the wait released. See
`[[knowledge/idioms/snapshot-acquisition]]` and `[[knowledge/idioms/relation-extension-lock]]`
for the lock/snapshot machinery this leans on.

## Where it diverges from core idioms

### 1. Exactly-once = progress written in the *same transaction* as the command

The signature move: "The internal progress tracking is done in the same
transaction as the command, which ensures exactly once delivery" (`README.md:23`)
`[from-README]`. Concretely, `PopSequenceNumberRange` calls
`UpdateLastProcessedSequenceNumber(pipelineName, range->rangeEnd)` *before*
running the command, "which will commit or abort with the current
(sub)transaction" (`src/sequence.c:161-166`) `[verified-by-code]`; the
time-interval and file-list paths do the same
(`UpdateLastProcessedTimeInterval`, `src/time_interval.c:239`;
`InsertProcessedFile` after each file, `src/file_list.c:154,244`)
`[verified-by-code]`. If the command throws, the whole transaction — progress row
included — rolls back, and the next cron tick retries the identical range. There
is no separate durable "checkpoint" store, no two-phase commit, no dedup table:
transactional atomicity *is* the exactly-once mechanism. Contrast
`[[knowledge/ideologies/pg_ivm]]` (synchronous AFTER-trigger deltas per statement)
and `[[knowledge/ideologies/pgmq]]` (a queue with explicit archive/delete) —
pg_incremental has no in-flight state to reconcile because a run is one
all-or-nothing transaction.

### 2. Watermark by lock-waiting, not by xid snapshot horizon

Core's own "what is safely visible / done" primitives are xid-based
(`GetOldestXmin`, snapshot `xmin`, the xmin horizon —
`[[knowledge/idioms/snapshot-acquisition]]`). pg_incremental sidesteps all of
that and instead *waits out* concurrent writers with `WaitForLockers` +
`pg_sequence_last_value` (`src/sequence.c:159,198`) `[verified-by-code]`. The
payoff is radical simplicity and no dependence on decoding or replication; the
cost is the correctness rider that writers must draw the sequence value *after*
acquiring the table lock, and (for time pipelines) that timestamps come from
`now()` with no clock jumps (`README.md:218,231`) `[from-README]`. It trades a
hard guarantee for an assumption about how writers behave.

### 3. Intentional `-Wdeclaration-after-statement` violation in the build

The Makefile deliberately strips PostgreSQL's C89-declarations warning:
`override CFLAGS := $(filter-out -Wdeclaration-after-statement,$(CFLAGS))`,
under the comment "PostgreSQL does not allow declaration after statement, but we
do" (`Makefile:16-17`) `[verified-by-code]`. Every source file exercises this —
e.g. `char *pipelineName = …` mid-function after executable statements
(`src/pipeline.c:60-65`, `src/sequence.c:94`) `[verified-by-code]`. This is a
documentable, self-aware break from the core `coding-style` contract
(`.claude/skills/coding-style/SKILL.md`), which forbids mid-block declarations —
a deliberate ergonomics-over-conformance choice, and a signal the code is not
aimed at upstream inclusion `[inferred]`.

### 4. A hard dependency on another extension, enforced at *runtime* not in the control file

pg_incremental cannot schedule without pg_cron, yet the control file carries no
`requires = 'pg_cron'` clause (`pg_incremental.control`) `[verified-by-code]`;
the dependency is checked in C at `ScheduleCronJob` time (`src/cron.c:20-24`)
`[verified-by-code]`. This makes pg_cron a *soft, deferred* prerequisite: you can
`CREATE EXTENSION pg_incremental` and run pipelines manually with `schedule :=
NULL` (`README.md:372`) `[from-README]`, and only hit the requirement when you
ask for scheduling. Building a maintenance feature *on top of another contrib
extension* rather than reimplementing a scheduler is itself the divergence — the
same "compose extensions" posture as `[[knowledge/ideologies/pg_partman]]`
leaning on pg_cron/bgworker for its retention runs.

### 5. The design is architected around append-only + monotonic keys + BRIN

Every worked example filters `where event_id between $1 and $2` or `where
event_time >= $1 and event_time < $2` over an *ascending, contiguous* range, and
the README explicitly steers users to BRIN: "BRIN indexes are highly effective in
selecting new ranges" on both the sequence column and the time column
(`README.md:98-99,177-178`) `[from-README]`. The safe-range mechanism only makes
sense when the key is monotone (sequence values, `now()` timestamps), which is
also exactly the access pattern BRIN block-range summaries serve best. The
extension has no answer for late-arriving out-of-order keys in a time pipeline —
"inserting old timestamps may cause data to be skipped" (`README.md:231`)
`[from-README]`; sequence pipelines are recommended precisely because the DB
generates the values `[from-README]`.

### 6. The drop-extension trigger is deliberately detached to outlive the extension

To clean up cron jobs on `DROP EXTENSION`, the install script registers an event
trigger `incremental_drop_extension_trigger` and then *removes it from the
extension* with `ALTER EXTENSION pg_incremental DROP EVENT TRIGGER …` /
`DROP FUNCTION …` / `DROP SCHEMA …` (`pg_incremental--1.0.sql:175-183`)
`[verified-by-code]`, "make sure the drop extension trigger survives the
extension to perform final cleanup" (`pg_incremental--1.0.sql:180`)
`[verified-by-code]`. On drop it runs `PERFORM cron.unschedule(jobname) … WHERE
jobname LIKE 'pipeline:%'` then `DROP SCHEMA incremental CASCADE`
(`pg_incremental--1.0.sql:161-167`) `[verified-by-code]`. A second event trigger
`pipeline_drop_trigger` on `SQL_DROP` auto-drops pipelines whose source table is
dropped (`pg_incremental--1.0.sql:124-150`) `[verified-by-code]`. Using event
triggers for lifecycle cleanup — and intentionally orphaning one from its own
extension so it can run *during* the extension's teardown — is an idiom most
extensions never reach for.

## Notable design decisions (cited)

- **One command per pipeline, validated up front.** `ParseQuery` rejects
  multi-statement commands ("pg_pipeline can only execute a single query in a
  pipeline", `src/query.c:21-23`) `[verified-by-code]`.
- **`max_batch_size` chunks huge backlogs.** A sequence pipeline caps the range
  to `rangeStart + maxBatchSize - 1` so a 100k-row burst is processed 10k at a
  time across successive cron ticks (`src/sequence.c:252-260`, `README.md:151`)
  `[verified-by-code]` / `[from-README]`.
- **Batched vs non-batched execution.** Time and file pipelines can run the
  command once per interval/file (non-batched) or once over the whole range/array
  (`src/time_interval.c:115-159`, `src/file_list.c:123-162`) `[verified-by-code]`;
  file batches are assembled into a `text[]` via `construct_array`
  (`src/file_list.c:225-230`) `[verified-by-code]`.
- **`skip_file` poisons a bad file.** Marking a file processed without running it
  lets a faulty input be skipped forever (`incremental_skip_file` →
  `InsertProcessedFile`, `src/pipeline.c:296-307`) `[verified-by-code]`.
- **Reset = zero the watermark.** `reset_pipeline` sets the last-processed marker
  back to 0 / clears `processed_files` (`ResetPipeline`, `src/pipeline.c:556-576`)
  `[verified-by-code]`; because progress is transactional, the README pattern
  wraps `DELETE FROM agg; reset_pipeline(...)` in one `BEGIN…COMMIT`
  (`README.md:386-391`) `[from-README]`.
- **File list function is pluggable and sanitized.** Defaults to
  `crunchy_lake.list_files` (Crunchy Data Warehouse) but any set-returning
  `(text) → path` function works; the name is validated and requalified via
  `LookupFuncName` + `quote_qualified_identifier`
  (`SanitizeListFunction`, `src/file_list.c:592-616`) `[verified-by-code]`.
- **Cron runs more often than work exists.** Jobs fire every minute and no-op
  when the range is empty ("pipeline %s: no rows to process",
  `src/sequence.c:99`, `README.md:361`) `[verified-by-code]` / `[from-README]`;
  every tick still shows in `cron.job_run_details`.
- **Shipped version is 1.5, not 1.0.** `default_version = '1.5'`
  (`pg_incremental.control`) `[verified-by-code]`; base install is
  `pg_incremental--1.0.sql` plus `--X--Y.sql` upgrade scripts (`Makefile:5`), and
  `create_file_list_pipeline` guards `PG_NARGS() != 9` with "Run ALTER EXTENSION
  pg_incremental UPDATE" (`src/pipeline.c:209-211`) `[verified-by-code]`.

## Links into corpus

- `[[knowledge/ideologies/pg_ivm]]` — the synchronous sibling: incremental view
  maintenance via query rewriter + AFTER triggers, updating on every statement.
  pg_incremental is *asynchronous and batched* — it accepts staleness (up to a
  cron interval) in exchange for zero write-path overhead and no standing
  triggers on base tables.
- `[[knowledge/ideologies/pipelinedb]]` — the maximal counterpart: a private
  bgworker process tree, an FDW-as-stream, and hand-rolled partial/combine
  aggregation. pg_incremental is the minimalist pole of the same "incrementally
  maintained aggregate" problem — SPI + cron + a lock-wait watermark, no resident
  processes.
- `[[knowledge/ideologies/pg_cron]]` — the scheduler pg_incremental delegates to
  entirely (`cron.schedule` / `cron.unschedule`), rather than owning a bgworker.
- `[[knowledge/ideologies/pg_partman]]` / `[[knowledge/ideologies/mimeo]]` —
  sibling "scheduled table maintenance driven by SQL + cron/bgworker" extensions;
  same compose-don't-reimplement posture toward scheduling.
- `[[knowledge/ideologies/pgmq]]` — an alternative "process each item once"
  primitive (a transactional queue with explicit read/archive), where
  pg_incremental instead derives the unprocessed set from a watermark or a
  set-difference against `processed_files`.
- `[[knowledge/ideologies/temporal_tables]]` — another time-window-oriented
  extension; useful contrast for how time ranges are modeled.
- `[[knowledge/idioms/spi]]` — every bookkeeping and command execution goes
  through `SPI_execute_with_args`.
- `[[knowledge/idioms/snapshot-acquisition]]` — `PushActiveSnapshot(GetTransactionSnapshot())`
  around each command; the watermark is the road-not-taken alternative to the
  xid-horizon primitives documented there.
- `[[knowledge/idioms/relation-extension-lock]]` — `WaitForLockers` on the source
  relation is the whole safety mechanism for sequence/time pipelines.
- `[[knowledge/idioms/process-utility-hook-chain]]` — `ExecuteCommand` builds a
  `CMD_UTILITY` `PlannedStmt` and calls `ProcessUtility` directly
  (`src/query.c:69-87`), the utility-dispatch entry point that idiom describes.
- `[[knowledge/idioms/fmgr]]` — the extension is pure fmgr composition
  (`PG_FUNCTION_INFO_V1` SQL-callable functions), no hooks.

## Anthropology takeaway

pg_incremental is the corpus's cleanest example of an extension that solves a
hard problem — incremental, exactly-once batch processing over a live stream — by
*subtracting* rather than adding machinery. Where `[[knowledge/ideologies/pg_ivm]]`
vendors three backend `.c` files and `[[knowledge/ideologies/pipelinedb]]` spins
up a bgworker hierarchy and an FDW, pg_incremental ships ~2,200 lines of C that do
nothing but: parse-validate a command, keep a watermark row, wait out concurrent
writers, run the command under a fresh snapshot, and record progress in the same
transaction. The exactly-once guarantee is not a protocol; it is a direct
consequence of running the progress update and the user command inside one
transaction and letting `ROLLBACK` handle failure. The "safe range" is not a
snapshot horizon; it is `WaitForLockers` plus `pg_sequence_last_value`. And the
scheduler is not a bgworker; it is a delegated pg_cron job. Two honest costs
follow: the correctness of the watermark rests on a *behavioral* assumption about
writers (sequence value drawn after the lock; `now()` with no clock jumps), which
the README states plainly (`README.md:218,231`); and the whole approach presumes
append-only, monotonically-keyed data best served by BRIN. For a
`knowledge/issues` note, pg_incremental is the counter-example to pg_ivm's "core
should export more internal APIs" argument: it demonstrates how far you can get
with only the *public* surface (SPI, fmgr, `WaitForLockers`, event triggers,
pg_cron) if you accept batch latency and constrain the data shape. Its one
self-aware conformance break — the deliberate `-Wdeclaration-after-statement`
override (`Makefile:16-17`) — reads as a statement of intent: this is a
pragmatic Crunchy Data tool, not an upstream-candidate patch.

## Sources

Fetched 2026-07-12 from `raw.githubusercontent.com/CrunchyData/pg_incremental/main/`.
Files were pulled as raw text via `curl` (HTTP 200) and read with line numbers, so
`file:line` cites are exact against branch `main` as of this date. The GitHub
git-trees / api.github.com endpoints are 403-blocked under the proxy; only raw
fetches were used, so the file set below was discovered by probing candidate paths.

- `README.md` @ 2026-07-12 → 200 (deep-read: pipeline types, exactly-once,
  watermark prose, BRIN guidance, per-type arg tables).
- `pg_incremental.control` @ 2026-07-12 → 200 (`default_version = '1.5'`,
  `schema = pg_catalog`, `relocatable = false`; no `requires`).
- `Makefile` @ 2026-07-12 → 200 (`SOURCES` wildcard, `-Iinclude`, the
  `-Wdeclaration-after-statement` filter-out at `:16-17`, psql-based installcheck).
- `pg_incremental--1.0.sql` @ 2026-07-12 → 200 (schema + 5 catalog tables, SQL
  function/procedure declarations, both event triggers, the `ALTER EXTENSION …
  DROP` detachment).
- `src/pipeline.c` @ 2026-07-12 → 200 (641 lines; deep-read: create/execute/reset/
  drop entry points, `ReadPipelineDesc`, `EnsurePipelineOwner`, superuser switch,
  cron job name/command).
- `src/sequence.c` @ 2026-07-12 → 200 (355 lines; deep-read: `GetSequenceNumberRange`,
  `PopSequenceNumberRange` + `WaitForLockers`, `pg_sequence_last_value`,
  `max_batch_size`, same-txn progress update).
- `src/time_interval.c` @ 2026-07-12 → 200 (390 lines; deep-read: `date_bin`
  watermark, optional `WaitForLockers`, batched/non-batched loop).
- `src/file_list.c` @ 2026-07-12 → 200 (616 lines; deep-read: LEFT JOIN
  set-difference against `processed_files`, batching/`construct_array`,
  `SanitizeListFunction`, `InsertProcessedFile`).
- `src/cron.c` @ 2026-07-12 → 200 (99 lines; `ScheduleCronJob`/`UnscheduleCronJob`,
  pg_cron presence check).
- `src/query.c` @ 2026-07-12 → 200 (87 lines; `ParseQuery`, `DeparseQuery`,
  `ExecuteCommand`/`ProcessUtility`).
- `include/crunchy/incremental/pipeline.h` @ 2026-07-12 → 200 (type tags,
  `PipelineDesc`). Also fetched: `sequence.h`, `time_interval.h`, `file_list.h`,
  `cron.h`, `query.h` (prototypes only, not separately cited).

**Manifest gaps / 404s** (probed, not present on `main`): `meson.build`,
`src/incremental.c`, `src/pg_incremental.c`, `src/utils.c`, `src/snapshot.c`,
`src/watermark.c`, and any `src/crunchy/incremental/*.c` subdir — the C sources
are flat under `src/` (`pipeline.c`, `sequence.c`, `time_interval.c`,
`file_list.c`, `cron.c`, `query.c`). Upgrade scripts (`pg_incremental--1.4--1.5.sql`
etc.) and the `docker/` test harness were referenced in README/Makefile but not
fetched; version-history claims rest on `README.md:249` and the control file
(`[from-README]` / `[verified-by-code]`). No `_PG_init` exists in the tree — the
"no bgworker, no hook" characterization is `[verified-by-code]` by absence across
all six fetched C files.
