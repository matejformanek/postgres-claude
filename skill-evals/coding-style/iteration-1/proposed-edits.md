# Proposed edits to SKILL.md — iteration 1 (NOT applied)

Baseline already scores 82% on this skill (PG style is well-represented in training data). The skill earns its keep on operational mechanics, not on re-teaching well-known rules. Edits below are minimal — targeted at gaps observed during grading.

## Edit 1: Add `errcode_for_file_access()` / `errcode_for_socket_access()` to the error-message section

**Why:** Eval-3 graded baseline higher than with-skill on the "appropriate SQLSTATE family" assertion. The skill mentions `errcode(ERRCODE_*)` but never names the two `errcode_for_*` helpers that handle the common cases (file I/O, socket I/O) correctly without the author guessing the right SQLSTATE.

**Where:** In the "Error message style" section, add a one-liner.

**Proposed addition:**
> For file/socket failures, prefer `errcode_for_file_access()` / `errcode_for_socket_access()` — they pick the right `ERRCODE_*` from `errno` so you don't have to.

## Edit 2: Add a one-liner that `ereport(ERROR, …)` makes following `pfree`/cleanup unreachable AND unnecessary

**Why:** Eval-3 graded baseline higher than with-skill on the "memory-context cleanup makes pfree unnecessary" assertion. The skill currently says `ereport(ERROR, …)` does not return — true, but it doesn't connect that to "don't bother with cleanup, the abort path handles it." That's the *useful* corollary.

**Where:** Hard rule #5 (errors via ereport).

**Proposed addition:** after the existing "never write code after it" sentence:
> Memory and resource cleanup is unnecessary — `AbortTransaction()` releases the per-query memory context, locks, buffers, and open file descriptors.

## Edit 3: Spell out the `for (int i = …)` corollary of the no-mid-block-decls rule

**Why:** Eval-1 graded baseline at 0.5 on the `for (int i = …)` assertion because it's an easy thing for a C developer to assume is fine (C99 allows it). The skill says "No declarations interleaved with statements" but doesn't call out the for-loop case explicitly. Modern C dev habit will trip on this.

**Where:** Hard rule #3 (C99 subset).

**Proposed change:**
- Current: `No declarations interleaved with statements (declare locals at the top of the block before any statement)`
- New: `No declarations interleaved with statements — declare locals at the top of the block before any statement. This includes `for (int i = 0; …)` — declare `i` at the top of the enclosing block.`

## Edit 4 (optional / low-priority): Cross-link headerscheck/cpluspluscheck to the build skill

**Why:** Eval-1 baseline missed the headerscheck/cpluspluscheck requirements entirely. The skill mentions them in passing under hard rule #2. Could be slightly more prominent — but this is minor and the current placement is fine.

**No edit proposed — current coverage is adequate.**

## Edits NOT to make

- Don't expand the naming-conventions table further. Baseline gets this fine; verbosity would dilute the operational rules.
- Don't add more verified-by-code citations. The skill is operational; the long-form `knowledge/conventions/coding-style.md` is where citations live, and the skill already points to it.
- Don't add error-handling depth (severity-level table, etc.). There's a separate `error-handling` skill for that, and the skill already cross-links to it.
