# hstore_gist.c

## One-line summary

GiST opclass (`gist_hstore_ops`) for hstore: builds a signature-tree
(bloom-filter-style bitset of CRC32 hashes of every key and non-null
value), with a configurable `siglen` opclass option (default 16 bytes =
128 bits), and implements compress/union/penalty/picksplit/same/consistent
for Contains, Exists, ExistsAny, ExistsAll.

Source pin: `4b0bf0788b0`.

## Public API / entry points

- `ghstore_compress(GISTENTRY*) -> GISTENTRY*` — leaf compression
  (`hstore_gist.c:147-206`) [verified-by-code].
- `ghstore_decompress(GISTENTRY*) -> GISTENTRY*` — no-op since ghstore
  isn't toastable (`hstore_gist.c:208-216`) [verified-by-code,
  from-comment].
- `ghstore_union(GistEntryVector*, *size) -> GISTTYPE*` — OR-merge of
  child signatures (`hstore_gist.c:309-334`) [verified-by-code].
- `ghstore_same(GISTTYPE*, GISTTYPE*, *bool)` — byte-identical signature
  comparison (`hstore_gist.c:218-250`) [verified-by-code].
- `ghstore_penalty(orig, new, *float)` — Hamming distance between
  signatures (`hstore_gist.c:336-348`) [verified-by-code].
- `ghstore_picksplit(entryvec, GIST_SPLITVEC*)` — Guttman/quadratic
  picksplit (`hstore_gist.c:365-505`) [verified-by-code].
- `ghstore_consistent(GISTENTRY*, query, strategy, subtype, *recheck) -> bool` — bitmap-membership check; ALWAYS sets `recheck = true`
  (`hstore_gist.c:508-612`) [verified-by-code].
- `ghstore_options(local_relopts*)` — registers the `siglen` opclass
  reloption (`hstore_gist.c:614-626`) [verified-by-code].
- `ghstore_in` / `ghstore_out` — both ereport `ERRCODE_FEATURE_NOT_SUPPORTED`
  (the internal signature type has no text representation)
  (`hstore_gist.c:97-115`) [verified-by-code].

## Key invariants

- `GISTTYPE { vl_len_; int32 flag; char data[FLEX]; }` — varlena header,
  one flag word, then `siglen` bytes of signature bits
  (`hstore_gist.c:48-53`) [verified-by-code].
- `flag & ALLISTRUE` (`= 0x04`) ⇒ the signature is conceptually
  all-1s (saturated bloom filter); the `data[]` buffer is omitted in
  this case (`hstore_gist.c:55-60`) [verified-by-code]. This is the
  standard GiST "matches everything" shortcut.
- `SIGLEN_DEFAULT = sizeof(int32) * 4 = 16` (128 bits)
  (`hstore_gist.c:23`) [verified-by-code].
- `SIGLEN_MAX = GISTMaxIndexKeySize` — the per-index-key page-fit limit
  (`hstore_gist.c:24`) [verified-by-code]. So siglen is operator-class-
  configurable from 1 byte up to whatever fits on a GiST internal page
  (typically a few KB).
- Hash function: `pg_crc32` of the key/value text via `crc32_sz`
  (`hstore_gist.c:80-90`) [verified-by-code]; bit index =
  `crc32 % (siglen * 8)`.
- `ghstore_compress` hashes BOTH the key and the value
  (`hstore_gist.c:163-176`) [verified-by-code]. Non-null values
  contribute; null values do not (the value is omitted, NOT replaced by a
  sentinel hash).
- Consistent always `*recheck = true` (`hstore_gist.c:521-522`)
  [verified-by-code]. Comment: "All cases served by this function are
  inexact" [from-comment].
- ISALLTRUE shortcuts in consistent: any inner node with ALLISTRUE
  unconditionally returns true ⇒ children must be examined
  (`hstore_gist.c:524-525`).

## Notable internals — signature-tree design

### Hash collision math

A 128-bit signature with `n` distinct hashes inserted has false-positive
rate ≈ `1 - (1 - 1/128)^n`. For a typical hstore with 10 K+V pairs (20
hashed items) and the default siglen=16:
- ~14% probability that any specific random query bit hashes to a set
  bit by collision.

That's high for selective indexes. The Phase D angle is that the
`siglen` opclass option is the user's only mitigation. Default of 16
bytes is aggressive — see `ghstore_compress:151` `GET_SIGLEN()` for the
reading and `ghstore_options:619-624` for the registration.

### Penalty function

`hemdist` = pure Hamming distance between bit signatures
(`hstore_gist.c:266-294`) [verified-by-code]. If one side is ALLISTRUE,
distance to the other = `siglen*8 - popcount(other)`. Standard signature-
tree penalty.

### Picksplit (`hstore_gist.c:365-505`) [verified-by-code]

Classical Guttman quadratic:
1. Find seed pair with maximum hemdist (O(N^2) over `maxoff` ≈ page
   capacity, ~few hundred).
2. Sort remaining entries by `|hemdist(L) - hemdist(R)|` (most decisive
   first).
3. Assign each to the closer side, with `WISH_F` tie-breaker that
   discourages extreme imbalance: `WISH_F(a, b, c) = -((a-b)^3) * c`
   (`hstore_gist.c:77`).
4. ALLISTRUE saturation: if either receiver is ALLISTRUE, the merge is a
   no-op (the side stays at all-1s); otherwise OR the bits.

### Union (`hstore_gist.c:309-334`) [verified-by-code]

