# Calibration — CB1 pgcrypto decompression bomb

**Patch:** `patches/cb1-pgcrypto-bomb/0001-pgcrypto-cap-decompressed-output-at-MaxAllocSize.patch`
**Cover:** `patches/cb1-pgcrypto-bomb/COVER.md`
**Methodology:** `knowledge/calibration/README.md`
**Calibrated at:** 2026-06-12 against `source` @ `e18b0cb7344` (pin from Phase B).
**Role:** methodology shake-down — the first patch run through the Phase C loop. Treat the §6 "skill edits" list here as the first sample of the gap catalog.

## 1. Patch summary

Adds a cumulative-output cap of `MaxAllocSize` to the zlib/zip decompression
filter in `contrib/pgcrypto/pgp-compress.c` (`decompress_read`, the per-chunk
inflate driver). A new `uint64 total_out` field on `DecomprData` accumulates
output bytes after each `inflate()` call; if the running total exceeds
`MaxAllocSize`, the function returns a new error code
`PXE_PGP_OUTPUT_LIMIT_EXCEEDED -124` mapped through `px.c`'s error table to
the string `"Decompressed output exceeds maximum allowed size"`.

Touches 3 files in `contrib/pgcrypto/`:
- `pgp-compress.c` (+8 LOC, including comment) — the cap logic + new include of
  `utils/memutils.h` for `MaxAllocSize`.
- `px.c` (+1 LOC) — error-table row.
- `px.h` (+1 LOC) — error-code define.

Behavior: any small OpenPGP blob whose decompressed form would exceed
`MaxAllocSize` now errors out via `pgp_sym_decrypt` / `pgp_pub_decrypt` early
instead of running inflate to completion and tripping the `bytea`/`text`
aggregator's own check. No regression test added (per COVER §3 — binary
fixture not included).

## 2. Predicted reviewers

Mined from `knowledge/personas/domain-ownership.md` cross-cut + actual
24-month commit/trailer history of `contrib/pgcrypto/` (via
`/usr/bin/git log -- contrib/pgcrypto/` on `source` — the `rtk`
50-line cap was avoided per the Phase B gotcha).

| Rank | Reviewer | Why they would review | Persona |
|---|---|---|---|
| 1 | Daniel Gustafsson | De-facto pgcrypto maintainer. 7 of the most recent ~15 substantive pgcrypto commits in 24mo are his (AES CFB mode, FIPS-mode check, disabling built-in crypto). The patch will land via him unless he punts. | `knowledge/personas/daniel-gustafsson.md` |
| 2 | Tom Lane | Universal reviewer. Two recent pgcrypto commits in 24mo (memory-leak fix in `px_crypt_shacrypt`, SHA-2 expected-files for FIPS OpenSSL) — he both reads and pushes pgcrypto code. Style + ABI reviewer for any patch that touches a public-ish API. | `knowledge/personas/tom-lane.md` |
| 3 | Michael Paquier | Recent pgcrypto contributor (`pgcrypto: Tweak error message for incorrect session key length`, `pgcrypto: Fix buffer overflow in pgp_pub_decrypt_bytea()`). Error-table editing is exactly the kind of small contrib touch he commits frequently. | `knowledge/personas/michael-paquier.md` |
| 4 | Noah Misch | Security-focused reviewer; landed `Require PGP-decrypted text to pass encoding validation` and `Fix test "NUL byte in text decrypt" for --without-zlib builds` — the second tells you he specifically tracks pgcrypto's zlib path. The exact area this patch touches. No persona file (`knowledge/personas/noah-misch.md` not yet written); use `committer-map.md` row instead. | (no persona — see §6 follow-up) |
| 5 | Peter Eisentraut | Frequent pgcrypto cleanup pusher (anonymous unions, useless-cast removal, `pg_noreturn`). Unlikely to engage on a security-fix shape, but if he does it will be a style/include-discipline comment. | `knowledge/personas/peter-eisentraut.md` |

## 3. Predicted review feedback, per reviewer

### Daniel Gustafsson (most-likely landing committer)

