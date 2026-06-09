# contrib/bloom/blutils.c

**Pin:** `4b0bf0788b066a4ca1d4f959566678e44ec93422`
**LOC:** 498
**Verification depth:** full read

## Role

Utility layer of the bloom index AM: registers the index AM via
`blhandler` (`IndexAmRoutine`), parses reloptions, initializes index
state and metapage, allocates pages, and — crucially — implements
`signValue`: hashing a Datum into the bloom signature.
[verified-by-code] `source/contrib/bloom/blutils.c:1-25`

## Public API

- `blhandler(PG_FUNCTION_ARGS)` — returns a static const `IndexAmRoutine`
  with all 30+ AM callbacks wired up and AM capability flags
  (`amcanorder=false, amcanunique=false, amcanmulticol=true,
  amcanparallel=false, amcanbuildparallel=false`, etc.).
  [verified-by-code] `source/contrib/bloom/blutils.c:102-161`
- `_PG_init()` — adds the `length` reloption and `col1..colN` per-column
  bit-count reloptions; runs at LOAD time.
  [verified-by-code] `source/contrib/bloom/blutils.c:49-78`
- `initBloomState(state, index)` — populates hash function infos +
  collations, lazily caches `BloomOptions` on `index->rd_amcache`.
  [verified-by-code] `source/contrib/bloom/blutils.c:167-214`
- `signValue(state, sign, value, attno)` — set bits in the signature
  for one column's value.
  [verified-by-code] `source/contrib/bloom/blutils.c:266-293`
- `BloomFormTuple` — builds a `BloomTuple` from a row of Datums (NULLs
  skipped — they contribute no bits).
  [verified-by-code] `source/contrib/bloom/blutils.c:298-317`
- `BloomPageAddItem` — appends a `BloomTuple` to a page's tail.
  [verified-by-code] `source/contrib/bloom/blutils.c:323-351`
- `BloomNewBuffer` — FSM-first, extend-after fallback.
  [verified-by-code] `source/contrib/bloom/blutils.c:358-399`
- `BloomInitPage`, `BloomFillMetapage`, `BloomInitMetapage`.
- `bloptions(reloptions, validate)` — parses + converts `length` from
  bits to words.
  [verified-by-code] `source/contrib/bloom/blutils.c:480-497`

## Invariants

- INV-1: Signature bit position for each value is `myRand() %
  (bloomLength * SIGNWORDBITS)`. RNG is seeded via `mySrand(attno)` then
  re-seeded with `mySrand(hashVal ^ myRand())` so the same Datum in
  different columns hits different bits.
  [verified-by-code] `source/contrib/bloom/blutils.c:266-293`
- INV-2: `BloomOptions` is frozen at index-create time on the metapage —
  `bloptions` parses reloptions, `BloomFillMetapage` copies them to the
  metapage, and from then on `initBloomState` reads from the cached
  metapage value. No way to change `length` or per-column `bitSize`
  after creation.
  [verified-by-code] `source/contrib/bloom/blutils.c:419-446, 182-214`
- INV-3: Magic numbers validated on every `initBloomState` —
  `BloomPageIsMeta` flag and `meta->magickNumber == BLOOM_MAGICK_NUMBER
  (0xDBAC0DED)`.
  [verified-by-code] `source/contrib/bloom/blutils.c:197-203`
- INV-4: AM uses `generic_xlog` for WAL (no custom RMGR), declared via
  the imports + `BloomInitMetapage` using `GenericXLogStart`.
  [verified-by-code] `source/contrib/bloom/blutils.c:17, 467-472`
- INV-5: `amcanparallel=false`, `amcanbuildparallel=false`,
  `amcanunique=false`, `amcaninclude=false` — bloom does NOT support
  parallel scan / parallel build / uniqueness / INCLUDE columns.
  [verified-by-code] `source/contrib/bloom/blutils.c:114-128`

## Notable internals

- **Custom RNG (Park-Miller LCG)** at lines 225-260, not `pg_prng_*`.
  Two stated reasons: (1) signatures are on-disk, so RNG stability
  across PG versions matters; (2) re-seeding the global PG RNG would
  have undesirable side effects on other code.
  [verified-by-code] `source/contrib/bloom/blutils.c:216-260`
- **Hash function dispatch**: each column uses its opclass's
  `BLOOM_HASH_PROC` (proc number 1) returning an INT4 — see blvalidate.c
  for signature check. Hashing relies on `fmgr_info_copy` for fast
  invocation.
  [verified-by-code] `source/contrib/bloom/blutils.c:174-180, 284`
- **Reloption registration is module-global** (one `bl_relopt_kind`
  allocated in `_PG_init`); `bl_relopt_tab` is also module-global,
  indexed by column number, with `optname` for `col2..colN` strdup'd
  into `TopMemoryContext` so it survives forever.
  [verified-by-code] `source/contrib/bloom/blutils.c:35-38, 66-77`

## Trust-boundary / Phase-D surface

- **`signValue` uses a deterministic RNG seeded with the column index +
  hash of the value** [verified-by-code:266-293]. This means an
  attacker who knows the AM's algorithm AND can choose what to index
  CAN construct values whose signatures collide with a target value's
  signature.  Because index-AM matching is `(itup->sign & search) ==
  search`, the collision produces a *false positive* — but the heap
  visibility recheck filters it.  Net effect: degraded scan
  performance, not data leak. **ISSUE-D1 (info)**.
- **Custom RNG is NOT cryptographic** — Park-Miller LCG with period
  `2^31 - 1`. By design and explicitly justified.
- **Per-index reloptions are clamped by `add_int_reloption`** to
  `[1, MAX_BLOOM_LENGTH]` for `length` and `[1, MAX_BLOOM_BITS]` for
  each `colN`. `length=1` is technically allowed and would produce
  a useless 1-word (16-bit) signature; not a security issue.
  [verified-by-code] `source/contrib/bloom/blutils.c:57-72`
- **`initBloomState` performs Relation-is-a-bloom-index validation via
  the magic-number check** — guarding against an operator deliberately
  passing the wrong relation to amcheck-style code paths. Good.
  [verified-by-code] `source/contrib/bloom/blutils.c:197-203`
- **No path injection, no shell-out, no extension-call sites.**

## Cross-refs

- `source/src/backend/access/transam/generic_xlog.c`.
- `source/src/backend/access/common/reloptions.c`.
- Sibling files: `blinsert.c`, `blscan.c`, `blvacuum.c`, `blvalidate.c`,
  `blcost.c`.

## Issues raised

- **ISSUE-D1 (info)** — `signValue` is deterministic; attacker can
  craft colliding signatures, only inflating false-positive rate.
  Heap recheck prevents data leak.
