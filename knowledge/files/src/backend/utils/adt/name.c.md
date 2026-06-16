# `src/backend/utils/adt/name.c`

- **File:** `source/src/backend/utils/adt/name.c` (355 lines)
- **Last verified commit:** `4b0bf0788b066a4ca1d4f959566678e44ec93422` (2026-06-03)

## Purpose

The `name` type — a fixed-length NUL-terminated string of physical length
`NAMEDATALEN` (64 bytes by default). The internal identifier type used
throughout system catalogs (`relname`, `attname`, etc.). The file replaces
the historical `char16` and **always uses the symbolic constant**
`NAMEDATALEN` — see the strident comment at `:8-10` [from-comment].

## Type role

- **Input:** `namein` (`:48`) — truncates oversize input via
  **`pg_mbcliplen(s, len, NAMEDATALEN-1)`** so multibyte characters are
  not split mid-encoding (`:56-58` [verified-by-code]). Uses `palloc0`
  for guaranteed zero-padding (`:60-62`).
- **Output:** `nameout` (`:71`) — `pstrdup(NameStr(*s))`.
- **Binary I/O:** `namerecv` (`:82`) hard-errors if input ≥ `NAMEDATALEN`
  (not truncate, unlike `namein`); `namesend` (`:106`) — `pq_sendtext`.
- **Comparison:** `nameeq/ne/lt/le/gt/ge`, all via the static
  `namecmp(arg1, arg2, collid)` helper (`:135`). Fast-path for C
  collation does `strncmp` with `NAMEDATALEN` cap (`:138-139`); else
  delegates to `varstr_cmp` from varlena.c.
- **SortSupport:** `btnamesortsupport` (`:211`) — uses generic
  `varstr_sortsupport`. NAME does **not** support abbreviated keys
  (noted explicitly in varlena.c's varstr_sortsupport).
- **Plain C helpers (extern):** `namestrcpy(name, str)` (`:233`),
  `namestrcmp(name, str)` (`:247`).

## Built-in SQL functions

- `current_user`, `session_user` (`:263`, `:269`) — wrap
  `GetUserNameFromId` through `namein`.
- `current_schema`, `current_schemas` (`:279`, `:294`) — fetch search
  path namespace names.
- `nameconcatoid(name, oid)` (`:333`) — used by `information_schema` to
  produce per-schema `specific_name` columns. **Truncates the name part,
  not the suffix**, when the concatenation would exceed `NAMEDATALEN`
  (`:345-347` [from-comment]).

## Phase D notes

- **Multibyte-aware truncation is the load-bearing invariant.** `namein`
  uses `pg_mbcliplen` to avoid splitting a multibyte UTF-8 character at
  the truncation boundary; `nameconcatoid` does the same on the
  name-portion. Without this, a half-multibyte byte at offset 63 would
  produce an invalid-encoding catalog entry. [verified-by-code]
- **`namerecv` enforces strict length, but `namein` truncates** — this
  asymmetry can surprise clients that send long identifiers over the
  binary protocol expecting truncation parity with the text path.
  [verified-by-code, :90-95 vs :57-58]
- The `namecmp` C-collation fast-path uses `strncmp` with `NAMEDATALEN`
  bound; if a buggy caller stored a Name without a trailing NUL within
  64 bytes, the comparison could read past the end. `palloc0` discipline
  in `namein`/`namerecv`/`nameconcatoid` prevents this — but external
  C code that builds Names via `memcpy` without zero-padding the rest is
  a hazard. [inferred — see also `namestrcpy` at :233-238 which zero-pads
  defensively]
- `namestrcpy` uses `strncpy` + explicit NUL termination (`:235-237`);
  semi-safe variant of the classic strncpy pitfall.

## Potential issues

- `[ISSUE-undocumented-invariant: namein TRUNCATES, namerecv ERRORS on
  oversize input; binary-protocol clients can hit ERRCODE_NAME_TOO_LONG
  where the text path would silently truncate (:90-95 vs :57-58).
  (medium)]`
- `[ISSUE-undocumented-invariant: Name values MUST be zero-padded across
  the whole NAMEDATALEN buffer or strncmp-based comparison may read
  past the meaningful end (:139). (medium) — load-bearing for catalog
  consumers]`
- `[ISSUE-info-disclosure: namerecv errdetail leaks NAMEDATALEN as a
  hard constant (:94); already public, no real concern. (info)]`

## Cross-references

- `source/src/include/c.h` — `NAMEDATALEN`, `Name`, `NameStr` macro,
  `NameData`.
- `source/src/backend/utils/mb/mbutils.c` — `pg_mbcliplen` definition.
- `source/src/backend/utils/adt/varlena.c` — `varstr_cmp`,
  `varstr_sortsupport`.

<!-- issues:auto:begin -->
- [Issue register — `utils-adt`](../../../../../issues/utils-adt.md)
<!-- issues:auto:end -->

## Confidence tag tally

- `[verified-by-code]` × 4
- `[from-comment]` × 2
- `[inferred]` × 1
