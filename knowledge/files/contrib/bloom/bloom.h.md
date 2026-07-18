# contrib/bloom/bloom.h

**Pin:** `4b0bf0788b066a4ca1d4f959566678e44ec93422`
**LOC:** 213
**Verification depth:** full read

## Role

Header for the `bloom` index AM contrib module — a lossy signature-based
index that hashes each indexed value into a fixed-length bit vector and
supports equality (and only equality) lookups via bit-pattern
intersection.  Useful for `WHERE a=? AND b=? AND c=?` over wide tables
where no single column is selective enough for a btree but the
intersection is.

## Public API

- `BloomPageOpaqueData` — per-page opaque (`maxoff`, `flags`,
  `bloom_page_id=0xFF83` magic for `pg_filedump`).
  [verified-by-code] `source/contrib/bloom/bloom.h:33-57`
- `BloomMetaPageData` — metapage struct: `magickNumber=0xDBAC0DED`,
  `nStart..nEnd` cursor into `notFullPage[]` (free-list of pages with
  room for more tuples), and the frozen-at-creation `BloomOptions`.
  [verified-by-code] `source/contrib/bloom/bloom.h:118-131`
- `BloomOptions` — per-index options: `bloomLength` (signature length in
  *words*, not bits; max 256 words = 4096 bits) and per-column `bitSize`
  (number of bits set per indexed value, default 2, max
  `MAX_BLOOM_LENGTH - 1`).
  [verified-by-code] `source/contrib/bloom/bloom.h:91-107`
- `BloomState` — runtime state for an open index: hash function infos,
  collations, options copy, precomputed `sizeOfBloomTuple`.
  [verified-by-code] `source/contrib/bloom/bloom.h:135-147`
- `BloomTuple` — `ItemPointerData heapPtr + BloomSignatureWord sign[]`.
  [verified-by-code] `source/contrib/bloom/bloom.h:157-163`
- AM interface declarations: `blinsert`, `blbeginscan`, `blgetbitmap`,
  `blrescan`, `blendscan`, `blbuild`, `blbuildempty`, `blbulkdelete`,
  `blvacuumcleanup`, `bloptions`, `blcostestimate`, plus signature-utility
  `signValue`, `BloomFormTuple`, `BloomPageAddItem`.
  [verified-by-code] `source/contrib/bloom/bloom.h:174-211`

## Invariants

- INV-1: `BLOOM_PAGE_ID` (0xFF83) is the last 2 bytes of every bloom
  page — a hard contract with pg_filedump.
  [verified-by-code] `source/contrib/bloom/bloom.h:49-58`
- INV-2: `DEFAULT_BLOOM_LENGTH = 5 * SIGNWORDBITS = 80 bits`,
  `MAX_BLOOM_LENGTH = 256 * SIGNWORDBITS = 4096 bits`,
  `DEFAULT_BLOOM_BITS = 2`, `MAX_BLOOM_BITS = MAX_BLOOM_LENGTH - 1`.
  These are hardcoded; the per-index reloption values are clamped by
  blutils' `add_int_reloption` calls.
  [verified-by-code] `source/contrib/bloom/bloom.h:89-98`
- INV-3: `BLOOM_NSTRATEGIES=1` — bloom supports exactly ONE operator
  strategy (equality, `BLOOM_EQUAL_STRATEGY=1`).
  [verified-by-code] `source/contrib/bloom/bloom.h:28-30`
- INV-4: `BLOOM_NPROC=2` support procedures: `BLOOM_HASH_PROC` (1) is
  required, `BLOOM_OPTIONS_PROC` (2) is optional.
  [verified-by-code] `source/contrib/bloom/bloom.h:23-26`
- INV-5: `BLOOM_METAPAGE_BLKNO=0` and `BLOOM_HEAD_BLKNO=1` — fixed
  on-disk layout; meta on block 0, data starts at block 1.
  [verified-by-code] `source/contrib/bloom/bloom.h:77-79`
- INV-6: `FreeBlockNumberArray` is sized so the entire metapage is full
  — `BLCKSZ - SizeOfPageHeaderData - opaque - (counters + opts)` worth
  of BlockNumbers.
  [verified-by-code] `source/contrib/bloom/bloom.h:110-115`

## Notable internals

- `BloomSignatureWord = uint16` (so `SIGNWORDBITS = 16`).
  [verified-by-code] `source/contrib/bloom/bloom.h:84-86`
- `BloomScanOpaqueData` holds the search signature computed by
  `signValue` over scan key arguments — the actual matching is
  `(itup->sign[i] & so->sign[i]) == so->sign[i]` in blscan.

## Trust-boundary / Phase-D surface

- **Per-index reloption `length` is operator-controlled** (max 4096
  bits). A tiny `length=1` would mean every value collides → reads
  return huge bitmap of false positives → DoS-ish but only the index
  itself becomes useless, the heap recheck still filters correctly. So
  not a correctness issue, just a self-inflicted slow-query foot-gun.
- **`signValue` uses a custom Park-Miller LCG in blutils.c**, NOT the
  PG `pg_prng` family, to keep on-disk format stable across PG random
  generator changes. (See blutils.c notes.)
- **No WAL-record-format custom RMGR** — bloom uses `generic_xlog.c`
  for all updates. So a corrupt bloom block detected by checksum gets
  the standard treatment; no bloom-specific recovery path.
- **Signature collidability**: signatures are designed to collide
  (that's the AM's nature). An attacker who can read AND choose
  what's indexed could craft values colliding with target values'
  signatures, but the heap recheck means this only inflates *false
  positive rate*, not data exposure. Not a security issue.

## Cross-refs

- A13 sibling GiST/signature modules: `pg_trgm`, `intarray`'s gist__int_ops.
- `source/src/backend/access/transam/generic_xlog.c` — WAL backend.
- Sibling: `blinsert.c`, `blutils.c`, `blscan.c`, `blvacuum.c`,
  `blvalidate.c`, `blcost.c`.

## Issues raised

None — header is descriptive.

## Synthesized by
<!-- backlinks:auto -->
- [subsystems/contrib-bloom.md](../../../subsystems/contrib-bloom.md)
