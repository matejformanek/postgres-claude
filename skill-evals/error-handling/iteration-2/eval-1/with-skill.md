# Eval 1 — with_skill (iter-2)

Three failure modes for a config-file reader in `src/backend/commands`.

## Preferred: don't use raw `open(2)`

Open with `OpenTransientFile()` instead — it registers the fd with the
transaction's ResourceOwner so it closes automatically on xact abort. That
removes one whole class of "do I need to close on error" worries.

```c
int fd = OpenTransientFile(path, O_RDONLY | PG_BINARY);
if (fd < 0)
    ereport(ERROR,
            (errcode_for_file_access(),
             errmsg("could not open file \"%s\": %m", path)));
```

Rules applied: `errcode_for_file_access()` consumes errno (skill rule 2);
`%m` splices `strerror(errno)` (rule 2 again — must NOT call `strerror(errno)`
manually with `%s`, errno may be clobbered, see rule 9); errmsg is lowercase,
no period, no newline (rule 3); identifier is quoted `\"%s\"` (rule 5).
Declared in `src/include/storage/fd.h:177`.

## fread() failure

```c
if (fread(buf, 1, len, fp) != len)
    ereport(ERROR,
            (errcode_for_file_access(),
             errmsg("could not read file \"%s\": %m", path)));
```

Same idiom — `errcode_for_file_access()` + `%m`. If you needed to do other
work between the failing read and the ereport, capture errno first
(`int save_errno = errno;`) — rule 9.

## Malformed line — user-triggerable parse error

```c
ereport(ERROR,
        (errcode(ERRCODE_CONFIG_FILE_ERROR),
         errmsg("syntax error in file \"%s\" at line %d",
                path, lineno),
         errdetail("Unrecognized directive \"%s\".", token),
         errhint("Valid directives are listed in the documentation.")));
```

- `errcode(ERRCODE_CONFIG_FILE_ERROR)` from `src/backend/utils/errcodes.txt`
  — a specific SQLSTATE, not the default `INTERNAL_ERROR` (rule 2).
- `errmsg` lowercase, no period, one phrase, identifier quoted (rules 3, 5).
- `errdetail` and `errhint` are full sentences with capital + period
  (rule 4). `errhint` is actionable.

## elevel

`ERROR` for all three. They abort the current transaction; the user can
retry with a fixed file. `FATAL` would be wrong (we don't need to kill
the backend). `PANIC` would be very wrong.

## Do I need close(fd) before reporting?

No — and you can't anyway, because `ereport(ERROR, ...)` does not return;
it longjmps to the nearest `PG_TRY` or to PostgresMain. The skill is
explicit: "Anything reached 'after' an ERROR in the source is dead code".
If you used `OpenTransientFile()`, the fd is auto-closed on xact abort by
the ResourceOwner. If you used raw `open(2)`, you'd need a `PG_TRY` to
close it — which is exactly why the skill recommends `OpenTransientFile()`.

## Files cited

- `src/include/storage/fd.h:177` — `OpenTransientFile`.
- `src/backend/utils/errcodes.txt` — SQLSTATE list.
- `src/include/utils/elog.h` — `ereport`, `errcode`, `errmsg`, etc.
