# Eval 3 — baseline (iter-2, no skill)

## Snippet 1

- "Relation" starts with a capital — PG style says errmsg starts lowercase.
- Trailing period — errmsg has no trailing period.
- Trailing `\n` — errmsg never ends in newline; the logger adds one.
- `%s` for an identifier should be quoted as `\"%s\"`.
- No `errcode()`. Should be `ERRCODE_UNDEFINED_TABLE`.
- `goto cleanup` after `ereport(ERROR, ...)` is dead code because ERROR
  longjmps out of the function. Drop it.

Fixed:
```c
ereport(ERROR,
        (errcode(ERRCODE_UNDEFINED_TABLE),
         errmsg("relation \"%s\" does not exist", name)));
```

## Snippet 2

- "cache lookup failed for relation %u" is the canonical "this should never
  happen" message. The idiomatic form is `elog(ERROR, ...)`, not
  `ereport(ERROR, errcode(ERRCODE_INTERNAL_ERROR), ...)`. lsyscache.c uses
  elog throughout.
- Adjacent string concatenation `"cache lookup failed for relation " "%u"`
  breaks gettext message extraction — the translator sees fragments.

Fixed:
```c
elog(ERROR, "cache lookup failed for relation %u", oid);
```

## Snippet 3

- "can't" contraction violates the PG style guide — use "cannot".
- Embedding "ERROR" (severity) in the message text — the logger emits
  severity, don't duplicate.
- Embedding "22003" (SQLSTATE) in the message text — same: use
  `errcode(ERRCODE_NUMERIC_VALUE_OUT_OF_RANGE)`, don't paste the code.
- No `errcode()`.

Fixed:
```c
ereport(ERROR,
        (errcode(ERRCODE_NUMERIC_VALUE_OUT_OF_RANGE),
         errmsg("value \"%s\" is out of range", input)));
```
