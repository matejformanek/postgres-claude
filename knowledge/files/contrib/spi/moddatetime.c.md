# `contrib/spi/moddatetime.c`

- **Last verified commit:** `e18b0cb7344`
- **Lines:** 133
- **Source:** `source/contrib/spi/moddatetime.c`

Tutorial-example trigger function that sets a TIMESTAMP or TIMESTAMPTZ
column to the current time on UPDATE (only UPDATE, not INSERT — see
INV-1). The file header credits this as "95%+ based on autoinc.c"
which is visible in the structure. Like its siblings, it doesn't use
SPI for query execution. [verified-by-code + from-comment]

## API / entry points

- `moddatetime(PG_FUNCTION_ARGS)` `:32-133` — sole entry. BEFORE-ROW
  trigger, single argument: column name. [verified-by-code]

## The pattern (what this file teaches)

1. **INSERT is rejected** (`:60-62`): `elog(ERROR, "moddatetime:
   cannot process INSERT events")`. Interesting design choice
   restricting to UPDATE-only. [verified-by-code]
2. **`DirectFunctionCall3(timestamp_in, CStringGetDatum("now"), ...,
   Int32GetDatum(-1))`** invokes the type's input function with
   the string `"now"` — the canonical pattern for getting the
   current timestamp without binding to a particular
   `transaction_timestamp` / `statement_timestamp` /
   `clock_timestamp` semantic (the input function uses the C-level
   transaction time). `:105-114` [verified-by-code]
3. **TIMESTAMP vs TIMESTAMPTZ branching**: only these two are
   accepted; everything else errors. `:104-122` [verified-by-code]
4. **`heap_modify_tuple_by_cols`** for the column-write, identical
   pattern to `autoinc.c`. `:126-127` [verified-by-code]
5. **`newdt = (Datum) 0;  /* keep compiler quiet */`** after the
   error branch — `ereport(ERROR, ...)` is `pg_noreturn` but old
   compilers didn't know this, hence the dead assignment.
   `:121` [from-comment]

## Notable invariants / details

- **INV-1: INSERT is explicitly rejected** (vs `autoinc.c` which
  fires on both INSERT and UPDATE). The user is expected to set a
  DEFAULT on the column for INSERT-time population. The trigger
  handles only "modification" time. [verified-by-code] `:60-62`
- **INV-2: `"now"` semantics**: `timestamp_in("now", ...)` resolves
  to the transaction start time, not the statement time. So
  multiple updates within one transaction all get the same
  timestamp. This is correct for "row was modified in transaction
  T". [from-inferred + verified-by-code via core
  `timestamp.c::timestamp_in`]
  **[ISSUE-doc-drift: not user-documented as "transaction time, not
  clock time" (nit)]**
- **INV-3: Only TIMESTAMP and TIMESTAMPTZ are accepted.** Notably
  NOT DATE, TIME, INTERVAL. [verified-by-code]

## Potential issues

- `:13` Header comment says the author "do not really know what
  I am doing" — historical curio, harmless. [from-comment]
- `:106-114` Use of `DirectFunctionCall3(timestamp_in, ...,
  ObjectIdGetDatum(InvalidOid), Int32GetDatum(-1))` — the InvalidOid
  is the typmod typioparam (irrelevant for TIMESTAMP), the -1 is the
  typmod itself. Will silently produce a value without typmod
  truncation; if the column has e.g. `TIMESTAMP(0)`, the inserted
  value won't be rounded to seconds. The actual rounding happens at
  column-assign time in the executor, so this should be fine.
  [inferred]
  **[ISSUE-question: does typmod=−1 here interact with column TYPMOD
  on insert? (nit)]**
- `:50-58` Error-message prefix style: `"moddatetime: ..."` again
  diverges from `autoinc.c`'s `"autoinc (%s): "`. Per-file style
  consistency. [verified-by-code]
  **[ISSUE-style: prefix inconsistency across spi/ tutorials (nit)]**
