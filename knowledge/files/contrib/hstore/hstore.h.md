# hstore.h

## One-line summary

Public header for the `hstore` extension: defines the `HStore` varlena layout,
the packed `HEntry` key/value descriptor (one per key, one per value), the
accessor macros that derive offsets and lengths by subtraction from the
previous entry, and the small public C API (`hstoreUpgrade`,
`hstoreUniquePairs`, `hstorePairs`, `hstoreCheckKeyLen`, `hstoreCheckValLen`,
`hstoreFindKey`, `hstoreArrayToPairs`).

Source pin: `4b0bf0788b0`.

## Public API / entry points

- `typedef struct { uint32 entry; } HEntry;` — packed descriptor, 4 bytes
  (`source/contrib/hstore/hstore.h:18-21`) [verified-by-code].
- `HENTRY_ISFIRST = 0x80000000`, `HENTRY_ISNULL = 0x40000000`,
  `HENTRY_POSMASK = 0x3FFFFFFF` — top-2 flag bits, 30-bit end-position
  (`hstore.h:23-25`) [verified-by-code].
- `HSE_OFF(he_)` / `HSE_LEN(he_)` — accessor macros that walk back to
  `(&he)[-1]` for the previous entry's end-pos; relies on caller passing an
  entry inside the array (`hstore.h:27-34`) [verified-by-code].
- `HSTORE_MAX_KEY_LEN = HSTORE_MAX_VALUE_LEN = 0x3FFFFFFF` — derived from
  `HENTRY_POSMASK` (`hstore.h:41-42`) [verified-by-code].
- `struct HStore { int32 vl_len_; uint32 size_; };` — 8-byte header, followed
  by `count*2` `HEntry`s and the string buffer (`hstore.h:44-49`)
  [verified-by-code].
- `HS_FLAG_NEWVERSION = 0x80000000`, `HS_COUNT() = size_ & 0x0FFFFFFF`,
  `HS_SETCOUNT()` sets count AND forces `HS_FLAG_NEWVERSION` bit
  (`hstore.h:59-62`) [verified-by-code]. The new-version flag lives in
  `size_`, NOT in the varlena header.
- `CALCDATASIZE(x, lenstr) = (x)*2*sizeof(HEntry) + sizeof(HStore) + lenstr`
  — total varlena size (`hstore.h:71-72`) [verified-by-code].
- `ARRPTR(x)` / `STRPTR(x)` — derive entry array and string buffer base from
  HStore* (`hstore.h:75-76`) [verified-by-code].
- `HSTORE_KEY` / `HSTORE_VAL` / `HSTORE_KEYLEN` / `HSTORE_VALLEN` /
  `HSTORE_VALISNULL` — per-pair accessors keyed by index `i_`
  (`hstore.h:79-83`) [verified-by-code].
- `HS_COPYITEM(dent_,dbuf_,dptr_,sptr_,klen_,vlen_,vnull_)` — copy already
  laid-out key+value bytes plus two new HEntry descriptors
  (`hstore.h:99-106`) [verified-by-code]. Multiple-evaluation hazard noted in
  comment.
- `HS_ADDITEM(dent_,dbuf_,dptr_,pair_)` — append from a `Pairs` struct
  (`hstore.h:112-126`) [verified-by-code].
- `HS_FINALIZE(hsp_,count_,buf_,ptr_)` — sets ISFIRST flag on entry 0,
  potentially `memmove`s the string region (if the actual count differs
  from the originally-set count), updates `SET_VARSIZE`
  (`hstore.h:129-140`) [verified-by-code].
- `HS_FIXSIZE(hsp_,count_)` — corrects varlena length without touching the
  string region (`hstore.h:143-147`) [verified-by-code].
- `DatumGetHStoreP(d) hstoreUpgrade(d)` — every code path that consumes an
  HStore Datum goes through `hstoreUpgrade()` which detoasts and (rarely)
  re-encodes from the pre-PG-8.4 on-disk format (`hstore.h:150-154`)
  [verified-by-code].
- `typedef struct { char *key; char *val; size_t keylen, vallen; bool isnull, needfree; } Pairs;` — "decompressed" representation used during input/output and merges (`hstore.h:161-169`) [verified-by-code].
- Strategy numbers: `Contains=7`, `Exists=9`, `ExistsAny=10`, `ExistsAll=11`,
  `OldContains=13` (`hstore.h:180-184`) [verified-by-code].
