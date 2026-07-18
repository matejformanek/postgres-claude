---
path: src/port/strtof.c
anchor_sha: e18b0cb7344
loc: 89
depth: read
---

# src/port/strtof.c

## Purpose

`pg_strtof()` — wrapper around the platform `strtof()` that adds
proper over/underflow detection. Motivated by Cygwin's `strtof`, which
is literally `(float) strtod(...)` and therefore loses ERANGE for
values that overflow `float` but fit in `double`. Mingw apparently has
the same problem. `[from-comment]` `[verified-by-code]`

PG calls this from `float4in` (`src/backend/utils/adt/float.c`) so SQL
`REAL`/`float4` input handling reports `ERANGE` correctly even on
broken libc.

## Public symbols

| Symbol | Site | Notes |
|---|---|---|
| `float pg_strtof(const char *nptr, char **endptr)` | `strtof.c:30` | Sets `errno=ERANGE` on under/overflow; preserves caller's `errno` on success |

## Internal landmarks

The function has two layers of escalation:

1. **Trust libc** (`strtof.c:36-44`): call platform `strtof`, capture
   `errno`. If the platform reports an error, propagate it as-is.
2. **Trust-but-verify** (`strtof.c:45-55`): on "success", check that
   the result is either nothing-parsed, NaN, or a normal-magnitude
   finite value. If so, restore `caller_errno` and return — libc got
   it right.
3. **Re-parse via strtod** (`strtof.c:62-87`): subnormal, zero, or
   infinity needs a second opinion. Call `strtod` on the same input,
   then:
   - both values 0 of same sign, or both infinities of same sign →
     accept as legitimate zero/inf (`strtof.c:69-75`).
   - `strtod` gave a subnormal `float`-range value where `strtof`
     returned exactly 0 → return the cast of `strtod`'s result
     (`strtof.c:76-82`).
   - everything else → set `ERANGE` and return whatever `strtof` gave
     (`strtof.c:84-87`).

## Invariants & gotchas

- **`endptr` is set even on error** (`strtof.c:38-39`) — caller can
  always inspect parse position regardless of return.
- The "subnormal-but-nonzero" branch (`strtof.c:76`) explicitly
  re-casts `(float) dresult` and checks it's not 0 — this distinguishes
  "double has subnormal, cast to float underflows to 0 → ERANGE" from
  "double has subnormal, cast to float still has a subnormal float
  representation → return without error".
- Double-rounding is still a hazard: parsing via `strtod` then casting
  to `float` can give a different last-bit result than a hypothetical
  correct `strtof`. The wrapper *documents* this in its header
  (`strtof.c:21-24`) rather than fixing it — fixing would require a
  full IEEE-754 binary32 parser.
- `errno` discipline: caller's `errno` is captured at entry, cleared,
  and restored only on success — error paths leave `errno` set to the
  appropriate ERANGE/EINVAL.

## Cross-refs

- `knowledge/files/src/port/snprintf.c.md` — sibling "fix libc
  numeric formatting on broken platforms" file.
- `source/src/backend/utils/adt/float.c:float4in` — primary consumer
  (SQL `REAL` input).

## Synthesized by
<!-- backlinks:auto -->
- [subsystems/port.md](../../../subsystems/port.md)
