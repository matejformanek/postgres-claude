# `src/include/storage/checksum.h`

- **Last verified commit:** `ef6a95c7c64`

## Purpose

One-function header for the data-page checksum entry point.

## Surface

- `pg_checksum_page(char *page, BlockNumber blkno) → uint16`

Implementation pointer is in `checksum.c`; algorithm body is in
`checksum_impl.h` (intentionally shipped as a header so external
tools can include it).

## Tag tally

`[verified-by-code]` 1.
