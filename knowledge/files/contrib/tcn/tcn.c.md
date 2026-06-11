# `contrib/tcn/tcn.c`

- **Last verified commit:** `e18b0cb7344`
- **Lines:** ~184
- **Source:** `source/contrib/tcn/tcn.c`

Single-function extension implementing
`triggered_change_notification()`, a generic AFTER-ROW trigger that
emits a LISTEN/NOTIFY payload describing each insert/update/delete:
`"<tablename>",I,"<pkcol1>"='val1',"<pkcol2>"='val2',…`. The notify
channel is `tcn` by default or the trigger's single argument if
given. Requires the target table to have a PRIMARY KEY.
[verified-by-code]

## API / entry points

- `triggered_change_notification` (tcn.c:56-184) — PG_FUNCTION_INFO_V1
  trigger function. Validates that the call is from a trigger, is an
  AFTER trigger, is row-level, has ≤ 1 argument; then determines
  operation (`I`/`U`/`D`), finds the table's primary key via
  `RelationGetIndexList` + INDEXRELID syscache, builds the comma-
  separated payload, and calls `Async_Notify(channel, payload.data)`.
  [verified-by-code]
- `strcpy_quoted` (tcn.c:35-47) — helper that wraps a string in a
  given quote char and doubles any embedded occurrence. Used to
  produce SQL-style identifier (`"…"`) and literal (`'…'`) quoting
  inside the payload. [verified-by-code]

## Notable invariants / details

- Only one trigger argument is accepted (tcn.c:108-111). Multi-arg
  setups raise `ERRCODE_E_R_I_E_TRIGGER_PROTOCOL_VIOLATED`.
  [verified-by-code]
- The PK is located by iterating `RelationGetIndexList` and looking
  for the index with `indisprimary && indisvalid` (tcn.c:130-144).
  Comment "hopefully there isn't more than one such" — PG enforces
  at most one PK per relation so this is safe. [verified-by-code]
  [from-comment] [ISSUE-undocumented-invariant: relies on catalog
  invariant "at most one indisprimary index per relation" (nit)]
- Per-key data is read via `SPI_getvalue(trigtuple, tupdesc, colno)`
  (tcn.c:165) — uses the type's output function to render each PK
  column as a SQL string literal. Note: SPI_getvalue returns a
  palloc'd C string; this code does NOT pfree those. The trigger
  function's per-tuple memory context is reset at the next ExecQual
  so this is a per-row leak that doesn't escape the txn.
  [verified-by-code] [ISSUE-leak: SPI_getvalue palloc'd strings
  not pfree'd (nit)]
- `Async_Notify(channel, payload.data)` queues the notification; it
  fires on transaction commit. If the txn aborts, no notify is sent
  — visibility matches NOTIFY's general semantics, NOT the trigger
  protocol's "after the change" framing. So consumers will only ever
  see committed changes. [verified-by-code] [from-comment]
- Quote-doubling is applied to both the table name and each PK
  column value (tcn.c:153, 163, 165). The relname inside the
  payload uses `"` wrapping; values use `'` wrapping. Parsers on
  the consumer side must therefore unquote two different schemes.
  [verified-by-code]
- The function has no superuser check; any user with CREATE TRIGGER
  on a table can install it. The notification queue is process-
  global and shared via the postmaster's async backend.
  [verified-by-code]

## Potential issues

- tcn.c:178-181. If the table has **no PK or only an invalid PK**, the
  function errors out with `ERRCODE_E_R_I_E_TRIGGER_PROTOCOL_VIOLATED`.
  This means an ALTER TABLE … DROP CONSTRAINT on the PK while the
  trigger is installed turns every subsequent INSERT/UPDATE/DELETE
  into a hard error. No fallback to "notify without PK info" is
  attempted. [ISSUE-correctness: missing-PK turns trigger into row-
  level error (likely)]
- tcn.c:139-141. The cache-lookup-fail elog is "should not happen"
  but is `ERROR` level, so the user sees an internal-style error if
  the catalog is concurrently mutated. [ISSUE-style: defensive elog
  surfaces to user (nit)]
- tcn.c:165. **`SPI_getvalue` results not pfree'd**; the per-row
  allocations live until the executor's per-tuple context resets.
  For a transaction that updates millions of rows under this
  trigger, the cumulative footprint depends on context-reset
  frequency. Not a true leak, but a noticeable peak-memory
  concern in bulk loads. [ISSUE-leak: per-row palloc accumulation
  (maybe)]
- tcn.c:168. **Payload size unbounded**. Each pk column adds
  `,colname='value'`. NOTIFY payload size is hard-limited by
  `NOTIFY_PAYLOAD_MAX_LENGTH` (8000 bytes); tables with very long
  text PKs or many-column composite PKs can overflow and Async_Notify
  will raise. No defensive truncation here; comment block does not
  warn. [ISSUE-correctness: silent dependence on NOTIFY size limit
  (maybe)]
- tcn.c:170-173. `ReleaseSysCache(indexTuple)` is called twice on
  the matching branch path: at line 170 (inside `if foundPK`) AND at
  line 173 (after the if). Wait — re-reading: at line 170 the
  release-and-break is inside the `if (indisprimary && indisvalid)`
  branch and exits the loop; line 173 is the fall-through release
  for indexes that did NOT match. Each iteration releases exactly
  one tuple. Actually correct. [verified-by-code]
- tcn.c:107-111. Two-or-more-args case errors but **zero-args is
  silently allowed** (line 113-114, channel defaults to `"tcn"`).
  Fine but users may not realise default. [ISSUE-doc-drift: default
  channel not in source comment (nit)]
- tcn.c:120-121. `trigdata->tg_trigtuple` is used regardless of
  operation, including UPDATE. For UPDATE this is the OLD row; for
  INSERT and DELETE it's the actual row. The PK is generally stable
  across UPDATE so OLD vs NEW PK is usually identical — but UPDATEs
  that change PK columns will notify the OLD PK, which is what
  consumers actually need to look up the row that became
  inaccessible. Probably intentional, but unstated.
  [ISSUE-undocumented-invariant: UPDATE always emits OLD PK (nit)]

## Cross-references

- `knowledge/issues/tcn.md` — per-extension issue register (create
  from template if absent).
- `source/src/backend/commands/async.c` — `Async_Notify` semantics,
  `NOTIFY_PAYLOAD_MAX_LENGTH`.
- `source/src/backend/utils/cache/relcache.c` —
  `RelationGetIndexList`.
- `knowledge/idioms/trigger-functions.md` for the
  `CALLED_AS_TRIGGER`/`TRIGGER_FIRED_*` discipline.
