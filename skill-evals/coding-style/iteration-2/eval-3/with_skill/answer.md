# Eval 3 — with skill

Lots wrong. Walking through it:

```c
ereport(ERROR,
        errcode(ERRCODE_INVALID_PARAMETER_VALUE),
        errmsg("Unable to open file %s: open() failed.", path));
pfree(buf);
```

## Message text

1. **"Unable"** — banned. PG style says use `"could not"` for recoverable
   conditions (this one) or `"cannot"` for permanent ones. Never
   `"unable"`, `"illegal"`, `"bad"`, `"unknown"`.

2. **Capital `"U"` in `"Unable"`** — `errmsg` is the primary message, it
   must start lower-case. (Only `errdetail`/`errhint` start with a
   capital, because those are full sentences. `errmsg` is a fragment.)

3. **Trailing period** — `errmsg` takes no terminal punctuation. Only
   `errdetail` / `errhint` end in `.`.

4. **`%s` for the filename is unquoted** — user-supplied identifiers,
   file names, and GUC names must be wrapped in `"%s"` so the quoted
   value stands out in the output: `"%s"`.

5. **`open() failed` leaks an implementation detail** — don't name the
   syscall in user-facing messages. The right pattern is `%m`, which
   expands to `strerror(errno)`. So instead of `: open() failed`, write
   `: %m` and let the formatter produce e.g. `: No such file or directory`.

## SQLSTATE

`ERRCODE_INVALID_PARAMETER_VALUE` is wrong for a file-open failure.
Use `errcode_for_file_access()` — it picks the right `ERRCODE_*` from
`errno` so you don't have to guess (it'll resolve to things like
`ERRCODE_UNDEFINED_FILE`, `ERRCODE_DISK_FULL`, etc. depending on what
actually failed).

## Code after the ereport

`ereport(ERROR, …)` **does not return** — it `longjmp`s out to the
nearest error handler. So:

- `pfree(buf);` after it is **unreachable**. Delete it. (Some compilers
  will warn about it.)
- It's also **unnecessary**: when `ereport(ERROR)` fires,
  `AbortTransaction()` runs and releases the per-query memory context
  (so any `palloc`'d buffers, including `buf`, are reclaimed
  automatically), plus locks, buffers, and open file descriptors. You
  don't need to clean up by hand on the error path.

## Fixed version

```c
ereport(ERROR,
        errcode_for_file_access(),
        errmsg("could not open file \"%s\": %m", path));
```
