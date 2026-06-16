# `src/backend/lib/hyperloglog.c`

- **Last verified commit:** `e18b0cb7344`
- **Lines:** ~255
- **Source:** `source/src/backend/lib/hyperloglog.c`

HyperLogLog cardinality estimator, based on Hideaki Ohno's C++
implementation (MIT-licensed, retained in the header). The PG comment
explicitly notes the Heule/Nunkesser/Hall ("HLL in Practice") improvements
are NOT implemented. Used by tuplesort's abbreviated-key stats and a
handful of stats consumers. [verified-by-code §hyperloglog.c:1-23]

Storage is dense, not sparse, despite the file header comment claiming
"A sparse representation … is used, with fixed space overhead" — the
actual `hashesArr` is a flat `nRegisters`-byte array allocated in
`initHyperLogLog`. The comment appears to be inherited from a
different planned variant. [verified-by-code §hyperloglog.c:74, 81 vs. header §13-16]

## API / entry points

- `initHyperLogLog(state, bwidth)` — `bwidth` ∈ [4,16]; allocates
  `2^bwidth + 1` bytes of register storage in current memory context.
  [verified-by-code §hyperloglog.c:65]
- `initHyperLogLogError(state, error)` — picks the smallest `bwidth`
  whose theoretical error `1.04 / sqrt(2^bwidth)` is below the
  requested rate; error range is ~25% (bwidth=4) to ~0.4% (bwidth=16).
  [verified-by-code §hyperloglog.c:127]
- `addHyperLogLog(state, hash)` — caller pre-hashes; the algorithm
  needs uniform bit distribution. [from-comment §hyperloglog.c:160-164]
- `estimateHyperLogLog(state)` — returns the corrected raw E with
  small-range correction (`<= 5/2 * m`) and large-range correction
  (`> 2^32 / 30`) applied. [verified-by-code §hyperloglog.c:185-220]
- `freeHyperLogLog(state)` — frees the hashes array but NOT the
  state struct (caller may have stack-allocated it). [from-comment §hyperloglog.c:144-148]

## Notable invariants / details

- `alpha` correction factor is hard-coded for `m = 16, 32, 64`, with
  the formula `0.7213 / (1 + 1.079/m)` for larger m. [verified-by-code §hyperloglog.c:88-102]
- `rho` returns `b + 1` when `x == 0` (the "all zeros" case), and
  clamps the leading-one position to b. [verified-by-code §hyperloglog.c:241-254]
- The register slot stores `Max(count, existing)` — monotonic, hence
  insertion order doesn't matter and the structure is mergeable in
  principle (but no merge function is provided here).
  [verified-by-code §hyperloglog.c:179]

## Potential issues

- **File-line `hyperloglog.c:14`.** Header claims sparse representation
  with fixed overhead — code is dense (one byte per register).
  [ISSUE-doc-drift: comment "sparse representation … is used" is wrong (nit)]
- **File-line `hyperloglog.c:7-12`.** Comment notes that Heule et al.
  optimisations (bias correction, sparse mode, 64-bit hashing) were
  considered but not done; that's been true since 2014. No tracker
  link. [ISSUE-stale-todo: deferred HLL-in-Practice improvements (nit)]

## Cross-references

<!-- issues:auto:begin -->
- [Issue register — `lib`](../../../../issues/lib.md)
<!-- issues:auto:end -->