- `HSTORE_POLLUTE` namespace-aliasing macro: by default redefines the
  pre-namespace-cleanup names (e.g. `fetchval`, `exists`, `delete`) as
  forwarders to the new names "for the benefit of people restoring old
  dumps" (`hstore.h:188-203`) [verified-by-code, from-comment].

## Key invariants

- **On-disk new-version layout** (`hstore.h:44-83`) [verified-by-code]:
  `vl_len_ (4) | size_ (4) | HEntry[2*count] (8*count) | string buffer
  (lenstr)`. Total = `CALCDATASIZE(count, lenstr)`.
- **HEntry packing**: top bit `ISFIRST` is set only on the first HEntry
  (i.e. the first key's entry); top-2 = `ISNULL` is meaningful only on the
  value-side HEntries; bottom 30 bits = cumulative end-position into the
  string buffer (NOT length; length = `endpos[i] - endpos[i-1]`)
  (`hstore.h:11-34`) [verified-by-code, from-comment].
- **Count limit**: the format reserves the top 4 bits of `size_`, so the
  hard count cap is `2^28`, but `MaxAllocSize` keeps the practical limit at
  about `INT_MAX / 24` (one HEntry pair = 8 bytes + minimum-realistic
  payload) (`hstore.h:51-58`) [verified-by-code, from-comment]. The comment
  explicitly notes "we don't explicitly check the format-imposed limit"
  because MaxAllocSize gets there first.
- **Keys are sorted**: by `(keylen ASC, key ASC)` lexicographic; this is the
  invariant validated by `hstoreValidNewFormat` and assumed by every merge
  (`hstore_op.c`'s `concat`, `delete_array`, `delete_hstore`) and by
  `hstoreFindKey`'s binary search (`hstore_op.c:35-70`) [verified-by-code].
- **Key uniqueness**: enforced by `hstoreUniquePairs` (qsort + dedup) before
  every `hstorePairs` call (`hstore_io.c:359-405`) [verified-by-code].
- **Byteorder**: format treats `HEntry.entry` as a single host-byteorder
  uint32 carrying bitfield + endpos. The pq protocol exchanges textual
  key/value strings (NOT the packed entries), so on-wire byteorder is OK;
  the on-disk hstore is endian-dependent (like all PG varlena types). The
  pre-8.4 format's `HOldEntry { uint16 keylen; uint16 vallen; uint32 pos:31, valisnull:1; }` had genuine endian + bitfield-layout
  variance — see `hstore_compat.c.md`.
- **`HS_FLAG_NEWVERSION` MUST be set** on any HStore value before it
  exits the I/O layer; `HS_SETCOUNT` forces this. The disambiguator
  between new- and old-format hstores is whether this bit is set on the
  first entry's `size_` field, with extensive fallback validation in
  `hstoreUpgrade` (`hstore_compat.c`).

## Notable internals

- `HS_FINALIZE` may `memmove` the string region (`hstore.h:137`) — if the
  initial allocation overestimated the count (e.g. concat where dup keys
  shrink the output), the entry array is shorter than reserved and the
  string data has to slide left to match. This is the reason
  `hstore_concat` etc. can allocate a `count1+count2`-sized buffer and
  trust `HS_FINALIZE` to repack.
- `HSE_OFF((arr_)[2*(i_)])` for `i_ == 0` returns 0 via the `HSE_ISFIRST`
  short circuit, which is why the per-entry-pos value is stored as a
  cumulative END pos, not a start pos (`hstore.h:27-34`).
- `HS_COPYITEM` and `HS_ADDITEM` are the ONLY supported writers that
  manipulate HEntry bits directly outside of `hstore_compat.c`'s in-place
  upgrade (`hstore.h:85-90` comment).
- `Pairs.needfree` is a hint to `hstoreUniquePairs`'s dedup code on which
  duplicates can be pfree'd; comparePairs explicitly returns the
  needfree-true pair LATER so the dedup loop can pfree it
  (`hstore_io.c:329-350`).

## Trust boundary / Phase D surface

- **`HENTRY_POSMASK = 0x3FFFFFFF`** (`hstore.h:25`) [verified-by-code]: any
  on-disk HEntry endpos is silently masked to 30 bits. Combined with
  varlena's 1 GB limit (`MaxAllocSize`), this is fine for in-memory but
  means a forged HEntry with garbage top-2 bits won't trigger an obvious
  signature mismatch — only the `hstoreValidNewFormat` keylen/vsize check
  will. `[ISSUE-defense-in-depth: HEntry mask hides garbage in top-2 bits
  on any forged hstore; only secondary validation catches it (maybe)]`.
- **`HSTORE_MAX_KEY_LEN = HSTORE_MAX_VALUE_LEN = 0x3FFFFFFF`** (1 GiB) is
  the format-imposed cap (`hstore.h:41-42`) [verified-by-code]; the actual
  hot-path checks live in `hstore_io.c`'s `hstoreCheckKeyLen` /
  `hstoreCheckValLen`. Note that varlena's 1 GB limit clamps it lower in
  practice — but a maliciously-crafted in-memory HStore could carry an
  HEntry claiming a 1 GiB key inside a 100-byte allocation. The `valid_new`
  loop's `vsize > VARSIZE(hs)` check (`hstore_compat.c:139-141`) catches
  this for upgraded values, but the validated invariant is only re-checked
  on `hstoreUpgrade` — i.e., on every Datum-receive — not on every macro
  access. `[ISSUE-defense-in-depth: HEntry endpos trusted by accessor
  macros, so a forged Datum that bypassed hstoreUpgrade (e.g. via a future
  cast or in-memory construction path) would read OOB (maybe)]`.
- **`HS_COPYITEM` / `HS_ADDITEM` macros do raw `memcpy`** of `klen + vlen`
  bytes from a caller-supplied src pointer with no internal length check
  (`hstore.h:99-126`); callers (`hstore_op.c`, `hstore_subs.c`) must
  pre-check via `hstoreCheckKeyLen`/`hstoreCheckValLen`. Subscripting
  assignment does check (`hstore_subs.c:165,177`), but merge functions
  (`hstore_concat`, `hstore_delete_array`) take their lens from already-
  validated HStore values without re-checking. `[ISSUE-audit-gap:
  HS_COPYITEM has no internal length cap; correctness depends on every
  caller pre-validating (verified for the SQL-callable paths but worth
  documenting)]`.
- **Pre-PG-8.4 compat path** (`hstore.h:88-89` comment): "Exception: the
  in-place upgrade in hstore_compat.c messes with entries directly." This
  is one of two known forgery surfaces for a malicious pg_dump; see
  `hstore_compat.c.md` for the trust analysis.

## Cross-references

- `utils/adt/jsonb.c` (A7) — jsonb_recv was the canonical "decoder-DoS"
  finding; compare to `hstore_recv` in `hstore_io.c`.
- `utils/adt/varlena.c` — base varlena machinery.
- A11 pgcrypto, A12 contrib security-themed bundle — similar "user-supplied
  binary buffer trusts internal length tags" pattern across contrib.
- GIN/GiST internals — `hstore_gin.c.md`, `hstore_gist.c.md`.
- `knowledge/files/contrib/hstore/hstore_compat.c.md` — the legacy-format
  upgrade path that this header explicitly waves through.

## Issues spotted

- `[ISSUE-defense-in-depth: HENTRY_POSMASK silently truncates top-2 bits;
  only secondary validation catches forged endpos values (maybe)]`
- `[ISSUE-audit-gap: HS_COPYITEM/HS_ADDITEM macros memcpy without internal
  length cap; correctness depends on every caller pre-validating (likely)]`
- `[ISSUE-documentation: comment on hstore.h:88-89 names hstore_compat.c as
  "the exception" that touches HEntry bits directly, but never names
  hstore_io.c's hstorePairs as the OTHER place HEntry bits are written
  (HS_ADDITEM/HS_COPYITEM/HS_FINALIZE are inline header macros that wrap
  this); the comment is technically correct but underspecifies (nit)]`
- `[ISSUE-api-shape: HSTORE_POLLUTE_NAMESPACE defaults to 1, so old
  pre-namespace names (fetchval, exists, delete, ...) are registered as
  SQL-visible C symbols even in modern installs; restoring an ancient dump
  is the stated rationale, but every new install pays for it (maybe)]`
