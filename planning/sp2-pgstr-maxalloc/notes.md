# SP2 implementation notes

## Phase 1 — implementation (single phase per R3)

**Status:** done.
**Commit:** `7e837854a65 Cap input size for pg_strlower/upper/title/fold to MaxAllocSize/3` (in `dev/` branch `feature_sp2_pgstr_maxalloc`)
**Test scope:** `meson test --suite regress` — 245/245 subtests pass (no behavior change for normal-size inputs).
**Broader test:** `meson test --no-rebuild` — 99 OK, 1 unrelated pre-existing ecpg flake (same one SP6/SP7 saw).

### What changed

One file in `dev/`:

1. **`src/backend/utils/adt/pg_locale.c`** — added `PG_STR_CASEMAP_MAX_SRCLEN` macro (`(MaxAllocSize - 1) / 3`), static-inline `check_str_casemap_srclen()` helper, and 4 single-line call sites at the top of `pg_strlower` / `pg_strtitle` / `pg_strupper` / `pg_strfold`. +26 LOC net.

### Surprises / drift

1. **Worktree dev/ shares one underlying repo.** When I `git checkout`-ed the SP2 branch in `dev/`, the SP6 worktree's `dev/` view changed too (both worktrees mount the same `postgresql-dev` tree). The SP6 work is preserved as a commit (`acd8c00fb96`) — branch ref intact — but the working-tree files reflect whichever branch is checked out. This is a known limit of the symlinked dev/ approach. Worth canonizing somewhere in the worktree-workflow rule: **"the dev/ branch is global across worktrees; only one Phase-D branch can have its files staged at a time."**

2. **LSP diagnostics fired on the unmodified parts of pg_locale.c.** The IDE's clang-LSP complained about `'postgres.h' file not found` and unknown types `pg_locale_t`, `Oid`, `MemoryContext` — all on lines I didn't touch. These are LSP-environment include-path issues (the LSP doesn't know about meson's include flags), not actual build errors. The meson build itself completed without any errors on the modified file.

3. **The cap is conservative for the C/POSIX path.** `check_str_casemap_srclen` fires before the `locale->ctype == NULL` branch — but ASCII case mapping is 1:1, so a stricter bound could be allowed there. Decided against splitting: one uniform limit keeps the code readable, and an operator hitting 357 MB on the C-locale path probably doesn't want their query to succeed in 1 GB output either.

4. **No regression test added.** A test that exercises the cap requires > 357 MB input, which would dominate buildfarm time + memory. The cap is straightforward defense-in-depth and the 3× ICU bound is a documented contract. Mentioned in commit message + this notes file so reviewers see the intent.

### What this phase did NOT do

- Did NOT touch `formatting.c` (the 4 caller sites at `str_tolower` / `str_toupper` / `str_initcap` / `str_casefold`). Decided header-layer cap is cleaner — protects ltree's `pg_strfold` callers too.
- Did NOT add a `PG_TEST_EXTRA=stress`-gated regression test exercising the cap. Worth a follow-up if hackers want one.
- Did NOT touch `pg_downcase_ident` (identifier downcasing path). Different shape, has its own `NAMEDATALEN`-bounded surface.
- Did NOT touch `contrib/ltree` directly. The cap inside `pg_strfold` covers ltree's callers for free.

### Submission readiness

- `format-patch` ready: `git format-patch e18b0cb7344..feature_sp2_pgstr_maxalloc --output-directory ../sp2-pgstr-maxalloc/`
- Patch subject: `Cap input size for pg_strlower/upper/title/fold to MaxAllocSize/3`
- Backpatch candidates: yes (defensive cap, no behavior change for normal inputs). v16, v17, v18 all share the same case-mapping primitives with no cap.
- CF target: 60 (January 2026).

### End-of-implementation gate (R12)

- [x] Full `meson test --no-rebuild` — 99 OK, 1 unrelated pre-existing ecpg flake
- [x] `git log --oneline e18b0cb7344..HEAD` shows exactly 1 commit
- [x] Commit message in upstream PG style (no Co-Authored-By, no Plan: trailer per R5's upstream exemption)
- [ ] Upstream-bound: needs `review-checklist` + `patch-submission` skills. NEXT STEP.
- [x] Local branch ready for review

### Next step

Same gate as SP7 + SP6: stage in a PR for user review before format-patch submission. Three Phase D quick-wins now queued side-by-side (SP7, SP6, SP2).
