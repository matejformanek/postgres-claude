# `src/backend/utils/adt/varchar.c`

- **File:** `source/src/backend/utils/adt/varchar.c` (1227 lines)
- **Last verified commit:** `ef6a95c7c64de07dff4dd1f1da88ffae7b086ef3` (2026-06-01)

## Purpose

Implementation of the SQL types `char(n)` (= `bpchar`, **blank-padded**)
and `varchar(n)`. Both are varlena, but bpchar is logically right-padded
with spaces to the declared length, which affects equality, ordering,
and length reporting. (`varchar.c:1-4` [from-comment])

## The two types and their data model

- **`bpchar` / `char(n)`** — stored padded with spaces up to `n`
  characters; trailing blanks are semantically insignificant in
  comparison (treated as if they weren't there). On disk it really has
  the padding; functions like `bcTruelen()` (`:673`) and
  `bpchartruelen()` (`:679`) compute the un-padded length for comparison.
- **`varchar` / `varchar(n)`** — stored without padding. The typmod is
  a length **limit** only.

### Typmod encoding (historical quirk)

`anychar_typmodin` (`:33`):
> "For largely historical reasons, the typmod is VARHDRSZ plus the
> number of characters; there is enough client-side code that knows about
> that that we'd better not change it." (`:60-64` [from-comment])

So `bpchar(10)` stores typmod = `VARHDRSZ + 10 = 14`. Clients (psql,
libpq, ORMs) read this back via `bpchartypmodout` (`:428`) which
subtracts `VARHDRSZ` to recover the logical length.

## Input / output

For each of bpchar and varchar:
- `*_input(s, len, atttypmod, escontext)` — internal parser, soft-error
  capable via `escontext`.
- `*in` / `*out` / `*recv` / `*send` — fmgr-shaped wrappers.

bpchar input pads with spaces to `n` characters (where "characters" is
multibyte-aware, using `pg_mbcliplen`). varchar input rejects with an
error if longer than `n`, except via the explicit cast path which
truncates.

## Length semantics

- `bcTruelen(arg)` (`:673`) — strips trailing spaces before computing
  length. Operates on a `BpChar *`.
- `bpchartruelen(s, len)` (`:679`) — same but on raw byte slice.
- `bpcharlen` (`:696`) — character (not byte) count of bpchar after
  stripping trailing blanks.
- `bpcharoctetlen` (`:712`) — byte count after stripping trailing blanks.

## Equality and comparison

`bpchareq` (`:746`) and friends (`bpcharne, bpcharlt, bpcharle, bpcharge,
bpchargt, bpcharcmp`) all use `bcTruelen` to ignore trailing blanks
before delegating to the byte-or-collation compare. This is why `'foo'
::char(5) = 'foo'::char(3)` is true.

`varchar` itself does NOT have its own comparison ops — it shares the
text operators (since storage matches text). varchar is essentially text
with a length-check entry point.

## Cast / coerce machinery

- `bpchar(input, typmod, isExplicit)` (`:271`) — coerces an existing
  bpchar to a different typmod (truncate / re-pad).
- `varchar(input, typmod, isExplicit)` (`:612`) — same for varchar.
- `varchar_support` (`:568`) — the **planner support function**
  (`SUPPORT_REQUEST_SIMPLIFY`) registered for the varchar length-coerce
  function. Simplifies `varchar(varchar_x, m)` calls when `m` is
  identical to or wider than the input typmod (a no-op cast).
- `char_bpchar` (`:354`), `bpchar_name` (`:373`), `name_bpchar` (`:410`)
  — bidirectional with the `"char"` and `name` types.

## SortSupport

Note: **bpchar's `BTSORTSUPPORT_PROC` lives in `varlena.c`**, not here —
the `bpcharfastcmp_c` / `bpcharfastcmp_locale` family is part of the
unified `varstr_sortsupport` machinery. See
`knowledge/files/src/backend/utils/adt/varlena.c.md` for the
abbreviated-key story; here we only own the trailing-blank-stripping
helpers it calls into.

`check_collation_set` (`:730`) — small helper that ereports if no
collation is in scope for an operation that needs one. Used by both
bpchar and varchar operators.

## Cross-references

- `source/src/backend/utils/adt/varlena.c` — sortsupport (incl. BpChar
  paths), text-like operators.
- `source/src/include/utils/varlena.h`.
- `source/src/include/catalog/pg_type.dat` — defines `bpchar` (OID
  1042) and `varchar` (OID 1043).
- `source/src/backend/utils/mb/pg_wchar.c` — `pg_mbcliplen` for
  multibyte-safe truncation.

## Confidence tag tally

- `[verified-by-code]` × ~6
- `[from-comment]` × ~2
