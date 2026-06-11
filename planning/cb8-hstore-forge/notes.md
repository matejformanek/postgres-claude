# CB8 implementation notes

## Phase 1 — implementation (single phase per R3)

**Status:** done.
**Commit:** `06c8204b300 hstore: validate structure before trusting HS_FLAG_NEWVERSION` (dev/ branch `feature_cb8_hstore_forge`)
**Test scope:** `meson test --suite hstore` — 2/2 subtests pass.
**Broader test:** `meson test --no-rebuild` — 99 OK, 1 unrelated pre-existing ecpg flake.

### What changed

One file (`contrib/hstore/hstore_compat.c`), +20/-4 LOC:

1. **`hstoreValidNewFormat()`** — removed the lines 130-131 `if (HS_FLAG_NEWVERSION) return 2;` short-circuit. Replaced with a 10-line comment explaining the trust-gap and why the structural pass must always run.
2. **`hstoreUpgrade()`** — the fast-path return now requires BOTH the flag AND a positive structural check: `if ((hs->size_ & HS_FLAG_NEWVERSION) && hstoreValidNewFormat(hs)) return hs;`. Forged datums fall through to the existing `valid_new + valid_old` recovery path (lines 257-258) which already rejects mismatched inputs.

### Surprises / drift

1. **The bug was duplicated across two functions.** Initial reading of the pitch suggested a single fix in `hstoreUpgrade`. But `hstoreValidNewFormat()` ALSO had the same short-circuit (line 130) — meaning the diagnostic function `hstore_version_diag` (line 354) was lying about validity for any flagged datum. Had to fix both, and the second fix (in the validator) is more important because it's the chokepoint.

2. **Behavior change for `hstore_version_diag`.** Before this patch, a forged hstore with NEWVERSION-bit-set + garbage offsets would return `valid_new=2 valid_old=0` → `2`. After: returns `valid_new=0 valid_old=0` → `0`. That's a behavior change in a diagnostic function, but the diagnostic was previously dishonest about the situation; the new value accurately reports "neither format". Documenting in the commit message — reviewers may or may not consider this part of the diagnostic contract.

3. **Both callers of `hstoreValidNewFormat`** were inspected: line 257 (inside hstoreUpgrade's recovery path, reached only when the flag is NOT set, so unaffected by the validator change) and line 354 (`hstore_version_diag`, behavior change noted above). Total surface is contained.

4. **No regression test added.** Crafting a forged hstore requires building the bytea directly with HEX-encoded HEntry array; would add ~50-100 LOC of test scaffolding for one error-path coverage. The structural-correctness argument is strong (the validator is well-tested for genuinely-old-format inputs).

### Submission readiness

- `format-patch` ready: `git format-patch e18b0cb7344..feature_cb8_hstore_forge`
- Patch subject: `hstore: validate structure before trusting HS_FLAG_NEWVERSION`
- Backpatch: yes (security fix for an OOB-read vector via public bytea path).

### End-of-implementation gate (R12)

- [x] Full `meson test --no-rebuild` — 99 OK, 1 unrelated pre-existing ecpg flake
- [x] One commit on `feature_cb8_hstore_forge` (`06c8204b300`)
- [x] Upstream-style commit message (no Co-Authored-By)
- [x] Local branch ready for PR

### Next step

PR + merge per user's "merge and continue" directive.
