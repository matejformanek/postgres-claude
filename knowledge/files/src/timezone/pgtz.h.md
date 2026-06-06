---
path: src/timezone/pgtz.h
anchor_sha: 4b0bf0788b066a4ca1d4f959566678e44ec93422
loc: 81
depth: read
---

# src/timezone/pgtz.h

## Purpose

Private header of the bundled timezone library — the struct definitions that
`pgtz.c`, `localtime.c`, and `strftime.c` share but that callers outside the tz
library do **not** see (the public API is `pgtime.h`). It defines the in-memory
representation of a parsed TZif zone: `struct state` (the whole zone), `struct
ttinfo` (one time-type / offset), `struct lsinfo` (leap-second correction), and
`struct pg_tz` (canonical name + state). `[verified-by-code]`

## Public symbols

| Symbol | Site | Notes |
|---|---|---|
| `struct ttinfo` | `pgtz.h:26` | One local-time type: `tt_utoff`, `tt_isdst`, abbreviation index, std/UT flags |
| `struct lsinfo` | `pgtz.h:35` | Leap-second transition + correction |
| `struct state` | `pgtz.h:41` | Full parsed zone: transition table (`ats`/`types`), `ttis[]`, abbreviation `chars[]`, `lsis[]`, `defaulttype` |
| `struct pg_tz` | `pgtz.h:65` | `TZname[TZ_STRLEN_MAX+1]` (canonical case) + embedded `struct state` |
| `pg_open_tzfile` (extern) | `pgtz.h:74` | Implemented in `pgtz.c` |
| `tzload` / `tzparse` (extern) | `pgtz.h:77,79` | Implemented in vendored `localtime.c` |

## Invariants & gotchas

- **Header split is deliberate:** "this file contains only definitions that are
  private to the timezone library. Public definitions are in pgtime.h"
  (`pgtz.h:6-7`). Backend code that just wants a `pg_tz *` includes `pgtime.h`;
  only the tz internals include this.
- `struct state` is a **fixed-size** struct — its arrays are bounded by the
  `TZ_MAX_*` limits from `tzfile.h` (`ats[TZ_MAX_TIMES]`, etc.), so a `pg_tz`
  has a large but constant footprint regardless of zone complexity. This is why
  the loaded-zone cache in `pgtz.c` stores zones by value.
- `defaulttype` is normally 0 for modern tzdb; nonzero only for pre-2018e data
  (`pgtz.h:56-61`).

## Cross-refs

- `knowledge/files/src/timezone/pgtz.c.md` — the integration layer using these.
- `knowledge/files/src/timezone/tzfile.h.md` — the `TZ_MAX_*` bounds.
