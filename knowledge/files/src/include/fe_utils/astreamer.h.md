---
path: src/include/fe_utils/astreamer.h
anchor_sha: 4b0bf0788b066a4ca1d4f959566678e44ec93422
loc: 231
depth: read
---

# `src/include/fe_utils/astreamer.h`

- **File:** `source/src/include/fe_utils/astreamer.h` (231 lines)
- **Last verified commit:** `4b0bf0788b066a4ca1d4f959566678e44ec93422` (2026-06-05)

## Purpose

Defines the **archive-streamer** ("astreamer") composable-pipeline interface used by
`pg_basebackup` and `pg_verifybackup` to process possibly-compressed tar archives. The
design is a chain of streamers: each receives chunks, may transform/annotate them, and
forwards to its `bbs_next` successor. A typical pipeline is `gzip_decompressor → tar_parser
→ extractor`. This header carries the vtable (`astreamer_ops`), the base struct
(`astreamer`), the per-member metadata struct (`astreamer_member`), the chunk classification
enum, the three static-inline dispatch wrappers, two buffering helpers, and the `_new`
constructors for every concrete streamer type. The implementations live in the
`src/fe_utils/astreamer_*.c` family. `[verified-by-code]` `[from-comment]` (:5-22)

## Public symbols

| Symbol | Line | Role |
|---|---|---|
| `astreamer` / `astreamer_ops` (fwd) | :38-41 | Opaque forward decls + typedefs. |
| `astreamer_archive_context` | :62 | Chunk class: UNKNOWN / MEMBER_HEADER / MEMBER_CONTENTS / MEMBER_TRAILER / ARCHIVE_TRAILER. |
| `astreamer_member` | :79 | Per-member metadata: `pathname[MAXPGPATH]`, size, mode, uid, gid, is_regular/dir/symlink, `linktarget[MAXPGPATH]`. |
| `struct astreamer` | :109 | Base: `bbs_ops` vtable ptr + `bbs_next` successor + `bbs_buffer` (StringInfoData). |
| `struct astreamer_ops` | :126 | The 3 callbacks: `content`, `finalize`, `free`. |
| `astreamer_content` | :136 | Inline dispatch → `bbs_ops->content`. |
| `astreamer_finalize` | :146 | Inline dispatch → `bbs_ops->finalize`. |
| `astreamer_free` | :154 | Inline dispatch → `bbs_ops->free`. |
| `astreamer_buffer_bytes` | :167 | Move `nbytes` from `*data` into `bbs_buffer`; adjust `*data`/`*len`. |
| `astreamer_buffer_until` | :185 | Accumulate until `bbs_buffer.len >= target_bytes`; returns reached?. |
| `astreamer_*_new` | :213-229 | Constructors: plain_writer, gzip_writer, extractor, gzip/lz4/zstd (de)compressors, tar parser/terminator/archiver. |

## Internal landmarks

- **Chunk-sequence contract** (`:43-60`): once an archive is parsed, every chunk is labelled;
  there is **exactly one** `MEMBER_HEADER` and **exactly one** `MEMBER_TRAILER` per member
  (even if that means a zero-length call), any number of `MEMBER_CONTENTS` between, and
  **exactly one** `ARCHIVE_TRAILER` following the last member trailer. Concrete streamers rely
  on this to know when to open/close files. `[from-comment]` (:49-56)
- **No memory contexts** (`:118-124`): the `free` callback exists precisely because this runs
  in a frontend environment with no palloc/MemoryContext; each streamer must release its own
  memory explicitly. `[from-comment]` (:121-123)
- `astreamer_buffer_until` (`:185-207`) is the re-entrant accumulation primitive every parser
  uses to reach a fixed-size header/record boundary across arbitrary input chunking. `[verified-by-code]`

## Invariants & gotchas

- **Struct-prefix convention enforced only by comment.** "Generally, each type of astreamer
  will define its own struct, but the first element should be 'astreamer base'" (`:94-96`).
  Every concrete streamer struct is cast to/from `astreamer *`, so the base must be the first
  member — but there is no `StaticAssertDecl`/`offsetof` guard. This is the same load-bearing
  copy-paste-prefix pattern flagged in plpgsql (A9 `PLpgSQL_function`/`PLpgSQL_variable`). `[from-comment]` (:94-96)
- `astreamer_member.pathname[MAXPGPATH]` and `.linktarget[MAXPGPATH]` (`:81,90`) are
  **fixed-size buffers filled from server-supplied tar header bytes** — the trust boundary the
  A4 pg_basebackup sweep flagged and the A11 `astreamer_tar.c` doc confirmed. The header just
  declares the struct; the validation (`isValidTarHeader`, `path_is_safe_for_extraction`) lives
  in the parser/extractor `.c` files. See `knowledge/issues/fe_utils.md` rows `astreamer_tar.c:305`,
  `astreamer_file.c:248`. `[verified-by-code]`
- All three dispatch wrappers `Assert(streamer != NULL)` (`:141,149,157`) — in a frontend
  `Assert` is compiled out of release builds, so a NULL streamer in the pipeline is UB in
  production. Pipelines are constructed statically so this is defensive only. `[verified-by-code]`

## Cross-refs

- Implementations: `knowledge/files/src/fe_utils/astreamer_{file,tar,gzip,lz4,zstd}.c.md`.
- Trust-boundary + decompression-bomb analysis: `knowledge/issues/fe_utils.md` (§Notes
  "Backup-stream-trust" and "Decompression-bomb").
- Compression spec it consumes: `common/compression.h` (`pg_compress_specification`).

<!-- issues:auto:begin -->
- [Issue register — `fe_utils`](../../../../issues/fe_utils.md)
<!-- issues:auto:end -->

## Potential issues

- **[ISSUE-undocumented-invariant: astreamer base-must-be-first-member is comment-only]**
  `astreamer.h:94` — every concrete streamer is cast through `astreamer *`, requiring the
  `astreamer` base as the first struct member, but nothing enforces it at compile time (no
  `StaticAssertDecl`). A future streamer that reorders its struct silently corrupts the
  pipeline. Severity `nit`; same class as the A9 plpgsql struct-prefix finding. Mirrored to
  `knowledge/issues/fe_utils.md`.
