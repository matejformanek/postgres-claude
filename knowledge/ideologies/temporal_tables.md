# temporal_tables — SQL:2011 system-versioning faked from userspace, as a C BEFORE-trigger that SPI-inserts the prior row image into a separately-named history table

> Ideology note produced by the `pg-extension-anthropologist` cloud routine.
> Repo: `arkhipov/temporal_tables` @ branch `master`. All `file:line` cites point
> into that repo (not `source/`). Cites verified against files fetched on
> 2026-06-13 (see Sources footer). The trigger body lives in `versioning.c`; the
> process-global transaction-time state machine lives in `temporal_tables.c` +
> `temporal_tables.h`. Read alongside `[[knowledge/idioms/fmgr]]`,
> `[[knowledge/idioms/spi]]`, `[[knowledge/idioms/memory-contexts]]`, and
> `[[knowledge/ideologies/pg_ivm]]` (the other corpus extension that drives
> derived-table maintenance from triggers + SPI rather than the rewriter).

## Domain & purpose

A temporal table "records the period of time when a row is valid" — the **system
period** (transaction-time) is a system-maintained `tstzrange` column whose start
is set when a row becomes current and whose old value is archived on UPDATE/DELETE
into a separate **history table** (`README.md:9-18`) `[from-README]`. The
extension targets the SQL:2011 *system_time* period semantics, but the README is
explicit that only the system period is implemented, not the application period
(`README.md:30-31`) `[from-README]`. Everything is wired by one C trigger
function, `versioning(period_column, history_table, adjust)`, declared
`FOR EACH ROW EXECUTE PROCEDURE` on `BEFORE INSERT OR UPDATE OR DELETE`
(`README.md:174-179`, `temporal_tables--1.2.2.sql:6-9`) `[verified-by-code]`.

The reason to document it: this is the corpus's cleanest example of a feature that
core Postgres **does not have natively** (PG has no system-versioned tables; the
SQL:2011 `FOR SYSTEM_TIME` syntax is absent from core) being reconstructed
entirely from the public extension surface — the C trigger API, the typcache, the
range-type API, and SPI — without touching the rewriter, the executor, or any
catalog. It is system-versioning as a *convention*, not as an engine feature.

## How it hooks into PG

Two SQL-visible C functions, both `LANGUAGE C`, no new types or operators
(`temporal_tables--1.2.2.sql:6-18`) `[verified-by-code]`:

- `versioning()` — `RETURNS TRIGGER`, `STRICT`, with `REVOKE ALL … FROM PUBLIC`
  (`temporal_tables--1.2.2.sql:6-11`). The whole feature.
- `set_system_time(timestamptz)` — `RETURNS VOID`, a test/ETL override for the
  transaction-time source (`temporal_tables--1.2.2.sql:15-18`) `[verified-by-code]`.

`_PG_init` does **not** install any hook; instead it seeds a process-global
`TemporalContext` stack in `TopMemoryContext` and registers transaction +
subtransaction callbacks (`RegisterXactCallback`, `RegisterSubXactCallback`,
`temporal_tables.c:33-61`) `[verified-by-code]` — the only "engine" wiring the
extension does is to ride the transaction lifecycle so that `set_system_time`
respects rollback.

Both entry points are `PG_FUNCTION_INFO_V1` with explicit `PGDLLEXPORT Datum
…(PG_FUNCTION_ARGS)` prototypes (`versioning.c:56-60`) `[verified-by-code]`. The
control file is bare: `relocatable = true`, default version `1.2.2`, no
`requires` (`temporal_tables.control:1-5`) `[verified-by-code]`. Note the
*extension* name is `temporal_tables` but the comment is `'temporal tables'` and
the only user-facing object family is `versioning` — a naming split worth
remembering when grepping.

Cross-ref `[[knowledge/idioms/fmgr]]`, `[[knowledge/idioms/spi]]`,
`.claude/skills/fmgr-and-spi/SKILL.md`, `.claude/skills/error-handling/SKILL.md`.

## Where it diverges from core idioms

### 1. SQL:2011 system-versioning as a BEFORE-trigger AFTER-image, not an engine feature

