# pgsql-hackers cover email — CB1 pgcrypto decompression bomb cap

**To:** pgsql-hackers@lists.postgresql.org
**Subject:** [PATCH] pgcrypto: cap decompressed output at MaxAllocSize
**Attach:** `0001-pgcrypto-cap-decompressed-output-at-MaxAllocSize.patch`

---

Hi hackers,

contrib/pgcrypto's `decompress_read` (in pgp-compress.c) inflates
zlib/zip-compressed OpenPGP packets via libz `inflate()` in 8 KB
chunks, called repeatedly until the stream ends.  There is no
output-size ceiling.

A small OpenPGP blob (10-100 KB) can encode a payload that decompresses
to many GB - the classic decompression-bomb shape.  `pgp_sym_decrypt`
and `pgp_pub_decrypt` are public SQL APIs reachable by any role with
EXECUTE (no REVOKE in the install scripts), so a hostile blob fed via
either entry point will inflate until the backend's bytea/text
aggregator trips the MaxAllocSize check.  At that point the backend
has already allocated nearly MaxAllocSize bytes plus burned the
corresponding CPU on the inflate.

The attached patch caps the cumulative output of the decompression
filter at MaxAllocSize -- the same ceiling that the eventual bytea/text
Datum must satisfy.  A new `uint64 total_out` counter on `DecomprData`
accumulates after each inflate() call; if the running total exceeds
MaxAllocSize, decompress_read returns a new
`PXE_PGP_OUTPUT_LIMIT_EXCEEDED` error code mapped to "Decompressed
output exceeds maximum allowed size".

Build + `meson test --suite pgcrypto` green on master @ e18b0cb7344
(25/25 subtests; no behavior change for normal-size inputs).

**Discussion points for reviewers:**

1. **Hardcoded MaxAllocSize, not a GUC.**  The cap is structural: the
   result bytea/text can never exceed MaxAllocSize in PostgreSQL, so
   anything past that is dead code.  Backpatch friendliness motivated
   skipping the GUC machinery.  Happy to add `pgcrypto.max_decompressed_size`
   as a follow-up if hackers want operator tunability.

2. **New error code, not re-using PXE_PGP_CORRUPT_DATA.**  Considered
   re-using -100 with a px_debug differentiator, but the new
   `PXE_PGP_OUTPUT_LIMIT_EXCEEDED -124` matches existing naming and
   gives consumers (extensions wrapping pgcrypto) a clean way to
   distinguish the bomb case from generic corruption.

3. **No regression test.**  A real bomb requires a binary fixture
   (~few KB compressed -> tens of MB to GB decompressed).  Including
   such a fixture in sql/pgp-compression.sql would need base64
   scaffolding (~50-100 LOC) for a single error-path test.  Decided to
   rely on structural correctness; can add if reviewers want one.

4. **Backpatch.**  Yes; confirmed DoS via a public SQL API.  v16, v17,
   v18 share pgp-compress.c verbatim.

Surfaced during a code-corpus sweep (postgres-claude/A11, 2026-06-09).

Thanks,
Matej

---

## After sending

1. Wait for the message to hit the archive: https://www.postgresql.org/list/pgsql-hackers/
2. Capture the archive message-id.
3. Open a CF entry at https://commitfest.postgresql.org/ targeting CF #60.
4. Add the CF link back to `postgres-claude/planning/cb1-pgcrypto-bomb/notes.md`.
