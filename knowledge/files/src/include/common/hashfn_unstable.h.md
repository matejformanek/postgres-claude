# src/include/common/hashfn_unstable.h

## Purpose
**Unstable** (between-versions and potentially between-platforms) inline
hash functions. The header comment is explicit: "*The functions in this
file are not guaranteed to be stable between versions, and may differ by
hardware platform. Hence they must not be used in indexes or other
on-disk structures. See hashfn.h if you need stability.*"

Implements `fasthash` (Zilong Tan 2012, MIT licensed) with both a
standalone API (`fasthash32`/`fasthash64`) and an incremental "feed me
chunks" API around a `fasthash_state`.

## Role in PG
- **`simplehash.h`** — the local-memory open-addressing hash-table
  template used by `nodeAgg.c`, `nodeHashjoin.c`, `nodeRecursiveunion.c`,
  TID-bitmap, planner internals. Picks fasthash for keying.
- **In-memory-only catalog accelerators** that don't persist hashes.
- **`hash_string(s)`** convenience (`hashfn_unstable.h:411`) — the inlined
  C-string hasher used in some lookups that don't need cross-version
  stability.

## API
- `fasthash_state { uint64 accum, hash; }` (`hashfn_unstable.h:101`)
- `fasthash_init(*hs, seed)` (`hashfn_unstable.h:118`)
- `fasthash_mix(h, tweak)` (`hashfn_unstable.h:126`) — both the mixer
  and finalizer step
- `fasthash_combine(*hs)` (`hashfn_unstable.h:136`) — mix in `hs->accum`
- `fasthash_accum(*hs, k, len)` (`hashfn_unstable.h:144`) — up-to-8-byte
  chunk, endian-aware byte loads
- `fasthash_accum_cstring_unaligned(*hs, str)` (`hashfn_unstable.h:232`)
- `fasthash_accum_cstring_aligned(*hs, str)` (`hashfn_unstable.h:261`) —
  word-at-a-time with `haszero64` SWAR NUL detection; **annotated
  `pg_attribute_no_sanitize_address`** because the trailing 8-byte read
  past the string can include up to 7 bytes of post-NUL memory (safe
  because allocator alignment guarantees the page is valid).
- `fasthash_accum_cstring(*hs, str)` (`hashfn_unstable.h:297`) — dispatches
  to aligned or unaligned, asserting consistency in debug builds
- `fasthash_final64(*hs, tweak)` (`hashfn_unstable.h:333`) — finalize
- `fasthash_reduce32(h)` (`hashfn_unstable.h:344`) — Fermat-residue
  reduction `h - (h >> 32)`
- `fasthash_final32(*hs, tweak)` (`hashfn_unstable.h:356`)
- `fasthash64(k, len, seed)` (`hashfn_unstable.h:372`)
- `fasthash32(k, len, seed)` (`hashfn_unstable.h:399`)
- `hash_string(s)` (`hashfn_unstable.h:411`) — NUL-terminated string,
  faster than `fasthash32(s, strlen(s))` because it computes length
  during hashing
- `haszero64(v)` macro (`hashfn_unstable.h:225`) — SWAR NUL-byte detector
  from Stanford bithacks

## State / globals
None. All inline.

## Phase D notes
- **`pg_attribute_no_sanitize_address`** on `fasthash_accum_cstring_aligned`
  is load-bearing: the function deliberately reads up to 7 bytes past the
  end of the string. The comment at lines 254-258 justifies: "*Loading
  the word containing the NUL terminator cannot segfault since allocation
  boundaries are suitably aligned.*" — relies on the palloc/malloc
  alignment guarantee. **Anyone using fasthash on a non-allocator-backed
  string (e.g. mmap'd file region with strict bounds) MUST use the
  unaligned variant or ensure padding.** [from-comment]
- **Endianness branching** (`hashfn_unstable.h:154-185, 186-216`) is
  explicit — fasthash produces different output on BE vs LE for inputs
  of length 1-7 bytes. This is why the file is labeled "unstable" and
  must not be persisted.
- **Use of `fasthash` vs `hash_bytes`.** Reviewers must check that any
  patch persisting hash values (in a catalog, in shared state, in an
  index) does **not** use fasthash. The compile-time separation
  (separate header) is the main safeguard, but no static check.
- **DoS surface.** Same hash-flooding caveat as `hash_bytes` — but
  simplehash users typically operate on small in-memory sets where
  collisions are bounded by `work_mem` spill.

## Cross-refs
- Stable companion: `knowledge/files/src/include/common/hashfn.h.md`.
- simplehash template: `src/include/lib/simplehash.h` callers.
- A11/A13/A14 hash-collision cluster context:
  `knowledge/issues/pgcrypto.md`, `knowledge/issues/contrib/citext.md`.

<!-- issues:auto:begin -->
- [Issue register — `include-common`](../../../../issues/include-common.md)
<!-- issues:auto:end -->

## Issues
1. `[ISSUE-audit-gap: simplehash users mustn't persist their hash
   values — enforced only by naming and the "unstable" header. A
   future caller could violate this by serializing a simplehash
   entry's hashcode (maybe)]` —
   `source/src/include/common/hashfn_unstable.h:1-13`.
2. `[ISSUE-correctness: fasthash_accum_cstring_aligned reads up to 7
   bytes past NUL. Safe on palloc'd strings (allocator alignment),
   unsafe on stack-allocated short strings or string slices not on
   8-byte boundaries. PointerIsAligned gate at line 309 is the only
   check (maybe)]` — `source/src/include/common/hashfn_unstable.h:259-291`.
3. `[ISSUE-defense-in-depth: timings can leak data layout via
   branch prediction (length-dependent switch in fasthash_accum), but
   data hashed is typically not security-sensitive (nit)]` —
   `source/src/include/common/hashfn_unstable.h:144-219`.
4. `[ISSUE-documentation: "unstable" guarantee is only in the file's
   leading comment; no per-function reminder — easy to copy a
   prototype into a context where it gets persisted (nit)]` —
   `source/src/include/common/hashfn_unstable.h:1-13`.