Driven by `daniel-gustafsson.md` "What to expect" bullets:

- **errorhandling discipline on compression / IO paths.** "The cap is structurally correct" (COVER §3) is not enough on a compression path. Expect: *"What happens to `dec->stream` when we return `PXE_PGP_OUTPUT_LIMIT_EXCEEDED` from inside `decompress_read`? `inflateEnd()` is called only via the `Z_STREAM_END` branch and the `eof` path in `decompress_free`. Is the early return safe re. resource ownership?"* Verifying: `pgp-compress.c:296-308` in the patch returns from inside the `restart:` block before reaching the `Z_STREAM_END` branch — the cleanup runs at `decompress_free` time via the pgp filter teardown, which is fine, but Daniel will ask the question explicitly.
- **History of the API spelled out.** Expect: *"Cite the prior pgcrypto error-table additions in the commit message — e.g. `PXE_PGP_MULTIPLE_SUBKEYS -123`'s commit — so the numbering choice is auditable."* COVER does not name a predecessor SHA.
- **Test module expected for new infra.** This is a security fix, not new infra, so this bullet partly relaxes. But the COVER §3 self-admission "No regression test" will be challenged: *"Even without a true bomb fixture, we can fold a regression case that asserts `pgp_sym_decrypt` returns the new error string on a hand-crafted blob whose `total_out` we control at the boundary. Worth ~50 LOC of base64."* Likely a soft block: he wants the test, not necessarily the bomb fixture.
- **errorhandling — the `px_debug` line.** `px_debug("decompress_read: output exceeds MaxAllocSize");` will probably be flagged as inconsistent with the surrounding style — most adjacent `px_debug` calls include a format string with a value. Soft nit, not blocker.

### Tom Lane

Driven by `tom-lane.md`:

