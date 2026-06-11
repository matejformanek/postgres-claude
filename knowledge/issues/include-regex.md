# Issues — `src/include/regex/`

Per-subdirectory issue register for the Henry-Spencer regex engine
headers (public API, customization layer, internal guts, NFA
exporter, error-string table). Many bullets reflect upstream-
Spencer baggage that PG inherits.

**Parent docs:** `knowledge/files/src/include/regex/*.md`.

## Open / Triaged

| Date | File:line | Type | Severity | Summary | Status | Linked doc |
|---|---|---|---|---|---|---|
| 2026-06-11 | src/include/regex/regex.h:126 | correctness | maybe | `pg_regoff_t = long` is 32-bit on Win64 — silent 2 GB match-offset cap | open | files/.../regex.h.md |
| 2026-06-11 | src/include/regex/regex.h:143 | doc-drift | nit | "REG_UPBOTCH: legal per spec, but that was a mistake" — POSIX quirk note buried | open | files/.../regex.h.md |
| 2026-06-11 | src/include/regex/regex.h:195-197,207-209 | stale-todo | nit | Six "none of your business" debug flag bits inherited from upstream Spencer | open | files/.../regex.h.md |
| 2026-06-11 | src/include/regex/regerrs.h:50-58 | doc-drift | nit | Error-code numbering skips 14 with no explanation in this file | open | files/.../regerrs.h.md |
| 2026-06-11 | src/include/regex/regerrs.h:14 | stale-todo | nit | "REG_BADPAT" string contains literal "(reg version 0.8)" — Spencer-era version | open | files/.../regerrs.h.md |
| 2026-06-11 | src/include/regex/regcustom.h:73-86 | stale-todo | likely | "REALLOC_ARRAY: XXX this definition does not provide the desired overflow check" — long-standing TODO (PG override avoids it via repalloc_array_extended, but the fallback in regguts.h has it) | open | files/.../regcustom.h.md, .../regguts.h.md |
| 2026-06-11 | src/include/regex/regcustom.h:79-81 | undocumented-invariant | nit | `CHR_IS_IN_RANGE` macro reserves the right to multi-evaluate its argument | open | files/.../regcustom.h.md |
| 2026-06-11 | src/include/regex/regcustom.h:62-70 | undocumented-invariant | maybe | `CHR_MAX = 0x7ffffffe` requires `pg_wchar` to remain unsigned int-wide | open | files/.../regcustom.h.md |
| 2026-06-11 | src/include/regex/regexport.h:34-35 | undocumented-invariant | likely | `COLOR_WHITE` / `COLOR_RAINBOW` duplicated between regexport.h and regguts.h with "must match" comment | open | files/.../regexport.h.md, .../regguts.h.md |
| 2026-06-11 | src/include/regex/regexport.h:50-52 | doc-drift | nit | Bounded-buffer getters (`pg_reg_getoutarcs`, `pg_reg_getcharacters`) — silent-truncation behavior not in header | open | files/.../regexport.h.md |
| 2026-06-11 | src/include/regex/regguts.h:494-509 | undocumented-invariant | maybe | `subre.flags` is a `char` and must stay signed-char-safe (no flag bit ≥ 0x80) | open | files/.../regguts.h.md |
| 2026-06-11 | src/include/regex/regguts.h:463-466 | question | maybe | `REG_MAX_COMPILE_SPACE` accounts for states+arcs only; pathological cvec growth not charged | open | files/.../regguts.h.md |
| 2026-06-11 | src/include/regex/regguts.h:421-422 | undocumented-invariant | nit | "HASCANTMATCH appears in nfa structs' flags, but never in cnfas" — compaction-time invariant | open | files/.../regguts.h.md |
| 2026-06-11 | src/include/regex/regguts.h:536-537 | question | nit | `STACK_TOO_DEEP` indirect-call-via-fns — is the indirection still load-bearing? | open | files/.../regguts.h.md |

## Wontfix / Submitted / Landed

(empty)

## Notes

- The COLOR constant duplication between `regexport.h` and
  `regguts.h` is the single most reviewer-trap-prone bit of this
  subsystem. Patches that touch one must `grep -r COLOR_WHITE`.
- `pg_regoff_t = long` on Win64 is a 30-year-old bug carried over
  from POSIX. Real-world impact bounded by `MaxAllocSize` (1 GB),
  so 2 GB cap is moot — but a patch that widens text-internal
  representations could surface it.
- Most "issues" in this subdir are upstream-Spencer stylistic
  artifacts; the only material reliability concerns are the
  COLOR duplication and the bitfield/`char`-signedness
  considerations.
