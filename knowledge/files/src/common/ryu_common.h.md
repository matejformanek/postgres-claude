# src/common/ryu_common.h

## Purpose
Shared inline helpers for Ryu's d2s and f2s implementations — log/power
approximations, NaN/Inf string emission, float↔bits puns. Compile-time
included by both `d2s.c` and `f2s.c`.

## Role in PG
Internal to the Ryu port. Not exposed via `shortest_dec.h` (the public
API).

## Key inlines
- `STRICTLY_SHORTEST` (`ryu_common.h:46`) — `#define`d to **0** in PG.
  Upstream Ryu uses 1. The PG comment at lines 38-45 explains: emitting
  the exact midpoint between two floats relies on the reader honoring
  round-to-even, which is the common failure mode across other languages'
  parsers. PG opts to slightly extend output to disambiguate.
  **This is a deliberate PG divergence and a key data-integrity invariant.**
- `pow5bits(e)` (`ryu_common.h:54`) — `ceil(log2(5^e))` approximation
  using a 32-bit multiplication; asserted valid for e ∈ [0, 3528].
- `log10Pow2(e)` (`ryu_common.h:70`) — `floor(log10(2^e))`; valid for
  e ∈ [0, 1650].
- `log10Pow5(e)` (`ryu_common.h:83`) — `floor(log10(5^e))`; valid for
  e ∈ [0, 2620].
- `copy_special_str(result, sign, exponent, mantissa)` (`ryu_common.h:95`)
  — emit "NaN", "Infinity", "-Infinity", "0", or "-0" depending on the
  IEEE special-value flags. Returns byte count.
- `float_to_bits(float)` / `double_to_bits(double)` — `memcpy`-based
  type punning (strict-aliasing safe).

## State / globals
None.

## Phase D notes
- The `STRICTLY_SHORTEST 0` choice is the file's only behavioral knob and
  the only real "trust boundary" — flipping it would change wire output
  for some floats and break version-mixing pg_dump roundtrip.
- `pow5bits`/`log10Pow2`/`log10Pow5` assertions guard against future
  refactors that might call them with out-of-range exponents — the
  approximations break silently outside their tested range.

## Potential issues
None new beyond what's covered in d2s/f2s/d2s_intrinsics notes.
