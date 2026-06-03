# datapagemap.c

## Purpose

Tiny bitmap implementation for tracking which blocks of a relation file
have been modified — one entry per `BlockNumber`. Bit `blkno` lives at
`bitmap[blkno/8] & (1 << (blkno%8))`. Bitmap is grown lazily by
`pg_realloc` with a +10-byte headroom heuristic.

## Role in pg_rewind

Backing store for `file_entry_t::target_pages_to_overwrite` etc.
`extractPageInfo()` in `parsexlog.c` adds bits as it walks WAL; the
filemap-driven fetch pass iterates each bitmap to enumerate dirty blocks
to request from the source.

## Key functions

- `datapagemap_add(map, blkno)` (`source/src/bin/pg_rewind/datapagemap.c:31-65`).
  Computes `offset = blkno/8`, `bitno = blkno%8`. If `bitmapsize <= offset`,
  `pg_realloc`s to `offset + 1 + 10` bytes, zero-fills the new tail, and
  sets the bit. The +10 byte slack avoids quadratic realloc when blocks
  arrive in ascending order — the common case for WAL replay.
- `datapagemap_iterate(map)` (`:74-84`). Mallocs an iterator that walks
  bits in ascending `BlockNumber` order. Caller `pg_free`s.
- `datapagemap_next(iter, *blkno)` (`:86-111`). Linear scan over every
  bit position, returning each set bit. O(MaxBlock) regardless of
  density — fine for a typical rewind (small set).
- `datapagemap_print(map)` (`:116-127`). Debug iteration via
  `pg_log_debug("block %u", ...)`.

## State / globals

None. All state lives in the caller-owned `datapagemap_t`.

## Phase D notes

This is a build-target bitmap, not a security boundary. The block
numbers flow in from WAL parsing (`extractPageInfo()`); they are
trusted in the sense that any malicious value would have to come from
WAL on disk already under the operator's control. Still:

- Realloc can fail (returns NULL via `pg_realloc` — actually
  `pg_malloc.c`'s wrapper `pg_fatal`s on OOM, so safe).
- `memset` of `newsize - oldsize` bytes assumes the realloc succeeded
  and `bitmap` is the new pointer — correct.

## Potential issues

- `[ISSUE-dos: malicious WAL with absurd block numbers can drive
  bitmap allocation to ~512 MB per relfile (low)]` — `BlockNumber`
  is `uint32`. A WAL record naming `blkno = 0xFFFFFFFE` causes
  `offset = 0x1FFFFFFF` → `pg_realloc` of ~512 MB, then immediately
  `pg_fatal` if OOM. Multiplied across N relfiles in the filemap,
  this is a DoS vector if an attacker can plant WAL on the target.
  However the target's WAL is by definition local — not an external
  trust boundary. Low severity, but worth a note.
- `[ISSUE-undocumented-invariant: signed int offset / bitmapsize
  on a uint32 BlockNumber (maybe)]` — `offset = blkno / 8` is
  computed into a signed `int`. For `blkno > INT_MAX*8 ≈ 1.7e10`
  it would wrap, but `BlockNumber` caps at `MaxBlockNumber = 0xFFFFFFFE`
  so `offset` stays below 2^29. Safe in practice, undocumented.
- `[ISSUE-correctness: datapagemap_next is O(MaxBlock) per relation
  even when bitmap is mostly empty (low)]` — A sparse bitmap of size N
  takes N iterations to enumerate K set bits. For a typical rewind
  (small dirty set in a large relation) this is fine; for a hypothetical
  worst case (a few dirty blocks at the end of a many-GB relation) the
  iteration walks every byte. Not a security issue, just inefficient.
