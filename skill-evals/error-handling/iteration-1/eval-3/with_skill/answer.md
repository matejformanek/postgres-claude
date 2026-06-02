# Eval 3 — code review of three broken ereport calls (with_skill)

## Snippet 1

```c
ereport(ERROR,
        errmsg("Relation %s Does Not Exist.\n", name));
goto cleanup;
```

Violations:

1. **Missing `errcode()`** — SKILL.md rule #2: "Always pass an `errcode()`
   in `ereport`. Default is `ERRCODE_INTERNAL_ERROR`, which is rarely what
   you want." For "does not exist" use `ERRCODE_UNDEFINED_TABLE`.
2. **Capitalised first word** — SKILL.md rule #3: "no leading capital".
3. **Trailing period** — same rule: "no trailing period".
4. **Newline in errmsg** — checklist item "No newlines in `errmsg`".
5. **Unquoted identifier** — SKILL.md rule #5: "Quote identifiers as `\"%s\"`."
6. **`goto cleanup` after `ereport(ERROR)`** — SKILL.md "Critical: `ereport(ERROR)`
   does not return ... Don't `goto cleanup`; let transaction abort handle
   memory contexts, locks, buffer pins, etc." That goto is dead code.

Fixed:
```c
ereport(ERROR,
        (errcode(ERRCODE_UNDEFINED_TABLE),
         errmsg("relation \"%s\" does not exist", name)));
```

## Snippet 2

```c
ereport(ERROR,
        (errcode(ERRCODE_INTERNAL_ERROR),
         errmsg("cache lookup failed for relation " "%u", oid)));
```

Violations:

1. **Should be `elog`, not `ereport`** — SKILL.md rule #1 and the checklist:
   `elog(ERROR, "cache lookup failed for relation %u", oid)` is the canonical
   internal-error idiom; the skill explicitly lists this exact string as the
   model. `ereport` with `ERRCODE_INTERNAL_ERROR` + a non-translated message
   is the wrong shape for "should never happen".
2. **String-fragment concatenation in the format string** —
   SKILL.md rule #7: "Don't concatenate fragments into the format string —
   breaks gettext. Build via printf args." Even though this particular
   message should be untranslated (internal), concatenated literals break
   the extractor when scanning, and it's just wrong style.
3. **(Minor)** if kept as `ereport`, should be `errmsg_internal` not `errmsg`
   for not-translated developer messages (SKILL.md rule #8). But the real
   fix is to switch to `elog`, which already uses `errmsg_internal` under
   the hood.

Fixed:
```c
elog(ERROR, "cache lookup failed for relation %u", oid);
```

## Snippet 3

```c
ereport(ERROR,
        (errmsg("can't parse value: ERROR 22003 numeric overflow")));
```

Violations:

1. **Missing `errcode()`** — SKILL.md rule #2.
2. **"can't" — contraction** — `knowledge/idioms/error-handling.md` style
   section: "Don't use contractions (\"can't\" → \"cannot\") in user-visible
   messages."
3. **SQLSTATE embedded in message text** — SKILL.md rule #6: "Don't put
   SQLSTATE or severity in the message text — `errcode()` and the logger
   handle them." The "ERROR 22003" both repeats severity and embeds the
   SQLSTATE.
4. **Severity word "ERROR" in message** — same rule #6.
5. **Multiple concepts crammed into one errmsg** — should split: primary
   `errmsg("value out of range")` plus `errdetail("Numeric overflow parsing
   \"%s\".", input)` per SKILL.md rule #4 (errdetail = full sentence).
6. **Colon-joined fragments** — close to rule #7; the proper structure
   is errmsg + errdetail, not glued into one string.

Fixed:
```c
ereport(ERROR,
        (errcode(ERRCODE_NUMERIC_VALUE_OUT_OF_RANGE),
         errmsg("value out of range: \"%s\"", input),
         errdetail("Numeric overflow.")));
```
(The errcode `22003` matches `ERRCODE_NUMERIC_VALUE_OUT_OF_RANGE` from
`src/backend/utils/errcodes.txt`.)
