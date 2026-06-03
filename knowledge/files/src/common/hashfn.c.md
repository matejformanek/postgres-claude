# src/common/hashfn.c

## Purpose
Bob-Jenkins 32-bit lookup3-style hash and friends. The workhorses behind
PG's general-purpose hashing: `hash_bytes`, `hash_bytes_extended` (with
64-bit seed → 64-bit output), `hash_bytes_uint32`, plus dynahash key
helpers `string_hash`, `tag_hash`, `uint32_hash`.

## Role in PG
- **Hash indexes / hash partitioning / hash joins / hash aggregate.**
  These all eventually invoke a per-type hash function that calls into
  `hash_bytes` or `hash_bytes_extended`. Hash output **is persisted** in
  hash indexes and **must remain stable across major versions** — that's
  why this file's algorithm is frozen and `hashfn_unstable.h` exists as
  the separate, optimization-friendly alternative.
- **dynahash.** The default hash table impl uses `string_hash`/`tag_hash`/
  `uint32_hash` (`hashfn.c:659-692`) as the hash callback. dynahash is
  used for shared-memory tables (LWLock partition tables, lock tables,
  buffer-tag → buffer-ID lookup, catcache, syscache, predicate-lock
  hashtable, …).
- Note: parser keyword lookup uses **kwlookup.c** (perfect hash), not
  this file. So keyword-table flooding is not a concern for `hashfn.c`.

## Key functions
- `hash_bytes(k, keylen)` (`hashfn.c:146`) — Jenkins lookup3 mix.
  Returns uint32. Aligned-fast path + unaligned + endian variants.
  **Must never elog(ERROR)** (`hashfn.c:138-139`) — ResourceOwner cleanup
  paths rely on this being failure-free.
- `hash_bytes_extended(k, keylen, seed)` (`hashfn.c:372`) — same core mix
  but folds an optional 64-bit seed in by treating it as a zero-padded
  12-byte prefix (`hashfn.c:385-394`), and uses both `b` and `c` final
  state to produce a uint64. Used by extended hash funcs like
  `hashtext_extended`, `partition_hash_*`, hash-partition pruning.
- `hash_bytes_uint32(k)` (`hashfn.c:610`) — single-uint32 input
  optimization, skips the `mix()` and runs only `final()`. Backbone of
  catcache/syscache hash on OID keys.
- `hash_bytes_uint32_extended(k, seed)` (`hashfn.c:631`).
- `string_hash(key, keysize)` (`hashfn.c:660`) — dynahash NUL-string hash;
  truncates at `keysize-1`.
- `tag_hash(key, keysize)` (`hashfn.c:677`) — fixed-size memcmp-style key.
- `uint32_hash(key, keysize)` (`hashfn.c:688`) — single-uint32 dyn key.
  `oid_hash` is `#define`d to `uint32_hash` in hashfn.h ("Remove me
  eventually").

## State / globals
None. Pure functions. The "seed" of 0x9e3779b9 + len + 3923095
(`hashfn.c:155`) is a fixed compile-time constant — the same on every
postmaster invocation, every PG instance. **This is the key on-disk
stability guarantee** for hash indexes but also the key hash-flooding
caveat (see Phase D).

## Phase D notes
- **No key randomization.** `hash_bytes` has zero per-process randomization.
  The output of `hash_bytes("hello", 5)` is identical on every PG instance
  ever built. Stability is mandatory for hash indexes (the index stores
  hash values on disk) and hash partitioning (the catalog records which
  partition serves which hash bucket).
- **Hash-flooding attack surface:**
  - **Hash indexes** — adversary-controlled input could be crafted to
    collide on `hash_text`/`hash_numeric`/etc., causing degenerate O(n²)
    behavior on inserts. Mitigated in practice by hash-index implementation
    using buckets with overflow pages (degrades gracefully, doesn't fault).
  - **Hash join / hash agg** — same concern, but executor uses spill-to-disk
    when buckets blow up; degrades to performance issue not correctness.
  - **dynahash on adversary-influenced keys** — the LWLock partition table
    keys (`{relfilenode, blockno}` for buffer mapping) and predicate lock
    table keys are derived from physical layout, not user input — not
    floodable. Catcache/syscache keys are OIDs allocated by PG — not
    user-controlled.
  - **`pg_class` name lookups via syscache** use `hash_any(name)` on the
    relation name. An attacker who can create many relations with names
    chosen to collide on Jenkins lookup3 could in principle slow down
    `RELNAMENSP` lookups. Requires CREATE privilege in a schema; unlikely
    practical attack but theoretically possible. [inferred]
- **Aligned vs unaligned paths** are functionally identical — both
  compute the same hash value (`hashfn.c:160` aligned vs `hashfn.c:258`
  unaligned; both end at `final(a,b,c)` with same intermediate sums for
  same input bytes). The split exists purely for speed: aligned path
  uses word loads, unaligned reconstructs uint32s byte by byte. Endian
  branches keep the byte-order interpretation identical across CPUs.
  [verified-by-code]
- **Must-not-elog contract.** `hash_bytes` is called from
  `ResourceOwnerForget*` cleanup paths; an `elog(ERROR)` from inside
  cleanup-during-error would cascade. This is a stronger invariant than
  most leaf functions. [from-comment: hashfn.c:138]

## Potential issues
- [ISSUE-dos: hash_bytes has no per-process keying. Adversary-influenced
  input to hash join / hash agg / hash partitioning could in principle
  trigger collisions for DoS. Mitigated by executor spill-to-disk and by
  hash-index overflow pages, but worth a note for the threat model.
  (maybe)]
- [ISSUE-undocumented-invariant: "must never throw elog(ERROR)" applies
  to hash_bytes per comment at hashfn.c:138, but is not asserted by any
  static-analysis hook. A future caller could pass a path that allocates
  — currently the impl doesn't, but the invariant could regress silently.
  (maybe)]
- [ISSUE-stale-todo: `#define oid_hash uint32_hash /* Remove me eventually */`
  (hashfn.h:59) — predates extension API stability discussion, still here.
  Not a bug, just a confirmed-stale TODO. (low)]
