# copyfromparse.c

- **Source path:** `source/src/backend/commands/copyfromparse.c`
- **Lines:** 2324
- **Last verified commit:** `ef6a95c7c64`
- **Companion files:** `copyfrom.c`, `copy.h`, `copyfrom_internal.h`, `mb/pg_wchar.c` (encoding conversion).

## Purpose

"Parse CSV/text/binary format for COPY FROM. The main entry point is `NextCopyFrom()`, which parses the next input line and returns it as Datums." [from-comment, copyfromparse.c:3-7]

## The four-stage buffer pipeline [load-bearing]

The top-of-file comment (lines 9-46) is the authoritative architecture diagram. Briefly:

```
[data source] → raw_buf → input_buf → line_buf → attribute_buf
              1.        2.          3.         4.
```

1. **`CopyLoadRawBuf`** (596) — reads bytes from file / frontend / program into `cstate->raw_buf` (`RAW_BUF_SIZE = 65536`).
2. **`CopyConvertBuf`** (406) — runs the client→server encoding conversion function on raw bytes, depositing into `input_buf`. **Shortcut:** if client and server encodings match, `input_buf` is aliased to `raw_buf` and this step only validates encoding.
3. **`CopyReadLine`** (1236) / **`CopyReadLineText`** (1467) / **`CopyReadLineTextSIMDHelper`** (1329) — find the next line terminator honouring quoting/escaping rules, copy bytes into `line_buf` with quotes still present.
4. **`CopyReadAttributesText`** (1829) / **`CopyReadAttributesCSV`** (2083) — split `line_buf` on delimiter, unescape, populate `attribute_buf` and `cstate->raw_fields[]` (an array of `char*` pointers into attribute_buf).

For binary mode, the pipeline is much simpler — input is loaded into `raw_buf` and `CopyFromBinaryOneRow` (1164) reads per-column length+bytes calling each type's binary input function (recv). [from-comment, copyfromparse.c:39-46]

## Public surface

- `ReceiveCopyBegin` (174), `ReceiveCopyBinaryHeader` (194) — frontend-protocol handshake.
- `CopyGetData` (249) — low-level read from current source; abstracts file / pipe / frontend.
- `CopyGetInt32` / `CopyGetInt16` (368, 385) — network-byte-order readers for binary mode.
- `CopyLoadRawBuf` (596), `CopyLoadInputBuf` (656) — fill the lower-stage buffers.
- `CopyReadBinaryData` (707) — like CopyGetData but ensures `nbytes` exactly (used by binary headers).
- `NextCopyFromRawFields` (753) — split current line into fields without converting to Datums; used by `COPY ... TO PROGRAM`-style chained tools that want raw text per column.
- `NextCopyFrom` (887) — **the canonical entry from `copyfrom.c:CopyFrom`**. Calls the format routine's OneRow function (text/CSV: `CopyFromTextLikeOneRow` 953; binary: `CopyFromBinaryOneRow` 1164), runs each column's `typinput`/`typrecv`, applies defaults for omitted/NULL columns.
- `CopyReadLineTextSIMDHelper` (1329) — SIMD-accelerated newline+quote scan for text mode (PG 17+). Falls back to byte-at-a-time on non-x86 or when escapes/multibyte chars require it.

## CSV vs text mode parsing differences

CSV mode handles: quoted fields (`"`), doubled-quote escape (`""` → `"`), embedded newlines inside quotes, optional `ESCAPE` character distinct from quote. Text mode uses `\` as the escape (sequences like `\N` for NULL, `\.` end-of-data marker, `\b`/`\t`/`\n`/`\r` for control chars). Binary mode has none of this — explicit length prefixes everywhere, plus a fixed 11-byte signature + 32-bit flag field + 32-bit header-extension area at the start.

## Confidence tag tally

`[verified-by-code]=4 [from-comment]=4`

## Synthesized by
<!-- backlinks:auto -->
- [subsystems/optimizer.md](../../../../subsystems/optimizer.md)
- [idioms/error-context-callbacks.md](../../../../idioms/error-context-callbacks.md)
- [subsystems/contrib-file_fdw.md](../../../../subsystems/contrib-file_fdw.md)

