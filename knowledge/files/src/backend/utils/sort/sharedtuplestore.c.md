# `src/backend/utils/sort/sharedtuplestore.c`

- **Last verified commit:** `e18b0cb7344`
- **Lines:** ~601
- **Source:** `source/src/backend/utils/sort/sharedtuplestore.c`

A parallel-aware temporary tuple-store backed by `BufFile`s in a
`SharedFileSet`. Designed for Parallel Hash Join: multiple worker
backends can write tuples concurrently (each to its own file), then
during the scan phase any worker can read tuples written by any other
worker. The only supported scan mode is "parallel" — i.e. each tuple
is read by exactly one worker, chosen dynamically by atomic page
claiming. [from-comment] [verified-by-code]

## Data layout

- **Chunk:** 4 pages × `BLCKSZ` = 32 KiB by default (`STS_CHUNK_PAGES
  = 4`). Header `SharedTuplestoreChunk { int ntuples; int overflow;
  char data[]; }` (line 42-47), data fills the rest. [verified-by-code]
- **Per-participant shared state:**
  `SharedTuplestoreParticipant { LWLock lock; BlockNumber read_page;
  BlockNumber npages; bool writing; }` (line 50-56). The lock
  serialises read-cursor advancement. [verified-by-code]
- **Control:** `SharedTuplestore { nparticipants; flags;
  meta_data_size; name[NAMEDATALEN]; participants[FLEX]; }` —
  followed by the per-participant array. [verified-by-code]
- **Per-backend accessor (local):** holds the current read/write
  `BufFile *`, a buffered chunk under construction, and read cursor
  bookkeeping. [verified-by-code]

## API / entry points

- `sts_estimate(participants)` — bytes needed to hold a
  `SharedTuplestore` for N participants. [verified-by-code]
- `sts_initialize(sts, nparticipants, my_id, meta_data_size, flags,
  fileset, name)` — first-participant init. Stores name (errors if
  too long for `NAMEDATALEN`), validates `meta_data_size + sizeof(uint32)
  < STS_CHUNK_DATA_SIZE`. [verified-by-code]
- `sts_attach(sts, my_id, fileset)` — subsequent participants attach
  to an already-initialized control struct. [verified-by-code]
- `sts_puttuple(accessor, meta_data, tuple)` — write a MinimalTuple
  plus optional fixed-size meta. Handles oversized tuples by
  splitting across "overflow" chunks (header `overflow > 0`). [verified-by-code]
- `sts_end_write(accessor)` — flush, close, free the write buffer.
  Must be called by every writer before any reader runs. [verified-by-code]
- `sts_begin_parallel_scan(accessor)` — initialise the scan cursor.
  Starts on this participant's own file for "caching locality".
  Asserts no participant is still writing. [verified-by-code]
- `sts_parallel_scan_next(accessor, meta_data_out)` — claim the next
  chunk via per-participant lock + atomic `read_page` advance, decode
  it, return tuples one at a time. Walks across participants in a
  round-robin starting from `my_participant`. Returns NULL when done.
  [verified-by-code]
- `sts_end_parallel_scan(accessor)` — close any open read file. [verified-by-code]
- `sts_reinitialize(accessor)` — reset all read cursors to 0, enabling
  a rescan. "Only one participant must call this." [verified-by-code]

## Notable invariants / details

- **Single-writer per file:** each participant writes to exactly one
  BufFile named `<sts->name>.p<participant>`. Reads can interleave
  across participants' files but writes never share. [verified-by-code]
- **Read-page advancement is atomic per participant:** under
  `participants[read_participant].lock` (LWLock), read `read_page`,
  bump by `STS_CHUNK_PAGES`, release. Each worker gets a unique
  chunk. [verified-by-code]
- **Overflow chunks:** when a tuple exceeds remaining space, the
  current chunk's `ntuples` counts the *split* tuple as one, then N
  follow-on chunks each carry `chunk_header.overflow = remaining`
  and zero "regular" tuples. Readers skipping at chunk granularity
  see the `overflow > 0` and jump ahead by `overflow * STS_CHUNK_PAGES`
  pages, avoiding redundant lock work. [verified-by-code] [from-comment]
- **Round-robin scan after own file:** `read_participant =
  (read_participant + 1) % nparticipants` (line 581), loops until
  back to own participant. Means worker 0 may revisit chunks
  produced by worker 3 just *after* worker 3 visits them, but the
  per-page lock keeps each chunk claimed exactly once globally.
  [verified-by-code]
- **`writing` flag is assertion-only** (line 55: `Used only for
  assertions`). Begin-parallel-scan asserts no participant still
  has it true. Not consulted at runtime. [verified-by-code]
- **No SHARED_TUPLESTORE_SINGLE_PASS implementation yet:** the flag
  is plumbed (line 113) but the eager cleanup it would enable is a
  TODO documented in `sts_end_parallel_scan` (line 282-286) — needs
  a reference count. [verified-by-code] [from-comment]
  [ISSUE-stale-todo: SINGLE_PASS flag plumbed but no behavior
  attached (nit)]
