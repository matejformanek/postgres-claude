# Eval 3 — with_skill (iter-2)

## Snippet 1

```c
if (lookup_failed) {
    ereport(ERROR,
            errmsg("Relation %s Does Not Exist.\n", name));
    goto cleanup;
}
```

Violations:

1. **Leading capital "R"** — rule 3: errmsg has no leading capital.
2. **Trailing period** — rule 3: no trailing period in errmsg.
3. **Trailing `\n`** — rule 3: no newlines in errmsg (also checklist).
4. **Identifier `%s` not quoted** — rule 5: identifiers must be quoted
   as `\"%s\"`.
5. **Missing `errcode()`** — rule 2: must always pass errcode. Default
   `ERRCODE_INTERNAL_ERROR` is wrong here; this should be
   `ERRCODE_UNDEFINED_TABLE`.
6. **`goto cleanup` after `ereport(ERROR, ...)`** — that's dead code.
   `ereport(ERROR)` longjmps and does not return. Checklist item:
   "No `goto cleanup` after `ereport(ERROR, ...)`."

Fix:

```c
ereport(ERROR,
        (errcode(ERRCODE_UNDEFINED_TABLE),
         errmsg("relation \"%s\" does not exist", name)));
```

## Snippet 2

```c
if (cache_miss) {
    ereport(ERROR,
            (errcode(ERRCODE_INTERNAL_ERROR),
             errmsg("cache lookup failed for relation " "%u", oid)));
}
```

Violations:

7. **Should be `elog`, not `ereport`** — rule 1: "elog for should-never-happen,
   ereport for user-visible". Cache lookup failure is the canonical
   `elog(ERROR, ...)` case. `lsyscache.c` is full of these.
8. **Adjacent string-literal concatenation** in the format string
   (`"cache lookup failed for relation " "%u"`) — rule 7: don't concatenate
   fragments, breaks gettext extraction.
9. (Stylistic, less load-bearing) Using `ERRCODE_INTERNAL_ERROR` explicitly
   is fine but redundant since `elog` defaults to it.

Fix:

```c
elog(ERROR, "cache lookup failed for relation %u", oid);
```

## Snippet 3

```c
if (bad_input) {
    ereport(ERROR,
            (errmsg("can't parse value: ERROR 22003 numeric overflow")));
}
```

Violations:

10. **`can't` contraction** — PG style is "cannot". (The message-style guide
    in the broader error-handling rules forbids contractions.)
11. **Severity ("ERROR") embedded in message text** — rule 6: don't put
    SQLSTATE or severity in the message; the logger handles them.
12. **SQLSTATE ("22003") embedded in message text** — same rule 6.
13. **Missing `errcode()`** — rule 2. The 22003 in the text suggests the
    author meant `ERRCODE_NUMERIC_VALUE_OUT_OF_RANGE` — should be a real
    `errcode()` call, not text.

Fix:

```c
ereport(ERROR,
        (errcode(ERRCODE_NUMERIC_VALUE_OUT_OF_RANGE),
         errmsg("value \"%s\" is out of range", input)));
```
