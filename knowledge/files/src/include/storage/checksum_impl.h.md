# `src/include/storage/checksum_impl.h`

- **Last verified commit:** `e18b0cb7344`
- **Lines:** ~201
- **Source:** `source/src/include/storage/checksum_impl.h`

The actual page-checksum implementation, written so that **external
programs** (`pg_verify_checksums`-style frontend tooling, `pg_rewind`,
`pg_basebackup`, third-party tools) can `#include` it standalone and
get a working `pg_checksum_page()` without linking against the backend.
The backend itself defines `PG_CHECKSUM_INTERNAL` first so that the
function-pointer-based dispatch in `src/backend/storage/page/checksum.c`
(which selects between scalar, SSE4.2, AVX-512, etc. at runtime) wins
instead of the static inline. [verified-by-code] [from-comment]

## API / declarations

- `#define N_SUMS 32` — number of parallel FNV-1a hashes (also picks
  the SIMD column width). Hard-coded; changing it changes the wire
  format of `pd_checksum` for every page. [verified-by-code]
- `#define FNV_PRIME 16777619` — standard 32-bit FNV prime. [verified-by-code]
- `typedef union PGChecksummablePage` — `BLCKSZ`-sized union of a
  `PageHeaderData` view (for zeroing `pd_checksum`) and a `[BLCKSZ /
  128][32]` `uint32` matrix view (for the SIMD loop). Strict-aliasing
  safe via the union. [verified-by-code] [from-comment]
- `static const uint32 checksumBaseOffsets[N_SUMS]` — 32 fixed
  pseudo-random uint32s used as per-column FNV seeds. Changing them
  changes every checksum on disk. [verified-by-code]
- `#define CHECKSUM_COMP(checksum, value)` — one FNV round with the
  PG-specific high-bit mixing tweak: `hash = (hash ^ value) * FNV_PRIME
  ^ ((hash ^ value) >> 17)`. The `>> 17` is the only deviation from
  textbook FNV-1a. [verified-by-code] [from-comment]
- `static uint32 (*pg_checksum_block)(const PGChecksummablePage *)` —
  in backend builds (when `PG_CHECKSUM_INTERNAL` is defined) the symbol
  is a function pointer assigned at startup by checksum.c. [verified-by-code]
- `static uint32 pg_checksum_block(const PGChecksummablePage *page)` —
  in external builds, the same name is a static function whose body
  is supplied by including `checksum_block_internal.h`. [verified-by-code]
- `uint16 pg_checksum_page(char *page, BlockNumber blkno)` — the
  public entry point. Temporarily zeros `pd_checksum`, calls the block
  primitive, XORs in `blkno` (to catch page-transposition corruption),
  and folds to `(checksum % 65535) + 1` so the on-disk value is never
  0. [verified-by-code] [from-comment]

## Notable invariants / details

- The exhaustive algorithm-rationale comment (lines 19-103) names the
  *why* of every design choice — SIMD-friendliness, the 17-bit shift,
  the choice of 32 parallel sums, the 2 trailing zero-mixing rounds.
  This is a rare in-tree example of a non-trivial cryptographic-ish
  primitive being fully justified at the use site rather than only in
  a design wiki. [from-comment]
- The header explicitly invites external use ("you may need to
  redefine `Assert()` as empty"). Any signature or seed change is
  therefore a **frontend ABI break** for downstream programs that
  embedded this header. [from-comment]
  [ISSUE-undocumented-invariant: external-tool dependence is
  documented in head comment but not exposed in the build system —
  changing seeds or N_SUMS silently breaks pgrewind-alikes (nit)]
- `pg_checksum_page` transiently writes 0 to the caller's page memory
  at offset `pd_checksum`. Caller must own the page mapping or have
  exclusive access; otherwise a concurrent reader could observe a
  zero-checksum page. The comment ("Beware also that the checksum
  field of the page is transiently zeroed") flags this but offers no
  enforcement. [from-comment]
  [ISSUE-correctness: transient `pd_checksum=0` write needs caller-side
  exclusive access; no Assert (nit)]
- Final fold `(checksum % 65535) + 1` deliberately avoids 0 as an
  on-disk value (since 0 marks "checksums disabled" on the page).
  Bias is documented as acceptable. [from-comment]
- `Assert(!PageIsNew((Page) page))` (line 179) enforces that
  fresh-zeroed pages never reach this code path — they're checksummed
  only after first init. [verified-by-code]

## Potential issues

- Line 173-189. The function takes `char *page` (mutable) only because
  of the transient `pd_checksum` overwrite. A const-correct alternative
  would memcpy `pd_checksum` to a local, NULL it via union view, and
  fold post-hoc. The mutable input is a long-standing API choice. [verified-by-code]
  [ISSUE-style: API takes mutable page only to transiently zero one
  field; const-friendly variant would simplify frontend use (nit)]
- Lines 113-117. The union view assumes `BLCKSZ % (sizeof(uint32) *
  N_SUMS) == 0` (i.e. BLCKSZ is a multiple of 128). PG's `BLCKSZ`
  choices (8K default, 1K-32K configured) all satisfy this, but no
  `StaticAssert` enforces it; building with an exotic non-multiple
  `BLCKSZ` would yield a wrong-size matrix. [verified-by-code]
  [ISSUE-undocumented-invariant: implicit `BLCKSZ % 128 == 0` constraint
  not StaticAsserted (nit)]
