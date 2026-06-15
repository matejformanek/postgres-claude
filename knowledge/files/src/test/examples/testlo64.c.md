---
path: src/test/examples/testlo64.c
anchor_sha: e18b0cb7344
loc: 302
depth: read
---

# src/test/examples/testlo64.c

## Purpose

64-bit variant of `testlo.c`. Demonstrates the same large-objects flow
(create, open, read, write, seek, close, unlink) but using the 64-bit
offset entry points: `lo_lseek64`, `lo_tell64`, `lo_truncate64`. Needed
for LOs larger than 2 GB, where the 32-bit `int` offsets would
silently overflow. Header comment is otherwise identical to testlo.c.
`[from-comment]`

## Public symbols

Same names as `testlo.c` (`importFile`, `pickout`, `overwrite`,
`exportFile`, `main`) — but the random-access helpers use 64-bit
offsets internally. `[verified-by-code]`

## Internal landmarks

- Includes `<stdint.h>` (`:15`) for `int64_t` types — testlo.c uses
  plain `int`.
- `BUFSIZE` = 1024 (`:27`) — same chunk size as 32-bit variant.
- `lo_lseek64`, `lo_tell64`, `lo_truncate64` are the three calls that
  distinguish this file from `testlo.c`.
- File header gives `IDENTIFICATION src/test/examples/testlo64.c`
  (`:11`) and the full PG copyright block.

## Invariants & gotchas

- Server-side LO size is limited by `LOBLKSIZE * INT_MAX` of pages,
  not by client API. The 64-bit API is the only way to reach offsets
  beyond `INT32_MAX = 2 GB - 1`.
- Transaction-bounded LO handles, same as testlo.c.
- Mixing 32-bit and 64-bit calls on one LO is technically allowed but
  confusing — pick one.
- Shipped example, not a regression test.

## Cross-refs

- `knowledge/files/src/test/examples/testlo.c.md` — 32-bit variant.
- `knowledge/subsystems/large-objects.md` — backend-side LO storage.
- `doc/src/sgml/lobj.sgml` — the chapter this is quoted in.