Core has no system-versioned tables and no `FOR SYSTEM_TIME` query rewriting. This
extension reconstructs the semantics from the trigger contract alone. `versioning`
hard-asserts its calling context: `CALLED_AS_TRIGGER(fcinfo)` else an
`ERRCODE_E_R_I_E_TRIGGER_PROTOCOL_VIOLATED` error (`versioning.c:218-221`), and it
further insists on `TRIGGER_FIRED_BEFORE` + `TRIGGER_FIRED_FOR_ROW`
(`versioning.c:224-228`) and an event in `{INSERT,UPDATE,DELETE}`
(`versioning.c:230-235`) `[verified-by-code]`. The `tg_event` bitmask then routes
to `versioning_insert` / `_update` / `_delete` (`versioning.c:286-296`)
`[verified-by-code]`.

The choice of **BEFORE** (not AFTER) is load-bearing: a BEFORE-row trigger's
return value *replaces the tuple the executor proceeds with*. `versioning_insert`
returns a `modify_tuple(…, tg_trigtuple, …)` carrying the new `[system_time, )`
range (`versioning.c:940`); `versioning_update` returns a modified `tg_newtuple`
with the fresh current period (`versioning.c:1014`); `versioning_delete` returns
the unmodified `tg_trigtuple` so the delete proceeds (`versioning.c:1070`)
`[verified-by-code]`. So the *current-row* period is stamped by mutating the tuple
the trigger hands back, while the *prior image* is pushed to history via SPI as a
side effect (next point). This is the inverse of how core system-versioning would
work — there the engine owns both images; here the trigger fabricates them.

### 2. The history row is an SPI INSERT of a hand-built, column-projected tuple — not a rule, not a rewrite

Archiving the old version is a literal `INSERT INTO <history> (cols…) VALUES
($1,…)` built as a string and run through SPI. `insert_history_row` opens the
history relation by name (`makeRangeVarFromNameList(stringToQualifiedNameList(…))`
→ `heap_openrv(relrv, AccessShareLock)`, `versioning.c:628-634`), `SPI_connect`s
(`versioning.c:701`), extracts the common-column datums from the prior tuple with
`SPI_getbinval` (`versioning.c:735`), and fires a **cached prepared plan** via
`SPI_execp(plan, values, nulls, 0)` expecting `SPI_OK_INSERT`
(`versioning.c:739-740`) `[verified-by-code]`. The plan text itself is assembled
in `fill_versioning_hash_entry` by walking the versioned relation's `TupleDesc`,
matching each non-dropped column by **name** against the history `TupleDesc`
(`SPI_fnumber`), type-checking it, and appending `quote_identifier`'d column names
and `$N` placeholders (`versioning.c:497-567`) `[verified-by-code]`.

This is the pg_ivm pattern (trigger + SPI-driven derived-table maintenance), but
where pg_ivm forks core `.c` files, temporal_tables stays entirely in public API.
The cost: the history schema is matched **structurally by column name+type at
runtime**, so the history table "does not have to have the same structure" — only
the common columns are copied, and the `sys_period` column must exist with the
same name and type (`README.md:160-169`, enforced at `versioning.c:472-478` and
`check_attr_type`, `versioning.c:423-443`) `[verified-by-code]`. Contrast core's
absent native feature, where the history relation would be engine-managed.

### 3. Transaction-time comes from `GetCurrentTransactionStartTimestamp` — overridable by a process-global static

The "now" stamped into every period is **statement/transaction-start time, not
wall clock**: `get_system_time` returns `GetCurrentTransactionStartTimestamp()` in
the default mode (`versioning.c:326-343`) `[verified-by-code]`, and the README
confirms the start of `sys_period` "is a CURRENT_TIMESTAMP value which denotes the
time when the first data change statement was executed in the current
transaction" (`README.md:212-215`) `[from-README]`. So all rows touched in one
transaction share one timestamp — which is why "if a single transaction makes
multiple updates to the same row, only one history row is generated"
(`README.md:222-223`) `[from-README]` is even coherent.

