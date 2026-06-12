# CB1 pgcrypto decompression bomb — notes

**Patch:** `0001-pgcrypto-cap-decompressed-output-at-MaxAllocSize.patch`
**Status:** **PARKED.** Sending requires explicit user re-auth.
**Calibration:** `knowledge/calibration/cb1-pgcrypto-bomb.md`

## Predicted lead committer
**Daniel Gustafsson** (de-facto pgcrypto maintainer; 7+ recent
substantive pgcrypto commits incl. AES CFB, FIPS-mode check). Tom
Lane is the realistic backpatch-landing committer if Daniel routes
the backport.

## Gate checklist (per `review-checklist` Phase 0)

### Gate 1 — `security@` embargo
**Question:** does this need `security@postgresql.org` first?
**Answer:** **YES, ASK FIRST.** This is a confirmed DoS on a public
SQL API (`pgp_sym_decrypt` / `pgp_pub_decrypt`, any role with
EXECUTE). The cover should either say "notified security@ on
<date>" or argue the exemption. **Recommend `security@` first** —
small embargo (1-2 weeks), then send to hackers when security@
greenlights.

### Gate 2 — Test-omission skepticism
**COVER §3 says:** "No regression test. A real bomb requires a binary
fixture (~few KB compressed → tens of MB to GB decompressed)..."
**Predicted Noah response:** push for a SQL test using a small
hand-crafted blob that exercises the error path even without a true
bomb-sized payload. **Action before send**: add a regression test
that asserts the new error string on a synthetic input where the
cap is set artificially low (build flag) OR that exercises the
cap-check code path with a smaller `total_out` boundary. ~50 LOC.

### Gate 3 — Install-script immutability
Not applicable — no `--*.sql` changes.

## Patch findings to address before send

| # | Finding | Source | Resolution |
|---|---|---|---|
| 1 | Resource-ownership Q on the early `return` from `decompress_read`'s `restart:` block | cb1 calibration §Notes (Daniel reflex) | **RESOLVED** — verified at `source/contrib/pgcrypto/pgp-compress.c`: cleanup runs via `decompress_free` at filter teardown. Add a one-line comment in the new code citing this. |
| 2 | `-124` predecessor SHA citation | cb1 §3 (Daniel "API history spelled out") | Pre-resolve: `git log -S 'PXE_PGP_MULTIPLE_SUBKEYS' -- contrib/pgcrypto/px.h` → cite that commit in the body. |
| 3 | `px_debug` line format inconsistency | cb1 §3 nit | Match the surrounding `px_debug` call format (include a value). |
| 4 | `uint64` vs `Size` width choice | cb1 §3 (Tom soft nit) | Stick with `uint64` — `total_out` is conceptually unbounded from inflate's perspective, casting to `uint64` for the `MaxAllocSize` comparison is defensive and correct. Document the choice in the commit body. |

## Reviewer-style pre-emption (commit body additions)

- Cite the predecessor error-constant SHA (resolves Daniel #2).
- One-sentence note on resource ownership (resolves Daniel #1).
- One-sentence note explaining `uint64 total_out` (pre-empts Tom #4).
- Scrub the "postgres-claude/A11 corpus sweep" reference (Tom rewrites this).
- Add `Discussion:` URL once thread exists.

## Send order recommendation

**3rd in the pile.** Process: pre-empt with security@ disclosure
first; CB1 is the cleanest exemplar of the security@ gate, so
running it first via the embargo path establishes the pattern for
CB7 + CB8.

## Verdict
**GO** for embargo path. Refine COVER per the 4 findings above,
notify security@, wait for greenlight, then send.

## DO NOT SEND
This file documents the pre-send state. Sending requires:
1. Refining COVER per the 4 findings above.
2. Adding the regression test.
3. `security@postgresql.org` notification.
4. Explicit user re-auth (per Phase D parking rule).
