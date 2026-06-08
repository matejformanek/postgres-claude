# 2026-06-07 — cloud/pg-file-backfiller: src/timezone sweep (completes the dir)

## What I did
- Popped the 4 remaining `[pending]` `src/timezone` queue entries and wrote
  per-file docs against anchor `4b0bf0788b0`:
  - `private.h` (read) — vendored IANA private header; calendar/limit/leap macros.
  - `strftime.c` (read) — bundled C-locale `strftime`; `pg_strftime`.
  - `localtime.c` (deep) — the runtime TZif loader + `pg_time_t→pg_tm` converter.
  - `zic.c` (read) — build-time zone compiler (frontend tool).
- `src/timezone` now **7/7 (100%)** (the first three landed 2026-06-06).
- Created `knowledge/issues/timezone.md` (4 open, all `nit`) + README index row.
- Appended 4 rows to `files-examined.md` (1781→1785), marked queue block
  `[done:timezone-2026-06-07]`, updated `coverage-gaps.md`.
- Refilled the queue (depth<5 rule) with the **`src/backend/libpq`** block
  (17 .c files, 0 docs) ordered data-leak-first: auth/crypt/scram/hba/be-secure
  then wire-protocol plumbing. File list pulled from the GitHub tree API at
  anchor (sizes recorded).

## What I learned
- `localtime.c::tzloadbody` (`:265-371`) is the **real TZif security boundary**:
  it hard-validates every header count against the `TZ_MAX_*` ceilings, rejects
  short reads, non-monotonic/duplicate transitions, and out-of-range indices,
  returning `EINVAL` not a crash. A hand-crafted TZif placed in the zone dir
  bypasses `zic` entirely, so the consumer-side checks — not `zic`'s
  producer-side `namecheck` — are what matter. (Documented as the producer/
  consumer trust split.)
- `pg_localtime`/`pg_gmtime` return a pointer to a single file-static
  `struct pg_tm tm` (`localtime.c:104`) — non-reentrant; the contract lives only
  in an in-file comment, not at the `pgtime.h` prototypes.
- `tzload`/`gmtsub` use raw `malloc`/`free` **on purpose** because the file links
  into frontend tools (`#include "c.h"`), a trap for backend hackers tidying to
  `palloc`.
- `pg_strftime`'s only untrusted-input path is `%Z` (copies `t->tm_zone`, which
  comes from the zone file / POSIX TZ string); bounded by `_add`'s `ptlim` guard
  and the overrun-returns-empty contract (`:121-132`).
- `pg_tz_acceptable` (`:2006`) rejects leap-second-aware zones by checking that
  GMT-midnight 2000-01-01 has `tm_sec == 0`.

## What I'm unsure about
- The queue-listed LOC for `localtime.c` (1600) and `zic.c` (3000) were low;
  actual are 2023 and 4022. The libpq refill LOC are byte-size-derived
  estimates — correct them on read.
- src/timezone has no synthesis subsystem doc; the per-file docs + issue
  register stand alone. Probably fine (vendored code), but a 1-paragraph
  `subsystems/` stub cross-linking the five files might help navigation.

## Pointers left for next time
- Next cloud run pops the `src/backend/libpq` block (queued). Load the
  subsystem-relevant skill per path — auth/hba/crypt → `error-handling` +
  consider a security lens; be-secure-openssl → TLS. High Phase-D value.
- This completes the easy mechanical dirs (fe_utils, timezone, port-core);
  remaining cloud gaps skew higher-judgement (libpq, src/interfaces, contrib).
