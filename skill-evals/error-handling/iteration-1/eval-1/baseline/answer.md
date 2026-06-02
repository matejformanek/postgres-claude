# Eval 1 — file open / read / parse error reports (baseline)

Three failure modes:

## 1. open() fails

```c
fd = open(path, O_RDONLY);
if (fd < 0)
    ereport(ERROR,
            errmsg("could not open file %s: %m", path));
```

I'd use `%m` to get the errno string. I'm not sure if there's a helper to
auto-set the errcode for file errors — I think you'd just use
`ERRCODE_IO_ERROR` or similar. I don't remember the exact name.

## 2. fread() fails

Similar pattern with ereport(ERROR) and `%m`. Some SQLSTATE for I/O.

## 3. Malformed parse line

```c
ereport(ERROR,
        errmsg("malformed input at line %d", lineno));
```

Add an errhint maybe pointing to docs.

## Style notes I think I remember

- errmsg should be lowercase, no period
- Identifiers in double quotes
- Use ereport not elog for user-facing

## Do I need to close(fd)?

I think on ERROR Postgres unwinds via longjmp and the transaction abort
cleans up. If `open()` was tracked by something I'd be fine — but raw open()
might leak the fd. Safest is to close it before ereport, but if ereport(ERROR)
doesn't return I can't close after. So put the close in a PG_TRY/PG_FINALLY,
or use whatever the PG wrapper for transient fds is — I think `OpenTransientFile`
exists but I'm not certain about its cleanup guarantees.
