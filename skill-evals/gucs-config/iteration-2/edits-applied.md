# Edits applied — iteration 2

Per-edit disposition relative to `iteration-1/proposed-edits.md`.

## Edit 1 — Tighten `MarkGUCPrefixReserved` cite — APPLIED

- Was: `[verified-by-code source/src/backend/utils/misc/guc.c:5178-5228]`
- Now: `[verified-by-code source/src/backend/utils/misc/guc.c:5185-5228]`
- Verification: Read `source/src/backend/utils/misc/guc.c:5180-5228`.
  Function header at line 5185, body 5187-5228. The header comment
  block above the function starts at 5178; tightening to 5185 makes
  the cite point at the function itself.

## Edit 2 — Tighten guc_malloc README cite + add guc_realloc — APPLIED

- Was: `[from-README source/src/backend/utils/misc/README:51-60]`,
  text mentioned only `guc_malloc / guc_strdup` / `guc_free`.
- Now: `[from-README source/src/backend/utils/misc/README:50-62]`,
  text adds `guc_realloc` with a one-line description, plus an inline
  cite `source/src/include/utils/guc.h:473-476`.
- Verification: Read `source/src/backend/utils/misc/README:45-62`.
  Lines 50-55 contain the string-replacement rule; lines 57-62 the
  extra-pointer rule. Both are needed. Read
  `source/src/include/utils/guc.h:473-476` for the four allocator
  declarations: `guc_malloc` (473), `guc_realloc` (474), `guc_strdup`
  (475), `guc_free` (476). All four verified.

## Edit 3 — Add SplitIdentifierString / SplitGUCList — APPLIED

- Added as a new bullet at the end of §6's check_hook body, where
  list-style GUCs are most naturally referenced (just above the
  assign_hook subsection).
- Verification: Read `source/src/include/utils/varlena.h:33-37`.
  `SplitIdentifierString(char *rawstring, char separator, ...)` at
  line 33 and `SplitGUCList(char *rawstring, char separator, ...)` at
  line 37. Verified.

## Edit 4 — Add guc_realloc to §5 storage-rules paragraph — APPLIED (merged with Edit 2)

Folded into Edit 2 in a single block.

## Edit 5 — Explain GUC_check_errcode default SQLSTATE — APPLIED

- Added inline gloss to the existing bullet listing the four
  `GUC_check_err*` macros: `"GUC_check_errcode(sqlerrcode) overrides
  the default rejection SQLSTATE (ERRCODE_INVALID_PARAMETER_VALUE,
  22023); only override when you have a more specific code."`
- Verification: `ERRCODE_INVALID_PARAMETER_VALUE` is widely used as
  the default rejection SQLSTATE for GUC validation throughout
  `source/src/backend/utils/misc/guc.c`; the macro definition
  resolves to `MAKE_SQLSTATE('2','2','0','2','3')` in `errcodes.h`.

## Edit 6 — Add per-type check_hook signature table — APPLIED

- Inserted at the top of §6 check_hook subsection, before the bullet
  list.
- Verification: README at lines 25-30 states *"The "newvalue"
  argument is of type bool *, int *, double *, or char ** for bool,
  int/enum, real, or string variables respectively."* Direct copy of
  the README's own enumeration. Added `[from-README
  source/src/backend/utils/misc/README:25-30]` cite to the new table.

## Edit 7 — Sub-cite README for assign + show hook contracts — APPLIED

- Added `[from-README source/src/backend/utils/misc/README:78-109]`
  under assign_hook bullet list.
- Added `[from-README source/src/backend/utils/misc/README:112-117]`
  under show_hook bullet.
- Also tightened the umbrella check_hook cite from `README:25-109` to
  `README:25-75` since the new sub-cites now cover the remainder.
- Verification: Read `source/src/backend/utils/misc/README` end-to-end.
  - Lines 25-75: check_hook contract (signature, rejection, errdetail,
    canonicalisation, derived extra, source argument, side-effect
    rule).
  - Lines 78-109: assign_hook contract (signature, can't-fail rule,
    rollback gotcha, catalog-lookup gotcha).
  - Lines 112-117: show_hook contract (signature, static-buffer note).
  All three ranges verified.

## Edits dropped

None. All seven edits applied; two (4 and 2) merged into one
edit-block in §5 for cleaner diff.

## Verified diff

```
$ git -C /Users/matej/Work/postgres/postgres-claude/.claude/worktrees/ft_meta_skill_creator_round_2 \
      diff --stat -- .claude/skills/gucs-config/SKILL.md
 .claude/skills/gucs-config/SKILL.md | 39 ++++++++++++++++++++++++++++++++-----
 1 file changed, 34 insertions(+), 5 deletions(-)
```

34 lines added, 5 modified; non-empty as required.

## Re-run note

Iter-2 with_skill: 30/30 (saturated, same as iter-1).
Iter-2 baseline: 19/30 (+1 vs iter-1's 18/30; natural baseline noise,
not a content change). The skill regressed no assertions; the new
content (signature table, SplitIdentifierString, guc_realloc,
GUC_check_errcode gloss) was used in the iter-2 with_skill answers and
held up to the same rubric without new errors.
