# slru_io.c

## Purpose

Single-segment, single-page SLRU file reader/writer used by
pg_upgrade's multixact format conversion. Stripped-down clone of the
backend's SLRU machinery: one fd per segment, one BLCKSZ buffer,
random-order page reads on the read side, sequential page writes on
the write side.

## Role in pg_upgrade

Used only by `multixact_read_v18.c` and `multixact_rewrite.c` for the
pre-v19 → current `MultiXactOffset` widening. The reader opens
`<old_pgdata>/pg_multixact/offsets` and `.../members` from the OLD
cluster (short segment names) and the writer creates fresh files
under `<new_pgdata>/pg_multixact/...` (long names for members,
short for offsets — see multixact_rewrite.c:55,59).

## Key functions

- `AllocSlruSegState(dir)` `slru_io.c:27` (static) — allocate +
  init defaults (segno = -1 sentinel, pageno = 0, fd = -1).
- `SlruFileName(state, segno)` `slru_io.c:44` (static) — formats
  the segment file name. Long format: `%015" PRIX64 ` (e.g.
  `00000000000003F`); short: `%04X` (e.g. `0AB7`).
- `AllocSlruRead(dir, long_segment_names)` `slru_io.c:62`,
  `AllocSlruWrite(dir, long_segment_names)` `slru_io.c:166`.
- `SlruReadSwitchPageSlow(state, pageno)` `slru_io.c:85` — opens the
  segment file for the requested page (if not already open),
  `pg_pread` loop until BLCKSZ bytes read. Special case: EOF before
  BLCKSZ → log WARNING "unexpected EOF ... reading as zeros" and
  zero-fill the remainder.
- `SlruWriteSwitchPageSlow(state, pageno)` `slru_io.c:187` — flushes
  the current page (`SlruFlush`), zero-fills the in-memory buffer,
  opens the new segment if changed (`O_RDWR | O_CREAT | O_EXCL`).
  If `offset > 0` at segment creation, writes zeros up to the
  offset (line 228 `pg_pwrite_zeros`).
- `SlruFlush(state)` `slru_io.c:239` — `pg_pwritev_with_retry` of the
  buffer to `state->pageno`'s offset.
- `FreeSlruRead`/`FreeSlruWrite` — close fd + free state.

## State / globals

None. All state in caller-allocated `SlruSegState`.

## Phase D notes

[from-code] **Trust boundary on OLD cluster's SLRU files.** The
reader does `open(O_RDONLY)` then `pg_pread` into a fixed buffer.
No content validation — the contents are passed straight back to
`multixact_read_v18.c::GetOldMultiXactIdSingleMember` which
arithmetically reasons about the bytes (length = next_offset -
current_offset, etc.). If the old `pg_multixact/offsets` file is
corrupted in just the right way, the result is silently wrong
multixid metadata in the new cluster's pg_multixact/.

[ISSUE-trust-boundary: SLRU page reader returns zero-filled buffer
on EOF with only a WARNING (slru_io.c:136-139); a truncated
pg_multixact file silently feeds zero offsets into the rewrite
(maybe-medium)] — Comment line 79-81 calls this out: "If the file
exists but is shorter than expected, the missing part is read as
zeros and a warning is logged. That is reasonable behavior for
current callers." Reasonable IF the caller (multixact_read_v18) is
prepared for zero-valued offsets (which it is: offset==0 → "invalid
entry").

[ISSUE-trust-boundary: `open(O_RDONLY)` with no `O_NOFOLLOW` on the
old cluster's SLRU files (low)] — `slru_io.c:112`. Old PGDATA is
operator-trusted.

[from-code] **`O_EXCL` on writer** (line 218) means a stale new
cluster's pg_multixact/ directory aborts; you must clean it first
(or use a fresh initdb). Comment line 179-182 documents this
limitation.

[from-code] **`pg_pwritev_with_retry`** (line 252) — full-buffer
write with EINTR/short-write retries. So writes are always full
BLCKSZ aligned; no torn-write window inside the SLRU page.

[from-code] **EOF read warning** (line 136) is printed via
`pg_log(PG_WARNING, ...)` — goes to stdout + internal log. Does NOT
abort. This is the only non-fatal anomaly path in the file.

[ISSUE-correctness: `SlruReadSwitchPageSlow` `pg_pread` EINTR loop
(line 129) — handles EINTR but not partial reads in mid-loop
correctly: a partial read advances `bytes_read` and continues, but
if rc returns 0 after a partial, the zero-fill kicks in only for the
remaining bytes. Documented behavior, correct.] —
`slru_io.c:119-143`.

[ISSUE-undocumented-invariant: `state->pageno` is updated AT END of
read (line 144); if `pg_fatal` fires inside the read loop the state
is half-updated. Since pg_fatal exits, this is harmless (low)] —
`slru_io.c:144`.

## Cross-references

<!-- issues:auto:begin -->
- [Issue register — `pg_upgrade`](../../../../issues/pg_upgrade.md)
<!-- issues:auto:end -->
