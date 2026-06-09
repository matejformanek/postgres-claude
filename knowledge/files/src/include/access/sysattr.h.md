# `src/include/access/sysattr.h`

**Source pin:** `4b0bf0788b066a4ca1d4f959566678e44ec93422`
**30 lines.**

## Role

Defines the **negative AttrNumbers** for the seven system pseudo-columns
that every heap-backed relation has: `ctid`, `xmin`, `cmin`, `xmax`,
`cmax`, `tableoid`. Plus the sentinel `FirstLowInvalidHeapAttributeNumber`
used by callers to bracket the system-attr range.
[verified-by-code] `source/src/include/access/sysattr.h:1-13`

## Public API

Seven `#define`s (lines 21-27):

```
SelfItemPointerAttributeNumber       = -1   /* ctid */
MinTransactionIdAttributeNumber      = -2   /* xmin */
MinCommandIdAttributeNumber          = -3   /* cmin */
MaxTransactionIdAttributeNumber      = -4   /* xmax */
MaxCommandIdAttributeNumber          = -5   /* cmax */
TableOidAttributeNumber              = -6   /* tableoid */
FirstLowInvalidHeapAttributeNumber   = -7   /* sentinel */
```

## Invariants

- **INV-sysattr-negative:** all system attributes have **negative**
  `AttrNumber`. User columns are 1..N; 0 is invalid; -1..-6 are
  system; -7 and below are invalid.
- **INV-sysattr-fixed-ids:** these numbers are **wire-level constants**.
  Any code path that maps SQL names to AttrNumbers (parser, executor,
  rewriter, replication output plugins) hardcodes the values. Renumbering
  is impossible without breaking binary compatibility.
- **INV-sysattr-bracket:** valid system attributes satisfy
  `attno > FirstLowInvalidHeapAttributeNumber && attno < 0`. Callers
  use this idiom in bitmapset construction (system + user attrs
  combined into one set by offsetting by `FirstLowInvalidHeapAttributeNumber`).

## Notable internals

The negative-AttrNumber convention is one of the oldest invariants in PG
(predates this header's separation). The reason: when AttrNumber was
chosen as `int16`, having user columns at 1..N and system at -1..-6
gave a single `if (attno > 0)` test for "is this a user column?".

Historically there was also `ObjectIdAttributeNumber = -7` for `oid`
columns on user tables, but `WITH OIDS` was removed in PG12 and the
slot was reclaimed as `FirstLowInvalidHeapAttributeNumber`. The
re-numbering is visible if you compare PG11 and PG12 sources.
[inferred from git log]

## Trust-boundary / Phase D surface

These are observable on every table by every user with `SELECT`
privilege. `xmin`/`xmax`/`cmin`/`cmax` expose transaction-ID metadata
about who modified a row. **A4-style xid scraping** — a low-privilege
user can `SELECT xmin FROM public.big_table` to enumerate which xids
have modified rows, indirectly observing system-wide transaction
activity beyond their own session.

`tableoid` exposes the relation's OID; combined with partition pruning,
a SELECT against a partitioned parent can leak partition-routing logic
(`SELECT tableoid::regclass, * FROM parent WHERE ...`).

`ctid` exposes physical row location; combined with `pg_visibility` or
just iterated probing, can map physical layout of the heap.

None of this is novel — it's the PG model — but the header is the
single place where these surfaces are NAMED.

## Cross-refs

- `access/htup_details.h` — accessor macros (`HeapTupleHeaderGetXmin`
  etc.) that the executor uses when these attrs are projected.
- `parser/parse_target.c` — the SQL-name-to-AttrNumber lookup
  (`SystemAttributeByName`).
- `nodes/bitmapset.h` — bitmapsets typically use this header's
  `FirstLowInvalidHeapAttributeNumber` to offset attnums.
- `subsystems/parser-and-nodes.md` — parser narrative.

## Issues

- **ISSUE-history**: `-7` was `ObjectIdAttributeNumber` pre-PG12;
  any forensic tool reading old pg_dump output should know.
- **ISSUE-leak (Phase D)**: documented xid-scrape surface; the
  header could carry a comment pointing at the trust model.
