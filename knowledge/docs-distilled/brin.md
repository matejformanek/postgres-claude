---
source_url: https://www.postgresql.org/docs/current/brin.html
fetched_at: 2026-06-03T19:55:00Z
anchor_sha: 4b0bf0788b066a4ca1d4f959566678e44ec93422
distilled_by: pg-docs-miner (cloud routine)
docs_version: current (PG18)
primary: true
---

# Docs distilled — Chapter 71: BRIN Indexes

Block Range INdexes — the "tiny index for huge, physically-ordered tables" AM.
The non-obvious parts are the four opclass *families* and the summarization
lifecycle (BRIN does not index new data automatically).

## Structure & query behavior

- **One summary per *block range*, not per row.** A range is `pages_per_range`
  physically-adjacent pages (storage param, fixed at creation). Index entries =
  table_pages ÷ pages_per_range — so the index is kilobytes for a multi-GB
  table. [from-docs]
  [verified-by-code, source/src/backend/access/brin/brin.c +
  brin_revmap.c (range→summary map), via
  knowledge/files/src/backend/access/brin/*.md]
- **Smaller `pages_per_range` ⇒ larger index but finer skipping.** It is the
  single knob trading index size against scan precision. [from-docs]
- **BRIN is *lossy*:** it answers via a **bitmap scan** that returns *all* tuples
  in every range whose summary *might* match; the executor then **rechecks** each
  tuple and discards non-matches. So BRIN never gives wrong answers, only does
  variable amounts of recheck work. [from-docs]
- **Effective only when the column correlates with physical order** (append-only
  timestamps, monotonic ids). On randomly-ordered data every range's summary
  spans the whole domain and BRIN prunes nothing. [from-docs]

## The four opclass families

| Family | Example opclass | Per-range summary |
|---|---|---|
| **minmax** | `int8_minmax_ops` | min + max value |
| **minmax-multi** | `int8_minmax_multi_ops` | several min/max intervals (tolerates outliers) |
| **inclusion** | `box_inclusion_ops` | a bounding/including value (e.g. bounding box) |
| **bloom** | `int8_bloom_ops` | a Bloom filter (equality on uncorrelated data) |

[from-docs] [verified-by-code — one .c per family:
`brin_minmax.c`, `brin_minmax_multi.c`, `brin_inclusion.c`, `brin_bloom.c`,
via the per-file corpus docs]

- **minmax-multi** exists to survive a few outliers that would otherwise blow a
  plain minmax range wide open (`values_per_range`, 8–256, default 32). [from-docs]
- **bloom** lets BRIN answer *equality* on data that is NOT order-correlated —
  the one family that doesn't need physical correlation. Params:
  `n_distinct_per_range` (default −0.1), `false_positive_rate` (0.0001–0.25,
  default 0.01). [from-docs]

## Summarization lifecycle — the operational catch

- **New data is NOT summarized automatically.** Pages past the last summarized
  range stay unsummarized (and thus always scanned) until a VACUUM, or until
  the `autosummarize` storage param (**off by default**) is enabled, or a manual
  call. This is the classic "my BRIN index stopped helping after the table grew"
  surprise. [from-docs]
- **Manual control functions:**
  `brin_summarize_new_values(regclass)` (summarize all new ranges),
  `brin_summarize_range(regclass, bigint)` (one range),
  `brin_desummarize_range(regclass, bigint)` (drop a summary, e.g. after deletes
  widened it). [from-docs]
  [verified-by-code, via knowledge/files/src/backend/access/brin/brin.c.md]

## Opclass-author support functions

Mandatory: `opcInfo(type_oid)`, `consistent(BrinDesc*, BrinValues*, ScanKey*,
nkeys)`, `addValue(BrinDesc*, BrinValues*, Datum, isnull)`,
`unionTuples(BrinDesc*, BrinValues*, BrinValues*)`. Optional: `options`.
Support-function *numbers* are stable: SF1 opcinfo, SF2 add_value, SF3
consistent, SF4 union (e.g. `brin_minmax_opcinfo` … `brin_minmax_union`); bloom
adds SF5 options + SF11 hash; minmax-multi adds SF11 distance. [from-docs]
[verified-by-code, via knowledge/files/src/backend/access/brin/brin_validate.c.md
(opclass validation) + brin_minmax.c.md]

## Links into corpus

- [[knowledge/files/src/backend/access/brin/brin.c.md]] — AM entry points,
  summarization, the `brin_summarize_*` SQL functions.
- [[knowledge/files/src/backend/access/brin/brin_revmap.c.md]] — the
  range→summary-tuple reverse map (how a heap block finds its summary).
- [[knowledge/files/src/backend/access/brin/brin_minmax_multi.c.md]] — the
  outlier-tolerant minmax variant.
- [[knowledge/files/src/backend/access/brin/README.md]] — canonical structure
  description.
- [[knowledge/docs-distilled/indexes-types.md]] — BRIN among the six AMs.
- Skill: `access-method-apis` — implementing a BRIN opclass in C.

## Gaps / follow-ups

- The chapter's worked "Extensibility" example (writing a new opclass family) is
  summarized only; the brin/README + per-file docs carry the concrete
  `BrinOpcInfo` wiring.
</content>