- **He will rewrite the commit message.** Likely outcome: the body will be shortened, the "Reported in postgres-claude corpus sweep A11" reference will be dropped (he tends to scrub external-tool references from upstream messages), and a `Discussion:` URL will be required. Submit with the URL pre-attached.
- **API/ABI back-compatibility on `px.h`.** `px.h` defines public-ish error constants; adding `-124` extends a numbering convention but does not break existing callers. Tom will check that no third-party extension keys on the *count* of constants (none do — they're `#define`d, not enumerated). Expect: *"OK on ABI."*
- **Backpatch implications.** COVER §4 already says "v16, v17, v18 share pgp-compress.c verbatim — yes." Tom will verify the file actually is verbatim across branches and probably commit a unified back-patch. Confidence: high — this is exactly the kind of small DoS fix he back-patches.
- **`uint64` vs `Size`.** Tom is fussy about width types in the storage and memory layers. The `uint64 total_out` choice is arguably correct (zlib's `inflate` total is conceptually unbounded), but expect: *"Why not `Size`? Or, since we compare against `MaxAllocSize`, comparing a `Size` to a `Size` is the natural shape."* Soft style nit; doesn't change behavior.
- **Hashability / typecache / cache-invalidation.** Not applicable to this patch — pure compression-path code, no operator-class touch.

### Michael Paquier

Driven by `michael-paquier.md`:

- **He may commit it (high baseline rate).** If Daniel punts, Michael is the next-most-likely landing committer for a small contrib patch.
- **`Discussion:` URL.** Confidence very high — 98% of his commits cite one. Patch will be returned if it lands in his queue without a thread URL.
- **Subject re-tag.** Expect the landing subject `pgcrypto: cap decompressed output at MaxAllocSize` — submit with that prefix to avoid the rewrite. COVER §subject already does this; good.
- **Test coverage.** Like Daniel he will flag the missing test. *"Can we add at least one regression case using a fixture small enough for the suite?"*
- **Trailer block.** Submit with `Reported-by: postgres-claude/A11` and any `Reviewed-by` you have (none yet — first send). Michael will add reviewer trailers as they come in.

### Noah Misch (no persona file)

Inferred from `committer-map.md` row + observed pgcrypto commits:

- **Encoding-validation reflex.** His `Require PGP-decrypted text to pass encoding validation` patch makes him the most likely reviewer to ask: *"Does the cap interact with the encoding-validation pass? After we error early, do we still run pg_verify_mbstr on a partial buffer? Confirm the cleanup path is reached on the error return."* — i.e. a request to trace the error propagation up to `pgp_sym_decrypt`/`pgp_pub_decrypt`.
- **Backpatch.** Noah does correctness backpatches frequently (inplace-update durability is his recent flagship). He will likely ask for the same v16/v17/v18 back-patch coverage Tom already implied.
- **CVE numbering.** This is a DoS fix on a public SQL API. Noah may ask: *"Has security@ been pre-notified? Should this go through the embargo path instead of pgsql-hackers?"* — important question, but COVER does not address it.

### Peter Eisentraut

- **Include discipline.** The patch adds `#include "utils/memutils.h"` to `pgp-compress.c`. Peter has multiple recent commits removing unused includes from contrib (`Remove unused #include's from contrib, pl, test .c files`). Expect: *"Is `MaxAllocSize` the only thing from `memutils.h` we now need? Confirm we're not pulling in transitive headers we don't use."* Soft nit.

## 4. Generic pipeline output (what `pg-patch-review` would catch unaided)

Synthesized from the current `pg-patch-review` SKILL + `review-checklist`
SKILL applied to this patch shape. (Not actually executed — the skills are
applied mentally for the gap analysis. Phase C's first real-execution pass
will happen on the second calibrated patch, CB7.)

Generic-pipeline findings:

1. **Test coverage gap.** "Patch changes behavior but adds no regression test. Add a SQL regression case asserting the new error path." (Matches both Daniel + Michael predicted comments.)
2. **Commit-message hygiene.** "Body cites `knowledge/issues/pgcrypto.md`; verify this is acceptable in upstream submission or drop it." (Partial match to Tom's predicted rewrite.)
3. **`Discussion:` trailer missing.** "Patch needs a pgsql-hackers thread URL." (Matches both Tom + Michael.)
4. **New error code numbering.** "Verify `-124` is the next free number in `px.h`." (Mechanical; not a real reviewer comment.)
5. **`#include "utils/memutils.h"` added.** "Confirm the include is needed for `MaxAllocSize` and nothing else." (Matches Peter's predicted nit.)
6. **Backpatch question.** "Confirm v16/v17/v18 file identity before back-patching." (Matches Tom's predicted bullet.)

The generic pipeline does NOT catch:

- The resource-ownership / `inflateEnd` cleanup question (Daniel #1).
- The `uint64` vs `Size` width nit (Tom #4).
- The encoding-validation interaction (Noah).
- The CVE-embargo question (Noah).
- The `px_debug` style nit (Daniel #4).
- The cite-the-predecessor-SHA convention (Daniel #2).

## 5. Gap analysis

| Predicted comment | Covered by §4? | Why missed |
|---|---|---|
| Cleanup safety on early return from `restart:` | ❌ | The generic pipeline doesn't load subsystem-specific cleanup conventions for compression filters. This is a `pgcrypto.md` subsystem-invariant, not a generic checklist item. |
| Width-type choice `uint64` vs `Size` | ❌ | `review-checklist` has no width-type rule; it's a Tom-Lane-specific reflex from his memory-layer work. |
| Encoding-validation interaction | ❌ | This is a specific cross-cut between two pgcrypto patches (the bomb fix and Noah's prior encoding patch). No skill currently links them. |
| CVE embargo / security@ disclosure | ❌ | Major omission — the generic pipeline assumes all patches go to pgsql-hackers, but DoS-on-public-API patches may warrant `security@` first. |
| `px_debug` style nit | ❌ | Subsystem-local style, not a global rule. |
| Cite predecessor SHA for new error codes | ❌ | Convention specific to error-table additions. |
| Cleanup test for `decompress_free` invariant under early error | ❌ | Subsystem-local invariant. |

The conserved finding (test coverage / `Discussion:` / backpatch / include
hygiene) is what the generic pipeline already produces. **The misses are
all subsystem-specific reflexes that live in personas.**

## 6. Recommended skill edits

Proposals to feed into the consolidated gap catalog at end of Phase C.
Each is tagged with the persona+bullet that drives it.

1. **Add a "subsystem cleanup-on-error" check** to `pg-patch-review`:
   for any patch that adds an early `return` inside a function that owns
   a `z_stream`, `BufFile`, `FileFd`, `MemoryContext`, or similar
   resource handle, surface a "trace cleanup path under the new error
   return" finding. Driver: `daniel-gustafsson.md` "errorhandling
   discipline on compression / IO paths."
2. **Add a "security@ embargo" gate** to `review-checklist`: when the
   patch description mentions DoS, denial-of-service, decompression
   bomb, integer overflow, or buffer overflow AND the patch touches a
   `pg_*_decrypt`, `pg_read_*`, `COPY`, or other public SQL API, ask
   the author to confirm `security@postgresql.org` has been notified
   first. Driver: inferred Noah Misch reflex (no persona yet — see
   follow-up #1 below).
3. **Add a "subsystem error-table predecessor cite" hint** to
   `pg-patch-review`: when a patch adds a `#define` to a contrib's
   error-table header (`contrib/*/px.h`, `contrib/*/errors.h`, etc.),
   suggest the commit message cite the SHA of the previously-added
   constant. Driver: `daniel-gustafsson.md` "History of the API
   spelled out."
4. **Add a "subsystem-style debug-line consistency" check**: when a
   patch adds a `px_debug(...)`, `elog(DEBUG2, ...)`, or similar to a
   contrib subsystem, compare its format against the surrounding
   convention in the same file. Driver: `daniel-gustafsson.md`
   inferred — soft nit, but pgcrypto specifically uses
   `px_debug` consistently with a format value.

### Follow-ups (not skill edits, but Phase B holes surfaced by this run)

1. **Noah Misch persona missing.** He's clearly a top-tier reviewer
   for security/durability/correctness patches; his Phase B persona
   should be written before calibrating CB7 (ltree amplification) or
   SP2 (pg_strlower size cap), both of which would route to him. File
   a `hf(corpus)` PR.
2. **Per-subsystem invariant index missing.** The cleanup-on-early-return
   question is a subsystem-invariant that should live in
   `knowledge/subsystems/contrib-pgcrypto.md` (or its parent). No such
   doc currently exists — `knowledge/subsystems/` only documents
   backend subsystems, not contrib modules. This is a Phase C/B
   structural gap; raise it after the 5 calibrations.

## Notes

- **Resource-ownership claim verified.** Spot-check at `source/contrib/pgcrypto/pgp-compress.c`: the early return inside `restart:` (lines 285-308 in the patched file) leaves cleanup to `decompress_free`, which is invoked unconditionally by the outer pgp filter machinery on stream teardown. So Daniel's predicted question has a satisfying answer; the COVER message should pre-empt it.
- **`-124` predecessor.** Last error code in `px.h` is `PXE_PGP_MULTIPLE_SUBKEYS -123`. Originating commit findable via `git log -S 'PXE_PGP_MULTIPLE_SUBKEYS' -- contrib/pgcrypto/px.h` — pre-resolve this SHA when refining the COVER for Phase D.
- **CVE embargo question.** Genuinely unresolved. Defer to user when Phase D resumes — the call to bypass `security@` should be explicit and informed, not implicit.

## Cross-references

- `patches/cb1-pgcrypto-bomb/COVER.md` — patch description (current).
- `knowledge/issues/pgcrypto.md` — the original A11-sweep finding that motivated this patch.
- `knowledge/personas/domain-ownership.md` — owner table consulted for §2.
- `knowledge/personas/daniel-gustafsson.md`, `tom-lane.md`, `michael-paquier.md`, `peter-eisentraut.md` — driver personas for §3.
- `knowledge/calibration/README.md` — the methodology this doc instantiates.
