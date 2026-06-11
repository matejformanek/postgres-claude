# `src/bin/pg_walsummary/pg_walsummary.c`

- **Last verified commit:** `e18b0cb7344`
- **Lines:** ~277
- **Source:** `source/src/bin/pg_walsummary/pg_walsummary.c`

Pretty-prints a WAL summary file (`pg_wal/summaries/*.summary`). WAL
summaries are produced by the walsummarizer and consumed by incremental
backups (`pg_basebackup -i`); they describe which blocks were modified
in a range of LSNs. This tool is a debug-and-inspect utility that
formats them as `TS <oid>, DB <oid>, REL <oid>, FORK <name>: block N`
(or `blocks N..M` if a contiguous range and not `-i / --individual`).
[verified-by-code]

## API / entry points

- `main` — parses `-i / --individual` and `-q / --quiet`, then for each
  positional arg opens the file, wraps it with `CreateBlockRefTableReader`,
  iterates `BlockRefTableReaderNextRelation`, and dumps each rel.
  [verified-by-code]
- `dump_one_relation(opt, rlocator, forknum, limit_block, reader)` —
  prints the `limit` block (if any), then fills a `BlockNumber[]`
  buffer via `BlockRefTableReaderGetBlocks`, growing the buffer 2× as
  needed (with overflow guard at line 159-160 capping at PG_UINT32_MAX),
  qsorts (block order is only guaranteed for the bitmap-chunk
  representation, not for array-of-offsets), then emits ranges.
  [from-comment]
- `compare_block_numbers` — qsort callback wrapping `pg_cmp_u32`.
- `walsummary_read_callback` — `read(fd, data, length)`, fatal on
  failure. [verified-by-code]
- `walsummary_error_callback` — pg_log_generic + exit 1. [verified-by-code]
- `help(progname)` — usage. [verified-by-code]

## Notable invariants / details

- The block buffer is realloc-doubled. Initial size 512 (line 37),
  growth capped at `PG_UINT32_MAX` to avoid integer overflow on size
  arithmetic. [from-comment]
- Quiet mode skips output entirely but still drives the reader, so the
  tool serves as a parse-validation pass for summary files.
  [verified-by-code]
- The error_callback is declared `void` but `pg_attribute_printf(2, 3)`;
  it does not return (calls `exit(1)`) but isn't marked
  `pg_noreturn` — minor declaration quirk. [verified-by-code]
- The library code (`common/blkreftable.c`) does all the heavy lifting;
  this file is a thin CLI front-end. [verified-by-code]

## Potential issues

- `pg_walsummary.c:144-145` — `block_buffer` is allocated lazily on
  first call to `dump_one_relation` and **never freed across relations
  or files**. For benchmarking it's fine; for a long-running invocation
  with many files the buffer is only freed at process exit. Documented
  by the "Save the new size for later calls" comment at line 169-170,
  so this is intentional reuse. [verified-by-code]
- `pg_walsummary.c:153-171` — the grow-buffer loop calls
  `BlockRefTableReaderGetBlocks` again with `block_buffer +
  block_buffer_size`. This continues filling beyond what the first call
  returned — but `nblocks` is incremented by the second call's return
  value. If the second call returns 0 (rel boundary hit between calls)
  we exit the while loop with `nblocks < block_buffer_size` and proceed
  to qsort over only the validly-filled prefix. [verified-by-code]
- `pg_walsummary.c:107-108` — `O_RDONLY | PG_BINARY` open; no
  validation that the file is actually a summary file before handing
  it to the reader. The reader will error out on a bad magic, but the
  CLI doesn't add its own sanity check. [verified-by-code]
- `pg_walsummary.c:46` — `walsummary_error_callback` declared as
  `void` returning but called as a libcommon error callback that
  conceptually returns. Calls `exit(1)` so really `pg_noreturn`.
  Inconsistent with `report_fatal_error` in `pg_verifybackup` which
  IS marked `pg_noreturn`. [ISSUE-style: missing pg_noreturn on
  exit-only function (nit)]