- **`elog(ERROR, "SharedTuplestore name too long")`** at init: a
  name >= NAMEDATALEN is rejected. Callers must keep it under 63
  bytes. [verified-by-code]
- **`elog(ERROR, "meta-data too long")`** at init: `meta_data_size +
  sizeof(uint32)` must be strictly less than chunk data size
  (`STS_CHUNK_DATA_SIZE` ≈ 32760 bytes). [verified-by-code]
- **Read buffer growth:** `accessor->read_buffer` is `MemoryContextAlloc`'d
  in `accessor->context`, growing to the largest tuple seen
  (`Max(size, read_buffer_size * 2)`). Previous buffer is pfree'd
  before reallocation — no leak. [verified-by-code]
- **Filename collision risk:** `sts_filename` uses `<sts_name>.p<N>`.
  If two SharedTuplestores in the same `SharedFileSet` share the
  same name, files clash. The init-time docstring requires the name
  to be unique across the fileset. [from-comment]
  [ISSUE-undocumented-invariant: name uniqueness is caller's
  responsibility (nit)]
- **`sts_reinitialize` race:** comment says "must not be called
  concurrently with a scan, and synchronization to avoid that is
  the caller's responsibility." No internal guard. [from-comment]
  [ISSUE-undocumented-invariant: caller-side sync requirement (nit)]
- **`participants[].writing` is set true on first write** (line 321
  inside `sts_puttuple`) but is set false **only in `sts_end_write`**
  (line 221). If a backend aborts mid-write without calling
  `sts_end_write`, the flag stays true — but the asserts in
  `sts_begin_parallel_scan` would fire. In practice abort cleanup
  goes through SharedFileSet destruction; the flag is for
  diagnostics, not safety. [verified-by-code]

## Potential issues

- File-line: sharedtuplestore.c:282-286. SHARED_TUPLESTORE_SINGLE_PASS
  is a documented dead flag — comment explicitly says reference
  counting is TODO. [ISSUE-stale-todo: flag accepted but no semantics
  yet (nit)]
- File-line: sharedtuplestore.c:141-152. `strcpy` is used (not
  `strlcpy`) after the length check at line 141 — safe but
  inconsistent with PG's general preference for strlcpy. [ISSUE-style:
  `strcpy` after length check (nit)]
- File-line: sharedtuplestore.c:463-467. `chunk_header.overflow == 0`
  on a chunk reached during overflow-read path means the on-disk
  layout is corrupted; reported as `errcode_for_file_access` (file
  I/O error) which is semantically off — should arguably be
  `ERRCODE_DATA_CORRUPTED`. [ISSUE-style: errcode classification on
  corrupted chunk header (nit)]
- File-line: sharedtuplestore.c:201. `memset(write_chunk, 0, size)`
  AFTER `BufFileWrite` (the buffer is reused for the next chunk).
  Subtle ordering — if `BufFileWrite` performs async I/O the buffer
  could be in-flight while we memset. PG's `BufFileWrite` is
  synchronous (copies into its own buffer), so safe. [ISSUE-undocumented-invariant:
  reliance on BufFileWrite synchronous-copy semantics (nit)]
- File-line: sharedtuplestore.c:389-391. Overflow chunk count
  rounding: `(size + STS_CHUNK_DATA_SIZE - 1) / STS_CHUNK_DATA_SIZE`
  is the ceiling, but the comment says "How many overflow chunks to
  go? This will allow readers to skip all of them at once." The
  value written here applies to the *next* chunk (the first
  overflow), so it must include itself — verify: the value
  decreases by 1 on each subsequent overflow chunk? Looking at the
  write loop (line 380-399), each iteration recomputes from current
  remaining `size`, so each overflow chunk carries the count of
  *remaining* overflow chunks including itself. Readers at line
  556-559 skip by `chunk_header.overflow * STS_CHUNK_PAGES`. If the
  first overflow chunk says "3 to go" but actually only 2 follow,
  the skip overshoots by one chunk. Verify by example: tuple needs
  3 overflow chunks. Loop iter 1: size = full remaining, overflow
  = ceil(size/data) = 3. Writes one chunk worth, size shrinks.
  Iter 2: overflow = 2. Iter 3: overflow = 1. So reader sees `3`
  on the first overflow chunk, jumps `3 * 4 = 12` pages — exactly
  past the three overflow chunks. Correct. [verified-by-code]
- File-line: sharedtuplestore.c:434. `read_buffer_size * 2` doubling
  policy can over-shoot if the first oversized tuple is, say, 1 GB:
  buffer grows to 2 GB even if subsequent tuples are small. No
  shrink-back. [ISSUE-leak: read_buffer never shrinks within accessor
  lifetime (maybe)]