OR all child signatures. Any ALLISTRUE child saturates the result and
short-circuits with `result->flag |= ALLISTRUE`. Note the early break
(`hstore_gist.c:325-328`) — the remaining children are not processed
once ALLISTRUE is reached, but their bits are already represented.

## Trust boundary / Phase D surface

### GiST signature collisions (PROMPT-SPECIFIC)

Per task prompt: signature-tree false positives ARE the design and are
intentional (recheck=true catches them). But for query-result-trust
audits: a query `WHERE hstore_col ? 'admin'` with a 128-bit signature
has a non-trivial chance of matching index pages with NO 'admin' key —
the recheck filter catches them at heap fetch time, so the final result
is correct. The audit-relevant point: an index scan that returns "page
matches" doesn't mean "row matches"; the AM must call back to the table.
`[ISSUE-defense-in-depth: default siglen=16 gives high false-positive
rate; document that this is intentional and recheck enforces correctness
(nit, by design)]`.

### `siglen` opclass option range

`add_local_int_reloption(relopts, "siglen", ..., SIGLEN_DEFAULT, 1,
SIGLEN_MAX, ...)` (`hstore_gist.c:619-624`) [verified-by-code]. Lower
bound is **1 byte = 8 bits**, which gives a comically bad signature with
~100% false positive rate even for tiny hstores. There's no warning at
CREATE INDEX time. `[ISSUE-api-shape: siglen lower bound is 1 byte (8
bits) which is operationally useless; should probably warn or refuse on
very low siglen (nit)]`.

### Memory bounds in compress

`ghstore_compress` palloc's exactly `CALCGTSIZE(flag, siglen)`
(`hstore_gist.c:121-122`). siglen is bounded by GISTMaxIndexKeySize at
opclass-creation time, so no DoS via siglen.

### Inner-node ALLISTRUE compression detection

`hstore_gist.c:184-203`: if an inner node's signature happens to be
all-bits-set, replace it with the ALLISTRUE flag form. This is invoked
on every compress call for non-leaf entries — meaning a query that ends
up with an inner node that's saturated bits gets the cheap ALLISTRUE
optimization. The detection scans `siglen` bytes looking for any non-0xff
(`hstore_gist.c:190-194`).

### `ghstore_in` / `ghstore_out` deliberately error out

These exist purely to make `ghstore` a valid type for the catalog, but
forbid SQL-level text I/O (`hstore_gist.c:97-115`) [verified-by-code,
from-comment]. So an attacker cannot directly feed a malformed ghstore
into the database. The only way to construct a ghstore is via the
compress callback inside the GiST AM. Good defense-in-depth.

### CRC32 is NOT cryptographic

`crc32_sz` is the legacy traditional CRC-32 (`INIT_TRADITIONAL_CRC32`,
`hstore_gist.c:85-87`) [verified-by-code]. An attacker who controls the
hstore content CAN compute collisions with any target key/value at will
— so an attacker can intentionally pollute index pages to make queries
slow (many false positives needing recheck). This is a DoS vector, not
a confidentiality issue. `[ISSUE-security: CRC32 hashing in
ghstore_compress is collision-trivial; an attacker who controls inserted
hstore keys/values can force pessimal index behavior by colliding into
hot signature bits (maybe)]`.

### No bounds re-validation in consistent

`ghstore_consistent` trusts that `entry->key` is a valid GISTTYPE
allocated by the AM — read directly via `PG_GETARG_POINTER(0)`. The
query (`PG_GETARG_HSTORE_P(1)` for Contains, `PG_GETARG_TEXT_PP(1)` for
Exists, `PG_GETARG_ARRAYTYPE_P(1)` for the array forms) is fully
validated by its respective input function. No issue here.

### Picksplit signed/unsigned in CRC% modulo

`#define HASHVAL(val, siglen) (((unsigned int)(val)) % SIGLENBIT(siglen))`
(`hstore_gist.c:45`) — explicitly casts to unsigned, so no signed-modulo
UB. Good. `[verified-by-code]`.

## Cross-references

- `access/gist.h`, `access/gist_private.h` — GiST AM internals.
- `utils/pg_crc.h` — `INIT_TRADITIONAL_CRC32` etc.
- `common/int.h` — `pg_cmp_s32` used in picksplit qsort comparator.
- `hstore_gin.c.md` — sibling exact-key GIN opclass for comparison.
- A12 contrib security bundle — pg_trgm has a similar
  signature-tree-with-recheck shape via trgm_gist.

<!-- issues:auto:begin -->
- [Issue register — `hstore`](../../../issues/hstore.md)
<!-- issues:auto:end -->

## Issues spotted

- `[ISSUE-defense-in-depth: default siglen=16 (128 bits) gives high
  false-positive rate; document better that recheck enforces correctness
  (nit, by design)]`
- `[ISSUE-api-shape: siglen lower bound 1 byte (8 bits) is operationally
  useless; no warning at CREATE INDEX time (nit)]`
- `[ISSUE-security: CRC32 hashing in ghstore_compress is collision-trivial;
  attacker-controlled hstore keys can pollute signature bits to degrade
  query performance (maybe)]`
- `[ISSUE-documentation: ghstore_in/out's ERRCODE_FEATURE_NOT_SUPPORTED
  is the right defense, but the comment doesn't explain WHY a non-textual
  internal type still needs in/out functions (it's a catalog requirement)
  (nit)]`
- `[ISSUE-api-shape: ALLISTRUE flag's bit value 0x04 (not 0x01 or 0x02)
  is an unstated PG-historical artifact — likely once shared with other
  flag bits (nit)]`
