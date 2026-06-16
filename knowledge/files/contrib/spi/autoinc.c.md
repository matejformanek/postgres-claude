# `contrib/spi/autoinc.c`

- **Last verified commit:** `e18b0cb7344`
- **Lines:** 130
- **Source:** `source/contrib/spi/autoinc.c`

Tutorial-example trigger function showing how to wire a BEFORE-row trigger
to auto-populate INT4 columns from a sequence on INSERT/UPDATE if the
column is currently NULL or zero. Despite living under `contrib/spi/`
the module does NOT actually use SPI for query execution — it uses
`DirectFunctionCall1(nextval, ...)` and `heap_modify_tuple_by_cols`
directly. (The `SPI_fnumber`, `SPI_gettypeid`, `SPI_getbinval`,
`SPI_getrelname` helpers don't need an `SPI_connect`/`SPI_finish`
bracket — they're tuple-level utility wrappers.) [verified-by-code]

## API / entry points

- `autoinc(PG_FUNCTION_ARGS)` `:21-130` — the only function. Must
  be installed as a BEFORE-ROW trigger on INSERT or UPDATE with an
  even number of trigger arguments: `(col1, seq1, col2, seq2, …)`. [verified-by-code]

## The pattern (what this file teaches)

1. **Standard trigger guards**: `CALLED_AS_TRIGGER`,
   `TRIGGER_FIRED_FOR_ROW`, `TRIGGER_FIRED_BEFORE` — all are `elog(ERROR, "internal error")` because they indicate misconfiguration, not user error. `:39-47` [verified-by-code]
2. **INSERT vs UPDATE tuple selection**: `tg_trigtuple` for INSERT,
   `tg_newtuple` for UPDATE. DELETE rejected. `:49-55` [verified-by-code]
3. **`SPI_fnumber(tupdesc, name)` → attnum** lookup. Returns ≤ 0 if
   the column does not exist (`:80-84`). [verified-by-code]
4. **`SPI_gettypeid(tupdesc, attnum)` → typeid** for type-asserting
   the target column is `INT4OID`. [verified-by-code]
5. **`SPI_getbinval(tuple, tupdesc, attnum, &isnull)` → Datum**
   read of the existing value. [verified-by-code]
6. **Only overwrite if NULL or zero** (`!isnull && val != 0` →
   skip). `:94-98` [verified-by-code]
7. **`DirectFunctionCall1(nextval, ...)`** invoked manually (no SPI
   plan). `nextval` returns `int64`; explicitly down-cast to `int32`.
   `:103-105` [verified-by-code]
8. **Loop-on-zero**: if `nextval` happens to return 0 (sequence's
   first call on a sequence whose start is 0, or wrap-around), call
   it again. `:106-110` [verified-by-code]
9. **Batch the writes via `heap_modify_tuple_by_cols`** rather than
   `heap_modify_tuple` so unmodified columns avoid recompute.
   `:117-122` [verified-by-code]
10. **Return `PointerGetDatum(rettuple)`** — BEFORE triggers must
    return the row they want the executor to insert/update.
    `:129` [verified-by-code]

## Notable invariants / details

- **INV-1: Sequence name is passed as a trigger ARGUMENT (string),
  not a column reference.** Each `(col, seqname)` pair is two
  consecutive `tgargs` entries. The function calls
  `CStringGetTextDatum(args[i])` and feeds that to
  `nextval(regclass)`. So bad-quoting/non-existent sequences only
  fail at trigger fire time, not creation. [verified-by-code]
  `:101-102`
- **INV-2: Only zero, not "any default" value, is treated as
  "needs autoincrement".** Surprising for users used to MySQL's
  AUTO_INCREMENT (which fires only on NULL). The behaviour is
  documented in the SQL doc that ships with this trigger.
  [from-comment-implicit] **[ISSUE-doc-drift: only test is `!isnull
  && val != 0`; zero is treated as "fill me in" (nit)]**
- **INV-3: `nextval` returning 0 triggers a single retry**, then
  the retried value is used unconditionally even if it is also 0.
  Pathological case: a sequence at MAX with WRAP enabled could
  cycle through 0 twice; this would write 0 to the column. Could
  be a subtle integrity bug. [verified-by-code] `:106-110`
  **[ISSUE-correctness: only one retry on zero from sequence (nit)]**

## Potential issues

- `:112` `pfree(DatumGetTextPP(seqname))` frees the text datum
  allocated by `CStringGetTextDatum` — good practice in tutorial
  code. Real trigger functions are typically in short-lived
  contexts where this matters less. [verified-by-code]
- `:65` "even number gt 0" error message has lowercase mixed casing.
  Style not strictly compliant with PG message style (would normally
  capitalize first letter of errmsg). Tutorial code, so cosmetic.
  [inferred] **[ISSUE-style: errmsg capitalization in tutorial code
  (nit)]**
- `:39-47` Uses `elog(ERROR, "internal error")` for trigger-guard
  failures rather than `ereport(ERROR, errcode(...))`. The internal-
  error convention is intentional — these conditions indicate the
  trigger is misconfigured by a developer, not bad user input.
  [from-comment-style]

## Cross-references

<!-- issues:auto:begin -->
- [Issue register — `spi`](../../../issues/spi.md)
<!-- issues:auto:end -->
