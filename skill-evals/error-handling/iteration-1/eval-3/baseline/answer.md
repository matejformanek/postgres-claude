# Eval 3 — code review of three broken ereport calls (baseline)

## Snippet 1

Problems I can spot:
- `errmsg` should be lowercase, no trailing period — "Relation ... Does Not Exist." breaks both.
- Identifier `name` should be in double quotes: `\"%s\"`.
- Newline `\n` shouldn't be in errmsg.
- No `errcode()` — should pick something specific, maybe `ERRCODE_UNDEFINED_TABLE`.
- `goto cleanup` after ereport(ERROR) is unreachable because ereport(ERROR) longjmps out.

Fixed:
```c
ereport(ERROR,
        errcode(ERRCODE_UNDEFINED_TABLE),
        errmsg("relation \"%s\" does not exist", name));
```

## Snippet 2

- For "cache lookup failed" the convention is `elog(ERROR, ...)` since this
  is a should-not-happen internal error, not a user-facing one.
- The string concatenation `"cache lookup failed for relation " "%u"` is odd
  and probably breaks gettext extraction.

Fixed:
```c
elog(ERROR, "cache lookup failed for relation %u", oid);
```

## Snippet 3

- "can't" is a contraction — PG style uses "cannot".
- "ERROR 22003" in the message text duplicates the SQLSTATE and severity
  that the logger handles separately.
- No errcode() set — should be `ERRCODE_NUMERIC_VALUE_OUT_OF_RANGE`.
- The message smashes multiple ideas together; could split into errmsg +
  errdetail.

Fixed:
```c
ereport(ERROR,
        errcode(ERRCODE_NUMERIC_VALUE_OUT_OF_RANGE),
        errmsg("numeric value out of range"),
        errdetail("Could not parse \"%s\".", input));
```
