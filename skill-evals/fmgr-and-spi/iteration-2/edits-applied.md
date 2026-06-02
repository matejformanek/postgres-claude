# Iteration 2 — Edits applied to .claude/skills/fmgr-and-spi/SKILL.md

All five proposed edits from `iteration-1/proposed-edits.md` were applied
via the Edit tool. Verified by re-reading the touched anchors.

## 1. §1.12 → backlink to §1.9 (fn_extra owned by SRF)

Appended one paragraph after the `MyCache *c = fcinfo->flinfo->fn_extra;`
example:

> Do not use `fn_extra` in a value-per-call SRF — it is owned by
> `SRF_FIRSTCALL_INIT` (see §1.9), which uses `fn_extra == NULL` as the
> first-call test.

## 2. §2.3 → "Cached on fn_extra — the full pattern" example

Inserted after the `SPI_keepplan` paragraph and before §2.4. Shows the
combined `fn_mcxt` + `SPI_keepplan` idiom with a `typedef struct {
SPIPlanPtr plan; } MyCache;` and a one-liner explaining that missing
either half is a use-after-free on the second call.

## 3. §2.7 → "Capturing diagnostics from a failed SPI call" paragraph

Appended after the aborted-subxact rule paragraph. States explicitly:

- `SPI_tuptable` and any tuples have been freed by `AtEOSubXact_SPI`;
  touching them after rollback is use-after-free.
- `CopyErrorData()` BEFORE `FlushErrorState()`, allocated in saved
  `oldctx`, is the supported channel.
- Partial result rows must be `SPI_palloc` / `SPI_copytuple`'d out into
  `oldctx` BEFORE `ReleaseCurrentSubTransaction`.

## 4. §1.10 → MAT_SRF flags promoted to a two-row mini-table

Replaced the one-liner with a verified-by-code table:

| Flag | When to set |
|---|---|
| `MAT_SRF_USE_EXPECTED_DESC` | You want the tupdesc the caller already expects (e.g. `SELECT * FROM srf() AS (...)`). |
| `MAT_SRF_BLESS` | Return type is RECORD and needs a typmod assigned (calls `BlessTupleDesc`). |

## 5. §2.5 → name `AtEOSubXact_SPI` with pointer to §2.7

Added a parenthetical to the opening sentence:

> (The same memory-context machinery is what `AtEOSubXact_SPI` runs at
> subxact end — see §2.7.)

## Verification

All five edits applied cleanly on the first Edit-tool invocation. No
edits replaced wrong text or duplicated content.