The override is the sharp part. `set_system_time` flips a `SystemTimeMode` enum
(`CurrentTransactionStartTimestamp` vs `UserDefined`) and stores a `TimestampTz`
in the *current* `TemporalContext` (`versioning.c:304-320`,
`temporal_tables.h:17-36`) `[verified-by-code]`. That context lives on a
**file-scope `List *temporal_contexts` stack rooted in `TopMemoryContext`**
(`temporal_tables.c:31, 47-53`) `[verified-by-code]` — i.e. it is *per-backend
process-global state*, not session-GUC and not transaction-local storage. Its
transactional behavior is hand-rolled: `set_system_time` pushes a copy onto the
stack scoped to the current subxact (`get_current_temporal_context(true)` →
`push_temporal_context`, `versioning.c:307`, `temporal_tables.c:71-89,162-179`),
and the xact/subxact callbacks pop-and-propagate on commit or discard on abort
(`temporal_tables.c:96-160`) `[verified-by-code]`. This is exactly the README's
contract: "If the `set_system_time` function is issued within a transaction that
is later aborted, all the changes are undone. If the transaction is committed, the
changes will persist until the end of the session" (`README.md:339-341`)
`[from-README]`.

Implication to flag: because the override survives commit and lives in
backend-global memory, a `set_system_time('past')` left set by one statement
**silently back-dates every subsequent versioning operation in that session** until
reset with `set_system_time(NULL)` (`README.md:332-337`) `[from-README]`. It is a
hidden, connection-pool-unsafe ambient input to a data-modifying trigger — a
property core's transaction-time machinery would never expose.

### 4. The `sys_period` column is found by name and validated by typcache at trigger time

There is no catalog binding of "this column is the system period." The trigger
takes the column *name* as `tgargs[0]` and resolves it per-fire:
`SPI_fnumber(tupdesc, period_attname)` → `SPI_ERROR_NOATTRIBUTE` is an
`ERRCODE_UNDEFINED_COLUMN` error (`versioning.c:253-263`) `[verified-by-code]`. It
then rejects a dropped attr (`attisdropped`, `versioning.c:267-273`) and an array
(`attndims != 0`, `versioning.c:276-281`). The type check is via the **typcache**:
`get_period_typcache` does a `SearchSysCache1(TYPEOID, …)`, requires
`typtype == TYPTYPE_RANGE`, then `range_get_typcache(fcinfo, typoid)` and requires
`typcache->rngelemtype->type_id == TIMESTAMPTZOID` — anything else is an
`ERRCODE_DATATYPE_MISMATCH` (`versioning.c:373-417`) `[verified-by-code]`. So the
"system period must be `tstzrange`" rule is enforced dynamically against the live
typcache, not by a column constraint. The range itself is dismantled with
`range_deserialize` and rebuilt with `make_range` over `RangeBound`s
(`deserialize_system_period`, `versioning.c:758-793`; `make_range` at
`:935,990,1009,1060`) `[verified-by-code]` — full use of the range-type internals
an extension is allowed to touch.

### 5. Per-backend caching of the history plan + tupdescs, with manual invalidation

To avoid re-`SPI_prepare`ing the INSERT on every row, the extension keeps a
backend-local `HTAB` keyed by the versioned relation OID
(`VersioningHashEntry`, `versioning.c:66-88`; `hash_create` with `HASH_BLOBS` in
`TopMemoryContext` via a custom `ctl.alloc`, `versioning.c:1082-1104`)
`[verified-by-code]`. The cached plan is pinned with `SPI_keepplan`
(`versioning.c:576-579`), and the copied tupdescs are `CreateTupleDescCopyConstr`'d
into `TopMemoryContext` (`versioning.c:583-593`) `[verified-by-code]`. Because
there is **no relcache invalidation callback**, staleness is detected by hand on
each use: the entry is invalidated if `natts == -1`, the history OID drifted, or
either `equalTupleDescs` comparison fails, in which case it frees the plan
(`SPI_freeplan`) and tupdescs and refills (`versioning.c:661-698`)
`[verified-by-code]`. This is a deliberate divergence from the idiomatic
`CacheRegisterRelcacheCallback` route — it trades correctness-by-invalidation for
correctness-by-revalidation, and it means a concurrent DDL that changes the
history schema is caught only on the next trigger fire.

### 6. Memory-context discipline: scratch in the trigger context, durable state in TopMemoryContext

