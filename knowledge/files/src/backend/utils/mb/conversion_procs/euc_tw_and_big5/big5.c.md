---
path: src/backend/utils/mb/conversion_procs/euc_tw_and_big5/big5.c
anchor_sha: e18b0cb7344
loc: 377
depth: read
---

# `big5.c` — BIG5 ↔ CNS 11643 plane mapping tables

## Purpose

Helper module (no `Datum` entry points of its own) for the
`euc_tw_and_big5` conversion proc. Provides static mapping tables and
lookup helpers between **BIG5 levels 1/2** and **CNS 11643-1992
planes 1/2**. The actual `Datum` functions live next door in
`euc_tw_and_big5.c`; this file is dedicated to the lossy BIG5↔CNS
range tables so the proc body stays manageable.

Built with `postgres_fe.h` rather than `postgres.h` so that the
mapping tables are reusable in frontend code (e.g. `pg_dump`).

## Public symbols

| Symbol | Line | Notes |
|---|---:|---|
| `codes_t` (struct typedef) | 17 | Pair `{code, peer}` of `unsigned short`. |
| `big5Level1ToCnsPlane1[25]` (static const) | 24 | BIG5 L1 → CNS Plane 1 ranges. |
| `cnsPlane1ToBig5Level1[26]` (static const) | 53 | Reverse map. |
| Additional `big5Level2ToCnsPlane2` / `cnsPlane2ToBig5Level2` tables | – | Same structure, plane 2. |
| `BIG5toCNS` (extern, exposed via `mb/pg_wchar.h` family) | – | Lookup helper consumed by `euc_tw_and_big5.c`. |
| `CNStoBIG5` (extern, exposed via `mb/pg_wchar.h` family) | – | Lookup helper consumed by `euc_tw_and_big5.c`. |

## Internal landmarks

- `#include "postgres_fe.h"` (line 13) — the **only** file in this
  directory that uses the frontend-safe entry point. This is the
  explicit signal that `big5.c` may also be linked into client tools
  rather than just the backend.
- Each `codes_t` table is a sparse range encoding: each row gives the
  *low* BIG5/CNS code in a contiguous range, with a sentinel
  `{0xXXXX, 0x0000}` row marking the *end* of a range. The
  lookup helper scans for the matching range and does the arithmetic
  diff against the row's `code` to derive the target.
- No `PG_FUNCTION_INFO_V1`, no `PG_MODULE_MAGIC` — `big5.c` is
  *not* an fmgr-loaded module on its own; it is statically linked
  into the `euc_tw_and_big5` shared library.

## Invariants & gotchas

- The two directions must stay symmetric. Sentinel rows
  (`{0xXXXX, 0x0000}`) terminate each range — silently omitting one
  produces a runtime read-past-end on the next range.
- BIG5 and CNS 11643 are **not in 1-to-1 correspondence**: this is
  why the transcoder is range-based instead of a single flat lookup
  table. Out-of-range codes return a sentinel and the caller (in
  `euc_tw_and_big5.c`) reports `untranslatable_character` or breaks
  out on `noError`.
- The credits (lines 1-7) note that the BIG5/CNS tables were lifted
  from `lv` (multilingual file viewer) by NARITA Tomio in 1999. The
  data is essentially frozen — Unicode normalisation drift on either
  side would require a coordinated update, but in practice neither
  BIG5 nor CNS 11643-1992 has moved.

## Cross-refs

- `knowledge/files/src/backend/utils/mb/conversion_procs/euc_tw_and_big5/euc_tw_and_big5.c.md`
  — the consumer of these tables (provides the `Datum` entry points).
- `knowledge/files/src/backend/utils/mb/conv.c.md` — shared error
  helpers reachable from the consumer.
- `source/src/include/mb/pg_wchar.h` — declarations exposed to other
  TUs; `PG_BIG5`, `PG_EUC_TW` enum values.

## Synthesized by
<!-- backlinks:auto -->
