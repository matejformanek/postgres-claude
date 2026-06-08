---
path: src/timezone/private.h
anchor_sha: 4b0bf0788b066a4ca1d4f959566678e44ec93422
loc: 155
depth: read
---

# src/timezone/private.h

## Purpose

The private header shared by PostgreSQL's vendored IANA tzcode files
(`localtime.c`, `strftime.c`, `zic.c`). It is a near-verbatim import of the
upstream tzdb `private.h`, trimmed of the IANA `HAVE_FOO` autoconf cruft
("in PG we want pretty much all of that to be done by PG's configure script",
`private.h:33-35`). It supplies the calendar/time arithmetic constants
(`SECSPERDAY`, `MONSPERYEAR`, `EPOCH_YEAR`, …), the type-introspection macros
(`TYPE_BIT`, `TYPE_SIGNED`, `MAXVAL`/`MINVAL`), and the `pg_time_t` extreme
values (`TIME_T_MIN`/`TIME_T_MAX`) the loader/converter rely on. It is
explicitly **not** a public include — "Do NOT copy it to any system include
directory" (`private.h:15-21`). `[verified-by-code]`

## Public symbols

Header-only; no functions. The load-bearing macros:

| Macro | Site | Role |
|---|---|---|
| `TYPE_BIT(type)` | `private.h:52` | `sizeof(type) * CHAR_BIT` |
| `TYPE_SIGNED(type)` | `private.h:53` | true if the type is signed (`((type)-1) < 0`) |
| `TWOS_COMPLEMENT(t)` | `private.h:54` | true if `t` uses two's-complement |
| `MAXVAL(t, b)` / `MINVAL(t, b)` | `private.h:61,64` | extreme values of integer type `t` using only the bottom `b` bits |
| `TIME_T_MIN` / `TIME_T_MAX` | `private.h:68-69` | extreme `pg_time_t` values (drive the discard-out-of-range logic in `tzloadbody`) |
| `is_digit(c)` | `private.h:45` | `ctype`-free digit test, safe for `c < 0` or `c > UCHAR_MAX` |
| `isleap(y)` / `isleap_sum(a,b)` | `private.h:129,143` | Gregorian leap-year tests; `isleap_sum` avoids addition overflow by reducing mod 400 first |
| `SECSPERREPEAT` / `SECSPERREPEAT_BITS` | `private.h:151,153` | 400-year repeat cycle in seconds; underpins `differ_by_repeat` extrapolation in `localtime.c` |

## Internal landmarks

- `INT_STRLEN_MAXIMUM(type)` (`private.h:77`) — max decimal digits a type can
  print, derived from `log10(2) ≈ 302/1000`; `strftime.c`'s `_conv` sizes its
  stack buffer with this.
- `isleap_sum` (`private.h:143`) — the comment (`:131-141`) documents *why* it
  reduces mod 400 before adding: to dodge signed-overflow UB on the year sum
  while preserving `isleap(a+b) == isleap(a%400 + b%400)`.
- `ENOTSUP`/`EOVERFLOW` fallbacks to `EINVAL` (`private.h:37-42`) for platforms
  lacking them.

## Invariants & gotchas

- **Frontend + backend both build this.** `localtime.c`/`strftime.c` include it
  after `c.h`/`postgres.h`; `zic.c` after `postgres_fe.h`. It must therefore
  stay free of backend-only dependencies — it pulls only `<limits.h>`,
  `<sys/wait.h>`, `<unistd.h>`, and `pgtime.h`.
- `TIME_T_MIN`/`TIME_T_MAX` are macros over `pg_time_t` (a signed 64-bit
  `int64`), not the platform `time_t`. PG decouples its zone arithmetic from the
  host `time_t` width on purpose; don't substitute `<time.h>` limits.
- These are vendored upstream macros — keep edits minimal and matched to the
  IANA source so future tzdb merges stay clean (the PG-local delta is only the
  removed `HAVE_*` block + the `IDENTIFICATION` tag).

## Cross-refs

- `knowledge/files/src/timezone/localtime.c.md` — primary consumer of the limit
  macros (range-discard in `tzloadbody`, `differ_by_repeat`).
- `knowledge/files/src/timezone/strftime.c.md` — uses `INT_STRLEN_MAXIMUM`,
  the `MONSPERYEAR`/`DAYSPERWEEK` constants.
- `knowledge/files/src/timezone/tzfile.h.md` — the on-disk TZif layout constants
  (`TZ_MAX_TIMES`, `TZ_MAX_TYPES`, …) used alongside these arithmetic ones.