The trigger does its per-row scratch allocations (the `StringInfo` query buffer,
`attnums`/`history_attnums`/`argtypes`, the `values`/`nulls` SPI arrays) in the
ambient (per-tuple/SPI) context and `pfree`s them explicitly
(`versioning.c:581,602-603,742-743`) `[verified-by-code]`, while anything that must
outlive the call — the cached plan, tupdesc copies, and `attnums` array — is
allocated under an explicit `MemoryContextSwitchTo(TopMemoryContext)` /
restore pair (`versioning.c:583-593`) `[verified-by-code]`. The
`TemporalContext` stack nodes are likewise placed deliberately:
`TopMemoryContext` for the never-freed root (so it survives transaction
boundaries, `temporal_tables.c:44-53`) and `TopTransactionContext` for pushed
subxact copies that may be discarded on abort (`temporal_tables.c:77-86`)
`[verified-by-code]`. Cross-ref `[[knowledge/idioms/memory-contexts]]`,
`.claude/skills/memory-contexts/SKILL.md`.

## Notable design decisions (cited)

- **Idempotent within a transaction.** Both UPDATE and DELETE paths early-return
  without writing history when the row's xmin is the current transaction —
  `modified_in_current_transaction` is `TransactionIdIsCurrentTransactionId(
  HeapTupleHeaderGetXmin(tuple->t_data))` (`versioning.c:883-890`, used at
  `:973-974` and `:1043-1044`) `[verified-by-code]`. This is why a multi-update
  transaction archives the prior version only once (`README.md:222-223`)
  `[from-README]`, and it is a direct read of heap-tuple visibility internals from
  a trigger.
- **The `adjust` parameter resolves write-write period collisions.** If the
  computed lower bound is `>=` the system time (a row updated by a concurrent,
  later-committed transaction), `adjust_system_period` either errors with a
  bespoke `ERRCODE_DATA_EXCEPTION` (when `adjust='false'`) or nudges the upper
  bound to `next_timestamp(lower)` and raises a custom
  `ERRCODE_WARNING_SYSTEM_PERIOD_ADJUSTED` SQLSTATE `01X01`
  (`versioning.c:62-63,848-878`) `[verified-by-code]`. The README's T1..T6
  conflict scenario is the motivating case (`README.md:244-294`) `[from-README]`.
- **`next_timestamp` reaches into `integer_datetimes`.** The "+1 microsecond"
  delta branches on whether timestamps are int64 or float8, looked up once via
  `GetConfigOption("integer_datetimes", …)` and cached in a static; the float path
  falls back to `nextafter(ts, DBL_MAX)` (`versioning.c:798-840`)
  `[verified-by-code]` — a relic of pre-PG10 float-timestamp builds.
- **`STRICT` + 3-arg trigger contract.** `versioning()` is declared with zero SQL
  args but reads exactly 3 trigger args (`tgnargs != 3` is an error,
  `versioning.c:240-245`) `[verified-by-code]`; the SQL signature is a placeholder
  and all configuration flows through `CREATE TRIGGER … EXECUTE PROCEDURE
  versioning('sys_period','employees_history',true)` (`README.md:174-179`).
- **`relocatable = true`, `REVOKE ALL … FROM PUBLIC`** on the trigger function
  (`temporal_tables.control:5`, `temporal_tables--1.2.2.sql:11`) — install-time
  hardening so non-owners can't attach the versioning trigger arbitrarily.

## Links into corpus

- `[[knowledge/idioms/fmgr]]` — `PG_FUNCTION_INFO_V1` trigger entry point,
  `CALLED_AS_TRIGGER`, `fcinfo->context` cast to `TriggerData *`, the BEFORE-row
  modified-tuple return contract.
- `[[knowledge/idioms/spi]]` — `SPI_connect`/`SPI_prepare`/`SPI_keepplan`/
  `SPI_execp`/`SPI_finish`, `SPI_getbinval`/`SPI_fnumber`/`SPI_gettypeid`, cached
  prepared-plan reuse keyed by relation OID.
- `[[knowledge/idioms/memory-contexts]]` — scratch-in-ambient vs durable-in-
  `TopMemoryContext`, the `TopTransactionContext` subxact copies, the custom
  `HASHCTL.alloc`.
