# `access/toast_internals.h` — TOAST chunk + compression internals

**Verified against source pin `4b0bf0788b0`** (path: `source/src/include/access/toast_internals.h`)

## Role
Low-level TOAST primitives shared between heap TOAST and table-AM TOAST:
the compressed-toast on-disk header layout, save/delete of individual
toast datums, toast-index handling, and the toast snapshot helper.

## Public API
- `toast_compress_header` struct (`toast_internals.h:23`): `vl_len_` varlena
  header + `tcinfo` (2 bits compression method, 30 bits external size).
- `TOAST_COMPRESS_EXTSIZE(ptr)` macro (`toast_internals.h:34`).
- `TOAST_COMPRESS_METHOD(ptr)` macro (`toast_internals.h:36`).
- `TOAST_COMPRESS_SET_SIZE_AND_COMPRESS_METHOD(ptr, len, cm_method)` macro
  (`toast_internals.h:39`).
- `toast_compress_datum(value, cmethod)` (`toast_internals.h:48`).
- `toast_get_valid_index(toastoid, lock)` (`toast_internals.h:49`).
- `toast_delete_datum(rel, value, is_speculative)` (`toast_internals.h:51`).
- `toast_save_datum(rel, value, oldexternal, options)` (`toast_internals.h:52`).
- `toast_open_indexes(toastrel, lock, **toastidxs, *num_indexes)`
  (`toast_internals.h:55`).
- `toast_close_indexes(toastidxs, num_indexes, lock)` (`toast_internals.h:59`).
- `get_toast_snapshot(void)` (`toast_internals.h:61`).

## Invariants
- `tcinfo` packs 2 bits of method code (`TOAST_PGLZ_COMPRESSION_ID=0` or
  `TOAST_LZ4_COMPRESSION_ID=1`) into the high bits and 30 bits of size
  into `VARLENA_EXTSIZE_MASK`. `[verified-by-code]` (`toast_internals.h:39`-`46`).
- Max compressed external size is `2^30 - 1` ≈ 1 GiB (per `VARLENA_EXTSIZE_MASK`
  in `varatt.h`). Beyond that, asserts fire. `[verified-by-code]`
  (`toast_internals.h:41`).
- The compress-method code must be `TOAST_PGLZ_COMPRESSION_ID` or
  `TOAST_LZ4_COMPRESSION_ID` — anything else triggers Assert.
  `[verified-by-code]` (`toast_internals.h:42`-`43`).
- A toast table may have multiple valid indexes during REINDEX
  CONCURRENTLY; `toast_open_indexes` returns all of them.
  `toast_get_valid_index` returns the one to insert into.
  `[from-comment]` (`toast_internals.h:49`, `:55`-`58`).
- `get_toast_snapshot` returns the snapshot used to read toast chunks —
  typically a snapshot that ignores xmin/xmax (toast chunks are written
  atomically with their owning row). `[from-comment]` (`toast_internals.h:61`).

## Notable internals
- Only **two** compression methods are wired in. Adding a third requires
  more bits or an alternate scheme — the 2-bit field caps at 4 methods
  total. `[verified-by-code]` (`toast_internals.h:34`-`46`).
- `toast_save_datum` chunks a value into `TOAST_MAX_CHUNK_SIZE`-sized
  rows of the toast table (chunk_id = `valueid`, chunk_seq = seq number,
  chunk_data = bytes).
- `is_speculative` flag mirrors heap speculative insertion for ON CONFLICT
  handling (`toast_internals.h:51`).

## Trust-boundary / Phase D surface

**[ISSUE-security: compressed-header method field is 2-bit, only 2 values
valid (low)]** — A corrupted or malicious toast chunk could carry method
codes 2 or 3 (currently unused). Decompression code paths must handle this
defensively. The Assert at the producer side (`toast_internals.h:42`-`43`)
catches *write*; *read* must validate independently. `[inferred]`.

**[ISSUE-resource: 30-bit external size = 1 GiB cap per datum (informational)]** —
`VARLENA_EXTSIZE_MASK` caps a single TOASTed datum at ~1 GiB.
`toast_internals.h:34`-`41`. Larger requires the large-object API.

**[ISSUE-correctness: `get_toast_snapshot()` returns a non-MVCC snapshot
(informational)]** — Toast reads must be consistent with the owning row's
visibility; the special snapshot bypasses normal MVCC. Documented but a
subtle source of cross-tx reads if misused. `toast_internals.h:61`.

## Cross-refs
- `knowledge/files/src/include/access/heaptoast.h` — chunk size + page
  arithmetic.
- `knowledge/files/src/include/access/toast_helper.h` — per-attr state.
- `access/toast_compression.h` (not in this slice) — pglz/lz4 wrappers.
- A11 + A5: decompression-bomb echoes — caps live in the compression layer,
  not here.

<!-- issues:auto:begin -->
- [Issue register — `include-access`](../../../../issues/include-access.md)
<!-- issues:auto:end -->

## Issues
1. **[ISSUE-security: method field is 2-bit; reader must defend against unused codes (low)]**
   — `toast_internals.h:34`-`46`.
2. **[ISSUE-resource: 30-bit size = 1 GiB per-datum cap (informational)]**
   — `toast_internals.h:34`-`41`.
3. **[ISSUE-correctness: get_toast_snapshot bypasses normal MVCC (informational)]**
   — `toast_internals.h:61`.
