# Eval 1 — file open / read / parse error reports (with_skill)

Three failure modes, three different patterns.

## 1. `open(2)` failed — syscall, use `errcode_for_file_access()`

```c
fd = OpenTransientFile(path, O_RDONLY | PG_BINARY);
if (fd < 0)
    ereport(ERROR,
            (errcode_for_file_access(),
             errmsg("could not open file \"%s\" for reading: %m", path)));
```

Why:
- `errcode_for_file_access()` consumes the current `errno` and maps it to the
  right SQLSTATE (per SKILL.md rule #2 and `knowledge/idioms/error-handling.md`
  on errxxx() helpers). Don't write `errcode(ERRCODE_INTERNAL_ERROR)` here.
- `%m` is the canonical way to splice `strerror(errno)` into the message.
- `errmsg` starts lowercase, no trailing period, identifier quoted as `\"%s\"`
  (SKILL.md rules #3 and #5).
- `ereport`, not `elog` — a user can trigger this (bad path, permissions),
  so it needs a translated message and a real SQLSTATE
  (`knowledge/idioms/error-handling.md` "ereport vs elog").

## 2. `fread()` / `read()` short read or I/O error

```c
if (nread < 0)
    ereport(ERROR,
            (errcode_for_file_access(),
             errmsg("could not read file \"%s\": %m", path)));
else if (nread != expected)
    ereport(ERROR,
            (errcode(ERRCODE_DATA_CORRUPTED),
             errmsg("could not read file \"%s\": read %zd of %zu",
                    path, nread, expected)));
```

Same `errcode_for_file_access()` for true I/O errors. For short read with
errno=0, pick a more specific code (data corrupted / unexpected EOF). Still
lowercase, no period.

## 3. Malformed line — user-facing parse error

```c
ereport(ERROR,
        (errcode(ERRCODE_SYNTAX_ERROR),
         errmsg("syntax error in file \"%s\" at line %d", path, lineno),
         errdetail("Expected key=value, found \"%s\".", token),
         errhint("Comment out the line with '#' or remove it.")));
```

Why:
- Pick the most specific SQLSTATE from `src/backend/utils/errcodes.txt`
  (SKILL.md rule #2). `ERRCODE_SYNTAX_ERROR` (class 42) or
  `ERRCODE_CONFIG_FILE_ERROR` depending on context.
- `errmsg` — lowercase, no period (rule #3).
- `errdetail` and `errhint` — full sentences with capital and period
  (SKILL.md rule #4). `errhint` is actionable.
- Don't put "ERROR:" or "SQLSTATE 42601" in the text (rule #6); the logger
  prepends severity.

## Do I need to close(fd) before reporting?

**No, and you can't anyway.** Per SKILL.md "Critical: `ereport(ERROR)` does
not return":

> It longjmps to the nearest `PG_TRY` or to PostgresMain. **You do not write
> cleanup code after it.** Anything reached "after" an ERROR in the source is
> dead code from a runtime perspective. Don't `goto cleanup`; let transaction
> abort handle memory contexts, locks, buffer pins, etc.

For the fd specifically: use `OpenTransientFile()` (not raw `open`) —
it registers the fd with the transaction's resource owner, so xact abort
closes it. If you must use raw `open`, register it with a `PG_TRY`/`PG_FINALLY`,
but the idiomatic answer is OpenTransientFile.

Source anchor: `knowledge/idioms/error-handling.md` "What happens on ERROR —
cleanup flow" lists the abort sequence (ResourceOwner callbacks release
buffer pins, locks, fds, etc.).

## Checklist hits (SKILL.md §Checklist)

- [x] errcode set explicitly (file_access helper or specific code, never default)
- [x] errmsg lowercase, no period, string literal for gettext
- [x] errdetail/errhint full sentences
- [x] identifiers quoted `\"%s\"`
- [x] no goto cleanup after ereport(ERROR)
- [x] no newlines, no fragment concatenation
