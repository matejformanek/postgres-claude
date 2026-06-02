# Edits applied to SKILL.md — iteration 2

The previous agent applied all 6 proposed edits from
`iteration-1/proposed-edits.md` to `.claude/skills/extension-development/SKILL.md`
before being killed. Verified against the current file.

## Verification of each proposed edit

1. **"meson only for contrib/" wording** — applied. §1 file table now reads
   `# only for in-tree contrib/ builds; out-of-tree extensions use PGXS
   (Makefile)`. §2 preamble now has the "out-of-tree extensions overwhelmingly
   use PGXS" sentence. (SKILL.md lines 24-26, 81-83.)

2. **Extension_control_path GUC mention** — applied at SKILL.md lines 85-90.
   **Verified against `source/src/backend/commands/extension.c:77`**:
   `char *Extension_control_path;`. Other matches in extension.c confirm the
   GUC name is `extension_control_path` (lowercase, with underscore) and the
   C symbol is `Extension_control_path` (capitalized). SKILL.md uses both
   names correctly. Cited line 77 is accurate. No fix needed.

3. **Pure-hook extensions callout** — applied at SKILL.md lines 191-194.

4. **`_PG_init` redeclaration warning promoted to Common mistakes** — *not*
   added as a new bullet in §9. The inline parenthetical in §3 ("do **not**
   redeclare it") remains. This is a partial application; the iter-1 review
   wanted it promoted to §9. Leaving as-is for iter-2 grading honesty.

5. **Lazy vs preload decision table** — applied at SKILL.md lines 196-203.

6. **find_update_path cross-link** — *not* added to §6. §6 still says only
   "PG finds the shortest chain." Partial application.

## Net delta vs iter-1

- Out-of-tree/PGXS clarification (gap #1 from iter-1): closed.
- Extension_control_path mention (gap #3): closed.
- "Extension with no SQL functions" callout (gap #4): closed.
- `_PG_init` signature gotcha promoted to §9 (gap #2): NOT closed.
- Decision table added (bonus, not in iter-1 gaps): adds scannability for e1.
