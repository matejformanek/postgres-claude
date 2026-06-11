# Plan: CB1 — pgcrypto decompression bomb cap

**Status:** READY. Single-phase plan.
**Pitch:** `knowledge/phase-d-pitches.md` CB1 (A11 critical finding)
**Source pin:** `e18b0cb7344cb4bd28468f6c0aeeb9b9241d30aa` (master at 2026-06-10)
**Slug:** `cb1-pgcrypto-bomb`
**Branch:** `feature_cb1_pgcrypto_bomb` (in `dev/`)
**Expected commits:** 1

## §1 Problem statement

`contrib/pgcrypto/pgp-compress.c::decompress_read` (`source/contrib/pgcrypto/pgp-compress.c:235-310`)
inflates zlib/zip-compressed PGP packets via libz `inflate()`.  The function is
called repeatedly until the stream ends.  There is **no output-size ceiling**:

- A small OpenPGP blob (10-100 KB) can encode a payload that decompresses to many
  GB (the classic decompression-bomb attack).
- `pgp_sym_decrypt(blob, pw)` and `pgp_pub_decrypt(blob, key, pw)` are public SQL
  APIs reachable by any role with EXECUTE — which is the default (no REVOKE in
  the install scripts).
- The decompressed output is consumed by `pgp_decrypt_*` and accumulated into a
  StringInfo / bytea, hitting `MaxAllocSize` eventually — but only after the
  attacker has driven backend memory to near MaxAllocSize and burned CPU on the
  inflate.  In practice this looks like backend OOM on the buildfarm-class boxes.

Surfaced 2026-06-09 by A11 sweep (foreground); catalogued as **CB1** in
`knowledge/phase-d-pitches.md`.

## §2 Approach

Add a per-stream `total_out` counter to `DecomprData` and cap it at
`MaxAllocSize`.  After every `inflate()` call we know exactly how many bytes were
just produced (`dec->buf_len - dec->stream.avail_out`); accumulate, and if the
running total exceeds the cap, return a new error code with a clear message.

Why `MaxAllocSize` is the right cap:

- The decompressed bytes are eventually accumulated into a single bytea/text
  Datum, which has `MaxAllocSize` as a hard ceiling.  A decompression that
  would exceed that can never succeed; failing earlier just avoids wasted work.
- It mirrors the existing PG-wide allocation contract.  Operators do not need
  to learn a new GUC.
- Backpatch friendly: no GUC machinery on stable branches.

A GUC `pgcrypto.max_decompressed_size` could be added later if operators need
to tighten further (e.g. < 1 GiB for low-memory boxes).  Reviewers may suggest
this; happy to add.

## §3 Files that change

| File | Change | LOC |
|---|---|---|
| `contrib/pgcrypto/pgp-compress.c` | Add `total_out` to `DecomprData`; check after each inflate | +14 |
| `contrib/pgcrypto/px.h` | New error code `PXE_PGP_OUTPUT_LIMIT_EXCEEDED` | +1 |
| `contrib/pgcrypto/px.c` | New error string in `internal_error_table` | +1 |

**Sites verified against current source (pin `e18b0cb7344`):**
- `source/contrib/pgcrypto/pgp-compress.c:193-201` — `DecomprData`
- `source/contrib/pgcrypto/pgp-compress.c:278-285` — `inflate()` + measurement of
  produced bytes
- `source/contrib/pgcrypto/px.h:67-80` — `PXE_PGP_*` error codes
- `source/contrib/pgcrypto/px.c` — `internal_error_table` mapping

## §4 Catalog impact

None.

## §5 Behavior changes

- Decompressed output ≤ MaxAllocSize: unchanged.
- Decompressed output > MaxAllocSize: previously could allocate up to
  MaxAllocSize of backend memory + waste CPU inflating, then ereport with
  the opaque "invalid memory alloc request size N".  Now errors at the first
  `inflate()` call past the cap with a specific
  `PXE_PGP_OUTPUT_LIMIT_EXCEEDED` code mapped to
  "Decompressed output exceeds maximum allowed size".

## §6 Test plan

No new regression test.  Constructing a true decompression bomb requires a
binary fixture (a small compressed blob whose decompressed form exceeds
MaxAllocSize).  Including the fixture as a base64 string in
`contrib/pgcrypto/sql/pgp-compression.sql` is feasible but adds ~100 lines of
test scaffolding.  Worth a follow-up if hackers want one.

**Phase-end check:** `meson test --suite pgcrypto` must pass (no behavior
change for non-hostile inputs); `meson test --no-rebuild` ≤ 1 pre-existing
flake (ecpg).

## §7 Implementation sketch

```c
/* in pgp-compress.c */
struct DecomprData
{
    int        buf_len;
    int        buf_data;
    uint8     *pos;
    z_stream   stream;
    int        eof;
    uint64     total_out;       /* NEW: bytes produced so far, capped at MaxAllocSize */
    uint8      buf[ZIP_OUT_BUF];
};

/* in decompress_read, after the inflate() call: */
dec->buf_data = dec->buf_len - dec->stream.avail_out;
dec->total_out += (uint64) dec->buf_data;
if (dec->total_out > (uint64) MaxAllocSize)
{
    px_debug("decompress_read: output exceeds MaxAllocSize");
    return PXE_PGP_OUTPUT_LIMIT_EXCEEDED;
}
```

```c
/* in px.h */
#define PXE_PGP_OUTPUT_LIMIT_EXCEEDED  -114   /* next free in -100..-113 range */
```

```c
/* in px.c, add to internal_error_table */
{PXE_PGP_OUTPUT_LIMIT_EXCEEDED, "Decompressed output exceeds maximum allowed size"},
```

## §8 Phase-end check

```bash
cd dev
ninja -C build-debug install
rm -rf build-debug/tmp_install
meson test -C build-debug --suite setup
meson test -C build-debug --suite pgcrypto
```

## §9 Risk + reviewer concerns

1. *"Why hardcoded MaxAllocSize and not a GUC?"* — Matches the existing PG-wide
   ceiling; output can never escape MaxAllocSize regardless.  GUC adds backpatch
   complexity.  Easy to convert if hackers prefer.
2. *"Error code numbering."* — Adding -114 follows the existing -100..-113
   block.  PXE_PGP_OUTPUT_LIMIT_EXCEEDED named symmetrically with the other
   PXE_PGP_* codes.
3. *"Why total_out tracking instead of inferring from buf?"* — `inflate()`
   processes data across many `decompress_read` calls; the bomb is the
   cumulative output across calls, not any single one.  A running counter is
   the minimal way to bound the total.
4. *"Backpatch."* — Yes; this is a confirmed DoS attack via a public SQL API.
   v16, v17, v18 all share `pgp-compress.c`.

## §10 Cross-corpus echoes

- A11 finding (`knowledge/issues/pgcrypto.md`)
- CB1 confirmed bug
- MP3 pgcrypto modernization series — this is sub-patch 6 of that meta-pitch.
- Shares the "size-cap based on MaxAllocSize" pattern with SP2 (pg_str* cap),
  CB7 (ltree variant cap).

## §11 Submission package

- `git format-patch e18b0cb7344..feature_cb1_pgcrypto_bomb --output-directory ../cb1-pgcrypto-bomb/`
- Patch subject: `pgcrypto: cap decompressed output at MaxAllocSize`
- Target: pgsql-hackers + commitfest 60.
- Backpatch candidate: yes.

## §12 Notes / surprises

(Empty at plan time. Populate in `notes.md` during implementation per R8.)
