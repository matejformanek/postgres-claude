# contrib/lo/lo.c

**Pin:** `4b0bf0788b066a4ca1d4f959566678e44ec93422`
**LOC:** 114
**Verification depth:** full read

## Role

Provides the `lo_manage` trigger function that auto-unlinks an orphaned
Large Object when the row holding its OID is deleted or the OID column is
overwritten with a different value (or set NULL).  The trigger is meant to
be attached to user tables via `CREATE TRIGGER ... EXECUTE FUNCTION
lo_manage('column_name')` to keep `pg_largeobject` from accumulating
zombies.
[verified-by-code] `source/contrib/lo/lo.c:1-24`

## Public API

- `lo_manage(PG_FUNCTION_ARGS)` — PG_FUNCTION_INFO_V1; trigger function,
  must be fired BEFORE/AFTER ROW UPDATE or DELETE on a table.
  [verified-by-code] `source/contrib/lo/lo.c:24-114`

## Invariants

- INV-1: Must be invoked via the trigger manager (`CALLED_AS_TRIGGER` check)
  and must be a row-level trigger (`TRIGGER_FIRED_FOR_ROW`).
  [verified-by-code] `source/contrib/lo/lo.c:38-43`
- INV-2: Trigger args must include the LO column name; absence is an
  internal error.
  [verified-by-code] `source/contrib/lo/lo.c:53-55`
- INV-3: On UPDATE, the OID column must actually be in `tg_updatedcols`
  (the bitmapset of changed columns) before the trigger considers
  unlinking — avoids spurious unlinks if only other columns changed.
  [verified-by-code] `source/contrib/lo/lo.c:79-80`
- INV-4: Unlink fires only if old OID is non-NULL AND (new OID is NULL OR
  the two strings differ). I.e. the LO is dropped iff the row no longer
  references it.
  [verified-by-code] `source/contrib/lo/lo.c:85-87`

## Notable internals

- The OID is retrieved as TEXT via `SPI_getvalue` and then converted via
  `atooid` — older textual-IO path. (Why TEXT not OID? Probably because
  this predates the modern tg_trigtuple binary access pattern.)
  [verified-by-code] `source/contrib/lo/lo.c:82-83, 102`
- Unlinks via `DirectFunctionCall1(be_lo_unlink, OID)` — the backend
  large-object delete function, which acquires the necessary locks on
  `pg_largeobject` rows.
  [verified-by-code] `source/contrib/lo/lo.c:86-87, 106-107`
- DELETE branch ignores `tg_updatedcols` (not relevant) and just unlinks
  the orphaned LO.
  [verified-by-code] `source/contrib/lo/lo.c:100-111`

## Trust-boundary / Phase-D surface

- **Not a SQL-callable function in normal sense** — must be invoked via
  trigger context. A direct `SELECT lo_manage()` errors out at line 38-39.
- **`bms_is_member(attnum - FirstLowInvalidHeapAttributeNumber, ...)`**
  uses the standard bitmap convention. The attnum returned by
  `SPI_fnumber(tupdesc, args[0])` is 1-based; the call shifts by
  `FirstLowInvalidHeapAttributeNumber` (= -7) to match the
  `tg_updatedcols` encoding.
  [verified-by-code] `source/contrib/lo/lo.c:80`
- **Privilege escalation?** `be_lo_unlink` runs with the trigger
  invoker's privileges (no SECURITY DEFINER chaining here). A user who
  can issue UPDATE/DELETE on the user table will be able to unlink
  LOs whose OIDs are in the column — which is the whole point.
- **No path/string injection** — only integer-via-text conversion via
  `atooid`.  Malformed OID strings parse to 0 silently
  (`atooid` returns 0 on garbage); `be_lo_unlink(0)` will error out.
  **ISSUE-D1 (info)**: garbage strings silently become OID 0; the
  unlink will then error with "large object 0 does not exist" rather
  than telling the operator "column had garbage". Diagnostic, not
  security.
- **LO oids do leak via the diagnostic ereports** of be_lo_unlink (a
  failed unlink reveals OID).  Not exploitable — invoker already has
  the OID in the row.
- **No SPI_connect/finish ceremony** — the trigger uses `SPI_*` helpers
  (`SPI_fnumber`, `SPI_getvalue`) WITHOUT calling `SPI_connect()`. This
  is actually wrong-looking but legal: these particular SPI helpers
  are pure tuple-formatting utilities that don't require an SPI
  connection. (See `executor/spi.c` comments.) **ISSUE-D2 (info)**:
  this is an idiom worth documenting — SPI prefixes don't always mean
  "needs SPI_connect".
  [from-comment] / [inferred] from absence of SPI_connect/SPI_finish
  in this file plus the working module.

## Cross-refs

- `source/src/backend/utils/adt/lo.c` (or `genfile.c`) — `be_lo_unlink`.
- `source/src/backend/storage/large_object/inv_api.c` — LO storage.
- A8: trigger infrastructure (`src/backend/commands/trigger.c`).

## Issues raised

- **ISSUE-D1 (info)** — garbage in the OID-column produces a confusing
  "LO 0 does not exist" error instead of a clear "column had garbage".
- **ISSUE-D2 (info)** — uses `SPI_*` helpers without `SPI_connect()`.
  Legal but easy to misread as a bug.

## Synthesized by
<!-- backlinks:auto -->
- [subsystems/contrib-lo.md](../../../subsystems/contrib-lo.md)

- [idioms/spi.md](../../../idioms/spi.md)