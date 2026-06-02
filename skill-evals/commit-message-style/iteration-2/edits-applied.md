# Edits applied for iteration 2

Iteration-1 proposed 5 edits; I applied 3 and dropped 2 after verification.

## Applied

### Edit 1 — `https://postgr.es/m/` is dominant; `http://` is rare-but-accepted
Verified by `git log --format='%b' -100 | grep -iE '^Discussion:'`:
  - 93 `https://`
  - 2 `http://`
SKILL.md §4 Notes updated.

### Edit 2 — Omit `Author:` when committer is sole author
Verified by reading `08127c641c0` (full body shown — committer was sole
author, no `Author:` line, just `Reported-by:` / `Reviewed-by:` ×2 /
`Discussion:` / `Backpatch-through:`).
SKILL.md §4 Notes updated with explicit bullet + verified-by-code cite.

### Edit 4 — Backpatch-through good/bad inline examples
Verified by `grep -E '^Backpatch-through:' git log -200` — 63 instances,
all bare-version (e.g. `Backpatch-through: 14`, `18`); no range form
in recent history.
SKILL.md §4 Backpatch-through bullet updated.

### Edit 5 — Clarify `Co-authored-by:` vs `Author:`
SKILL.md §4 table row reworded.

## Dropped after verification

### Edit 3 — "Two spaces after sentence-ending period"
Initially proposed because `db5ed03217b` body uses two spaces. But
`08127c641c0` body uses single space ("commit. The", "validation. (").
Wider check in recent 50 commits: 32 two-space vs 41 one-space —
**not a house-style rule**, just per-committer preference. Dropped.

### (no Edit 6)

## Net effect
Three small precision additions, none of which change the answers
on the existing 3 evals (those were already 21/21) — they tighten
edge cases (sole-author commits, URL scheme, BP format strictness).
