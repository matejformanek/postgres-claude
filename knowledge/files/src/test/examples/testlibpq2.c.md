---
path: src/test/examples/testlibpq2.c
anchor_sha: e18b0cb7344
loc: 150
depth: read
---

# src/test/examples/testlibpq2.c

## Purpose

Demonstrates the libpq **asynchronous notification interface** —
`LISTEN` / `NOTIFY` plus `PQnotifies()` polling. The program issues
`LISTEN TBL2`, then sits in a `select()` loop on `PQsocket(conn)`,
calling `PQconsumeInput` when the socket is readable and draining any
pending `PGnotify` records. Exits after receiving four notifications.
The header comment shows the matching SQL setup (TBL1 with a rule that
fires NOTIFY on insert) so a user can reproduce the demo.
`[from-comment]`

## Public symbols

| Symbol | Site | Notes |
|---|---|---|
| `static void exit_nicely(PGconn *conn)` | `testlibpq2.c:41-46` | `PQfinish` + `exit(1)` |
| `int main(int argc, char **argv)` | `testlibpq2.c:48-149` | LISTEN loop |

## Internal landmarks

- `LISTEN TBL2` issued via `PQexec` after the standard search-path
  hardening.
- The loop uses `select()` on `PQsocket(conn)` with no timeout — blocks
  until the kernel delivers data on the connection socket.
- On wakeup: `PQconsumeInput(conn)` → `PQnotifies(conn)` loop until
  `NULL`. Each notification frees with `PQfreemem(notify)`.
- Exits after `nnotifies >= 4` (`:140` region).

## Invariants & gotchas

- Shipped example, not a regression test.
- The `PQsocket(conn)` fd is only safe to `select()` on after
  `PQconsumeInput` confirms the connection is in pollable state;
  the loop here checks `PQstatus` implicitly via `PQexec` results
  first.
- `PQnotifies` returns notifications already buffered locally; it
  does NOT itself read from the socket. You MUST call
  `PQconsumeInput` first.
- On Windows the file includes `<windows.h>` (`:28-30`) so that
  `<sys/select.h>` substitutes are pulled in indirectly.

## Cross-refs

- `knowledge/subsystems/notify.md` — backend-side NOTIFY/LISTEN
  implementation in `async.c`.
- `knowledge/files/src/test/examples/testlibpq.c.md` — minimal client.
