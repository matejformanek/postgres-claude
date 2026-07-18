---
source_url: https://www.postgresql.org/docs/current/textsearch-limitations.html
fetched_at: 2026-07-17T20:58:00Z
anchor_sha: 5174d157a038
distilled_by: pg-docs-miner (cloud routine)
docs_version: current (PG18)
section: "12.11 Limitations"
maps_to_skill: [type-cache, toast-storage, gin]
---

# Docs distilled — textsearch-limitations (the FTS hard limits, code-verified)

The FTS hard limits are not arbitrary — every one is a bit-field width in the
`tsvector`/`tsquery` on-disk layout (`src/include/tsearch/ts_type.h`). This doc
pins each stated limit to the struct field that enforces it, and flags two
places where the prose has drifted from the code.

## Non-obvious claims (docs limit → enforcing code)

- **Lexeme length < 2 KB.** The `WordEntry.len` field is **11 bits**
  (`len:11, /* MAX 2Kb */` [[ts_type.h:45]]) so `MAXSTRLEN = (1<<11)-1` = **2047
  bytes** [[ts_type.h:49]]. [verified-by-code @ 5174d157a038]
- **`tsvector` size < 1 MB.** The `WordEntry.pos` field (byte-offset of the
  lexeme string from the end of the WordEntry array) is **20 bits**
  (`pos:20, /* MAX 1Mb */` [[ts_type.h:46]]) so `MAXSTRPOS = (1<<20)-1`
  [[ts_type.h:50]]. This offset width is the real cap on total lexeme-string
  bytes. [verified-by-code @ 5174d157a038]
- **Position value 1..16,383.** A `WordEntryPos` is `weight:2, pos:14`
  [[ts_type.h:58]]; the position mask is `WEP_GETPOS(x) = (x) & 0x3fff`
  [[ts_type.h:80]] (14 bits). Positions past `MAXENTRYPOS = (1<<14)` = 16384 are
  clamped, not stored exactly: `LIMITPOS(x) = ((x) >= MAXENTRYPOS ?
  (MAXENTRYPOS-1) : (x))` [[ts_type.h:87]] — i.e. everything ≥16384 collapses to
  16383. [verified-by-code @ 5174d157a038]
- **FOLLOWED-BY `<N>` distance ≤ 16,384.** Same `MAXENTRYPOS` ceiling, enforced
  at parse time: `l > MAXENTRYPOS` raises an error [[tsquery.c:207]]. So the
  phrase-distance ceiling and the position ceiling are the *same* constant.
  [verified-by-code @ 5174d157a038]
- **≤ 256 positions per lexeme.** `MAXNUMPOS = 256` [[ts_type.h:86]]; excess
  positions for a lexeme are dropped. [verified-by-code @ 5174d157a038]

## ⚠ Two doc-vs-code drifts found this run

- **"Number of lexemes must be less than 2^64" — overstated.** The `tsvector`
  header stores the lexeme count in an **`int32 size`** field
  (`int32 size - number of lexemes (WordEntry array entries)` [[ts_type.h:24]]),
  so the structural cap is **2^31**, not 2^64. In practice the 1 MB size limit
  (the 20-bit `pos` offset) binds far earlier than either. Trust the struct:
  count is int32-bounded. [verified-by-code @ 5174d157a038] — **hf/pgsql-docs
  candidate.**
- **"Number of nodes in a `tsquery` must be less than 32,768" — stale.** The
  current enforcement macro is `TSQUERY_TOO_BIG(size, lenofoperand)` =
  `(size) > (MaxAllocSize - HDRSIZETQ - (lenofoperand)) / sizeof(QueryItem)`
  [[ts_type.h:236]], raised as "tsquery is too large" (`ERRCODE_PROGRAM_LIMIT_
  EXCEEDED`) at [[tsquery.c:890]]. With `MaxAllocSize` = 1 GB−1 and
  `sizeof(QueryItem)` = 8, the real node ceiling is on the order of **10^8**,
  not 32,768. The docs' 2^15 figure does not correspond to any constant on the
  current parse path. [verified-by-code @ 5174d157a038] — **hf/pgsql-docs
  candidate** (same drift class as the intarray-siglen and refint-removal finds
  logged 2026-07-14 / 2026-07-16).

## Links into corpus

- `[[docs-distilled/textsearch-controls.md]]` / `[[docs-distilled/textsearch-features.md]]`
  — the `<->` phrase operator and `ts_rank_cd` cover extents both live inside
  the 16,383-position window bounded here.
- `[[docs-distilled/storage-toast.md]]` — a >1 MB document can't become one
  `tsvector`; the limit interacts with TOAST since large vectors are toasted.
- `type-cache` / `toast-storage` skills — `tsvector`/`tsquery` are varlena
  types; these ceilings are their on-disk-format invariants.

## Code-vs-docs / verification notes

- Every limit above is **code-verified** at anchor `5174d157a038` via
  `raw.githubusercontent.com` against `src/include/tsearch/ts_type.h` and
  `src/backend/utils/adt/tsquery.c`. The two drifts are flagged as hf/pgsql-docs
  candidates for the corpus's doc-bug ledger; no code change is implied — the
  docs prose is what should be corrected upstream.