- `[[knowledge/ideologies/pg_ivm]]` — the sibling "maintain a derived table from
  AFTER/BEFORE triggers + SPI instead of the rewriter" ideology; pg_ivm forks core
  `.c` files, temporal_tables stays in public API — a useful trigger-vs-rewriter,
  public-API-vs-core-fork contrast.
- `[[knowledge/subsystems/access-heap]]` — `HeapTupleHeaderGetXmin` +
  `TransactionIdIsCurrentTransactionId` read from the trigger for the
  once-per-xact idempotence check.
- `[[knowledge/subsystems/utils-cache]]` — typcache (`range_get_typcache`,
  `SearchSysCache1(TYPEOID)`) used to validate the period column's range/element
  type at trigger time; note the *absence* of a relcache invalidation callback.
- `.claude/skills/fmgr-and-spi/SKILL.md`, `.claude/skills/memory-contexts/SKILL.md`,
  `.claude/skills/error-handling/SKILL.md`.

## Anthropology takeaway

temporal_tables is the corpus's purest "core feature reconstructed from userspace"
artifact: SQL:2011 system-versioning — which Postgres has no native engine for —
delivered by one C BEFORE-row trigger that fabricates both row images (mutating
the returned tuple for the current version, SPI-inserting a name-and-type-matched
projection for the archived version) and stamps them with transaction-start time.
The two sharpest divergences are (a) the **trigger-vs-engine** architecture: the
history table is bound by *string name* in a trigger argument and revalidated by
hand on every fire (no catalog relationship, no relcache invalidation callback —
just `equalTupleDescs` re-checks), so what core would make an integrity invariant
is here a runtime convention; and (b) the **transaction-time override as a
process-global static stack** — `set_system_time` mutates backend-global memory
that survives commit until session end and is rolled back via hand-registered
xact/subxact callbacks rather than living in a GUC or transaction-scoped store.
That second one is the cautionary flag for any `knowledge/issues` note: a
data-modifying trigger whose timestamp source is a hidden, connection-pool-unsafe
ambient variable that, once set, back-dates every subsequent write in the session.
The whole thing is a model of "how far the public trigger + SPI + typcache +
range-type API can carry you" — and exactly where it stops being safe.

## Sources

Fetched 2026-06-13 (branch `master`):

- `https://raw.githubusercontent.com/arkhipov/temporal_tables/master/README.md`
  @ 2026-06-13 → HTTP 200 (16923 bytes; deep-read — semantics, usage, conflict
  model, set_system_time contract).
- `.../master/temporal_tables.c` @ 2026-06-13 → HTTP 200 (4918 bytes; deep-read —
  `_PG_init`, TemporalContext stack, xact/subxact callbacks).
- `.../master/temporal_tables.h` @ 2026-06-13 → HTTP 200 (1178 bytes; the
  `SystemTimeMode` enum + `TemporalContext` struct).
- `.../master/versioning.c` @ 2026-06-13 → HTTP 200 (31914 bytes; deep-read — the
  `versioning`/`set_system_time` entry points, history INSERT plan build + SPI
  exec, typcache validation, period (de)serialization, adjust logic, per-backend
  hash cache). This file holds the actual trigger; the prompt-listed
  `versioning_function.c` does not exist.
- `.../master/temporal_tables.control` @ 2026-06-13 → HTTP 200 (140 bytes).
- `.../master/temporal_tables--1.2.2.sql` @ 2026-06-13 → HTTP 200 (696 bytes; the
  two `CREATE FUNCTION`s + REVOKE).
- `.../master/versioning_function.c` @ 2026-06-13 → HTTP 404 (14 bytes). The
  trigger source is `versioning.c`, not `versioning_function.c`.
- `.../master/set_system_time.c` @ 2026-06-13 → HTTP 404 (14 bytes).
  `set_system_time` is defined inside `versioning.c:304-320`, not a separate file.

All cites are `[verified-by-code]` against the fetched `versioning.c` /
`temporal_tables.c` / `temporal_tables.h` / `.control` / install SQL, except the
end-user semantics (conflict model, multi-update-once-per-xact, the
set_system_time persistence-across-commit contract, the system-period-only scope),
which are `[from-README]` and cross-checked against the matching code paths.
