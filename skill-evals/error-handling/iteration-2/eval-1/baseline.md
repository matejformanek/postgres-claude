# Eval 1 — baseline (iter-2, no skill)

For each of the three failure modes:

## open() failed

```c
int fd = open(path, O_RDONLY);
if (fd < 0)
    ereport(ERROR,
            (errcode_for_file_access(),
             errmsg("could not open file \"%s\": %m", path)));
```

Use `errcode_for_file_access()` — it picks a SQLSTATE from errno. The `%m`
format specifier expands to `strerror(errno)`. Filename quoted with `\"%s\"`.

## fread() failed

```c
if (fread(buf, 1, n, fp) != n) {
    if (ferror(fp))
        ereport(ERROR,
                (errcode_for_file_access(),
                 errmsg("could not read file \"%s\": %m", path)));
    else
        ereport(ERROR,
                (errcode(ERRCODE_DATA_CORRUPTED),
                 errmsg("unexpected end of file \"%s\"", path)));
}
```

## Malformed line

```c
ereport(ERROR,
        (errcode(ERRCODE_SYNTAX_ERROR),
         errmsg("syntax error in file \"%s\" at line %d", path, lineno),
         errdetail("Expected a directive, got \"%s\".", token)));
```

errmsg style: lowercase start, no trailing period, no newline.
errdetail is a full sentence with a period.

## Do I need close(fd)?

`ereport(ERROR)` does a `longjmp` out of the function, so it never returns
— so technically a `close(fd)` after it would be dead code. But you still
have an fd leak: nothing in the surrounding scope will close it. The cleanest
fix is to put the `close` *before* the `ereport`, or to use a `PG_TRY` block.
I don't recall whether there's a wrapper that registers the fd with the
transaction; if there is, use it.

## Headers

`utils/elog.h` for `ereport`, `errcode`, `errmsg`. `utils/errcodes.h` for
the ERRCODE_* constants.
