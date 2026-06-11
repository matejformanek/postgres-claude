# CB1 implementation notes

## Phase 1 — implementation (single phase per R3)

**Status:** done.
**Commit:** `2dda343c518 pgcrypto: cap decompressed output at MaxAllocSize` (dev/ branch `feature_cb1_pgcrypto_bomb`)
**Test scope:** `meson test --suite pgcrypto` — green (25/25 subtests).
**Broader test:** `meson test --no-rebuild` — 99 OK, 1 unrelated pre-existing ecpg flake (same as the previous Phase D patches).

### What changed

Three files in `dev/`, all under `contrib/pgcrypto/`:

1. **`pgp-compress.c`** — added `#include "utils/memutils.h"` for `MaxAllocSize`; added `uint64 total_out` to `DecomprData`; added cumulative cap check right after the existing `inflate()` call site in `decompress_read`. +14 LOC.
2. **`px.h`** — added `PXE_PGP_OUTPUT_LIMIT_EXCEEDED -124` next to the existing PXE_PGP_* codes. +1 LOC.
3. **`px.c`** — added the error-string entry to `internal_error_table`. +1 LOC.

Net: +20/-0 LOC, single conceptual change.

### Surprises / drift

1. **`#include` placement at top of file, not in `#ifdef HAVE_LIBZ`.** The original sketch envisioned placing the new include alongside `<zlib.h>` (inside the `#ifdef HAVE_LIBZ` block), but `MaxAllocSize` is needed unconditionally — moved up to the unconditional include block at the top of the file. Trivial but worth noting.

2. **No PXE code re-use; chose to add a new one.** Considered re-using `PXE_PGP_CORRUPT_DATA` (which is already used for inflate errors) with a px_debug differentiator, but a dedicated code is clearer to consumers (e.g. extensions wrapping pgcrypto) and matches the existing naming pattern. The cost is 2 lines in px.h + px.c.

3. **Cap chose MaxAllocSize, not a smaller hardcoded constant.** The pitch suggested 1 GiB, which is equivalent to MaxAllocSize. Using the existing PG-wide symbol means the cap automatically tracks any future change to MaxAllocSize and matches the actual bound on the result bytea/text.

4. **No regression test added.** Same reasoning as SP2 + CB7's existing-test challenge: a real decompression bomb fixture is ~few KB compressed + tens-of-MB to GB decompressed. Including a binary fixture in `sql/pgp-compression.sql` would require base64 scaffolding (~50-100 LOC) for a single error-path test. Decided to skip and rely on structural correctness; can add if hackers want one.

### What this phase did NOT do

- Did NOT add a GUC. `pgcrypto.max_decompressed_size` could be a follow-up if operators need tighter caps on low-memory boxes; the structural ceiling is MaxAllocSize and operators wanting tighter bounds would be filing a different patch.
- Did NOT touch the encryption / non-compression paths. Symmetric encryption + decryption without compression are unaffected.
- Did NOT cap intermediate compression-format frames (the pitch's "Defense in depth" suggestion). The current frame-by-frame inflate is bounded by ZIP_OUT_BUF = 8 KB per call; the cumulative cap is what matters here.

### Submission readiness

- `format-patch` ready: `git format-patch e18b0cb7344..feature_cb1_pgcrypto_bomb --output-directory ../cb1-pgcrypto-bomb/`
- Patch subject: `pgcrypto: cap decompressed output at MaxAllocSize`
- Backpatch candidates: yes (confirmed DoS via public SQL API). v16, v17, v18 share pgp-compress.c.
- CF target: 60 (January 2026).

### End-of-implementation gate (R12)

- [x] Full `meson test --no-rebuild` — 99 OK, 1 unrelated pre-existing ecpg flake
- [x] `git log --oneline e18b0cb7344..HEAD` shows exactly 1 commit
- [x] Commit message in upstream PG style
- [x] Local branch ready
- [ ] Upstream-bound: needs review-checklist + patch-submission. NEXT STEP.

### Next step

Per the user's "merge anything relevant and continue" directive: open a meta PR, merge, and continue to the next quick-win.
