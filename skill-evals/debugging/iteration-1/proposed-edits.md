# Proposed edits to `.claude/skills/debugging/SKILL.md` (iteration 1)

Baseline scored 15/22 (68%) — meaningfully higher than the locking skill's baseline (48%), because gdb/lldb attach is well-known territory. The skill's marginal value is concentrated in PG-specific knobs (SIGUSR1, errfinish, pprint, macOS suppress-cores, single-user `-j`, /cores). Edits should sharpen exactly those, not reteach attaching.

## E1 — Surface the project's slash commands earlier and more visibly

**Problem.** Eval 1 baseline missed the "use the project's `/pg-attach`" cue. The SKILL.md mentions `/pg-attach` only by inference (it lives in `.claude/commands/`). A reader who doesn't already know commands exist won't find it.

**Edit.** Add a short "Project shortcuts" callout at the top of §2 (after line 28):

> In this repo, `/pg-attach` automates the PID-grab + prints the attach line, and `/pg-tail-log` follows `dev/data-debug/server.log` (where `pprint` output lands). Use them.

## E2 — Promote the SIGUSR1 silencing tip out of the gdb→lldb table

**Problem.** The SIGUSR1 advice is currently the last row of the translation table (line 61) followed by one prose sentence (lines 63–65). It's the single most useful PG-specific debugger setting and easy to miss while scanning.

**Edit.** Pull it into its own bolded sub-heading "### First command after every attach" right under the table, with the lldb form first since macOS is the project default.

## E3 — Promote `errfinish` as a top-level "catch all errors" pattern

**Problem.** `errfinish` is in the §5 breakpoint table (line 121) but its filter trick (`edata->elevel >= ERROR`) is in a parenthetical. For SIGSEGV-style debugging (eval 2), this is *the* breakpoint people want and they often don't know it exists.

**Edit.** Add a §5.1 micro-section "Trapping every error" with the explicit lldb commands:

```
(lldb) b errfinish
(lldb) br mod -c '((ErrorData *) edata)->elevel >= 20'   /* ERROR=20 */
```

(Or reference `elevel.h` constants — verify exact value before publishing.)

## E4 — Tighten the macOS cores section

**Problem.** §8 mixes `[verified-by-code]`, `[inferred]`, and "verify on your box" disclaimers in a way that undermines confidence. The Apple-signed-binary caveat (line 206–208) is correct but buried.

**Edit.** Restructure §8 as: prerequisites (numbered, with verification commands and *expected* output), then a single "Caveats" sub-section consolidating the macOS-specific gotchas. Replace "verify on your box" with concrete diagnostic: "If `sysctl kern.coredump` returns 'unknown oid', cores are controlled by ulimit alone on your macOS version."

## E5 — Add a 4-line "decision tree" near the top

**Problem.** Eval 3 baseline got the broad strokes right (single-user / -W / spin-loop) because they're well-known. What's missing is the *decision rule*. The skill has all the pieces but they're scattered across §3 and §4.

**Edit.** Insert at the top of §3:

> | Symptom | Tool |
> | ---|---|
> | Code runs *before* shared memory is attached / during InitPostgres | `postgres --single` |
> | Code runs in the forked-backend startup path (post-shmem, pre-query) | `PGOPTIONS="-W N"` |
> | Code runs in a worker (autovac / parallel / bgw) | spin-loop waitpoint |
> | Code runs during a query you can drive from psql | normal `lldb -p` attach (§2) |

## E6 — Verify and tighten line citations

A few `[verified-by-code]` cites would benefit from explicit ranges:
- §4 line 106: `xlog.c:7707, 7724` — these are 2026-current numbers; pin to commit hash in `progress/files-examined.md`.
- §3 line 80–82 / 84–86: `postgres-ref.sgml line 714+` and "around line 730" — pin exact ranges.

## E7 — Add `log_min_messages` cross-link

§7 references `.claude/skills/build-and-run/SKILL.md` line 78 for the GUC name; consider linking the corresponding `knowledge/idioms/` doc for `log_min_messages` levels (DEBUG1..DEBUG5) so readers don't have to chase the GUC docs.

## Non-edits

- The pprint section (§6) is already strong; baseline missed it entirely and with_skill got it right.
- The `gdbpg.py` non-existence note (§6 line 154–157) is exactly the kind of verified absence that prevents wasted searches. Keep.
- The "10 reproducing locking bugs" section overlaps with the locking skill but the cross-link is correct; no change.
