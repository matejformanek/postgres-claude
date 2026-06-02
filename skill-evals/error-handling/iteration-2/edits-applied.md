# Iteration 2 — edits applied to SKILL.md

All 5 proposed edits from `iteration-1/proposed-edits.md` were applied verbatim.

## Verification of load-bearing values

| Value | Claim | Verified | Source |
|---|---|---|---|
| `ERRORDATA_STACK_SIZE` value 5 | "5-frame stack" | yes | `source/src/backend/utils/error/elog.c:154` — `#define ERRORDATA_STACK_SIZE 5` |
| `ERRORDATA_STACK_SIZE` location `elog.c:154` | file:line cite | yes | same grep above, hits line 154 exactly |
| `PG_ENSURE_ERROR_CLEANUP` in `storage/ipc.h` | (already in SKILL.md, edit 2 doesn't touch) | yes | `source/src/include/storage/ipc.h:47` |
| `OpenTransientFile()` exists, registers fd | edit 2 claim | yes | `source/src/include/storage/fd.h:177` — `extern int OpenTransientFile(...)`; fd.h:36 comment confirms ResourceOwner semantics |
| `%m` is canonical errno format specifier | edit 1 + 5 | yes | widespread in backend (e.g. ~thousands of call sites) |

No values needed correction; all five edits applied verbatim.

## Edits applied

1. Edit 1 — added `%m` guidance after `errcode_for_file_access()` bullet (rule 2).
2. Edit 2 — added `OpenTransientFile()` note to the "ereport(ERROR) does not return" section.
3. Edit 3 — strengthened `PG_FINALLY` over `PG_CATCH` from one bullet to a "Prefer" paragraph.
4. Edit 4 — added `ERRORDATA_STACK_SIZE` name and `elog.c:154` cite to the 5-frame note.
5. Edit 5 — added rule 9, errno clobbering warning.
