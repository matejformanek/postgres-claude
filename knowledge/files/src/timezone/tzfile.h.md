---
path: src/timezone/tzfile.h
anchor_sha: 4b0bf0788b066a4ca1d4f959566678e44ec93422
loc: 110
depth: read
---

# src/timezone/tzfile.h

## Purpose

Describes the **on-disk TZif file format** (IANA / RFC 8536) and the hard limits
the parser enforces. Public-domain header carried near-verbatim from the IANA
tz distribution; it defines the `struct tzhead` wire layout and the `TZ_MAX_*`
size caps used to bound `struct state` in `pgtz.h`. `[from-comment]`
`[verified-by-code]`

## Public symbols

| Symbol | Site | Notes |
|---|---|---|
| `TZ_MAGIC "TZif"` | `tzfile.h:37` | File magic |
| `struct tzhead` | `tzfile.h:39` | 44-byte header: magic, version (`\0`/`2`/`3`), reserved, and six big-endian count fields |
| `TZ_MAX_TIMES 2000` | `tzfile.h:100` | Max transition times |
| `TZ_MAX_TYPES 256` | `tzfile.h:103` | Max local-time types (unsigned-char index limit) |
| `TZ_MAX_CHARS 50` | `tzfile.h:105` | Max abbreviation characters |
| `TZ_MAX_LEAPS 50` | `tzfile.h:108` | Max leap-second corrections |
| `TZDEFAULT "/etc/localtime"`, `TZDEFRULES "posixrules"` | `tzfile.h:27-28` | Default paths/rules |

## Invariants & gotchas

- **The `TZ_MAX_*` macros are the parser's DoS bound** — `tzset()`/`tzload()`
  refuse any file exceeding them (`tzfile.h:95-98`), so a malformed or hostile
  TZif file cannot drive unbounded allocation; `struct state` sizes its arrays
  to exactly these caps.
- The header documents the **version-2/3 dual layout**: version `2`+ appends a
  second `tzhead` + 64-bit transition data + a trailing POSIX-TZ string;
  version `3`+ relaxes the POSIX string's hour range to ±167 and allows
  all-year DST (`tzfile.h:78-93`). The parser must read the 64-bit block when
  present.
- Self-described as unstable: "This header is for use ONLY with the time
  conversion code… Do NOT copy it to any system include directory" (`:15-20`).
- `TZ_MAX_TYPES` must be ≥17 for `Europe/Samara` / `Europe/Vilnius`
  (`:102`) — a concrete reminder these caps track real-world zone complexity.

## Cross-refs

- `knowledge/files/src/timezone/pgtz.h.md` — `struct state` uses these bounds.
- `knowledge/files/src/timezone/pgtz.c.md` — `tzload`/`tzparse` callers.
