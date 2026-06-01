# subtrans.h

- **Source path:** `source/src/include/access/subtrans.h`
- **Lines:** 24
- **Last verified commit:** `ef6a95c7c64`
- **Companion files:** `subtrans.c`.

## Purpose

Tiny header exposing the eight pg_subtrans entry points.

## Top-of-file comment (verbatim)

```
subtrans.h

PostgreSQL subtransaction-log manager
```
[verified-by-code] `subtrans.h:1-4`.

## Public surface

- `SubTransSetParent(xid, parent)` — `subtrans.h:14` [verified-by-code]
- `SubTransGetParent(xid)` — `subtrans.h:15` [verified-by-code]
- `SubTransGetTopmostTransaction(xid)` — `subtrans.h:16`
  [verified-by-code]
- `BootStrapSUBTRANS`, `StartupSUBTRANS(oldestActiveXID)`,
  `CheckPointSUBTRANS`, `ExtendSUBTRANS(newestXact)`,
  `TruncateSUBTRANS(oldestXact)` — `subtrans.h:18-22`
  [verified-by-code]

## Key invariants

(See `subtrans.c.md`.) No WAL; not crash-persistent.

## Confidence tag tally

- `[verified-by-code]`: 5
