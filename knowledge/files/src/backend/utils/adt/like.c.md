# `src/backend/utils/adt/like.c`

- **File:** `source/src/backend/utils/adt/like.c` (446 lines)
- **Last verified commit:** `ef6a95c7c64de07dff4dd1f1da88ffae7b086ef3` (2026-06-01)

## Purpose

The `LIKE` / `NOT LIKE` / `ILIKE` / `NOT ILIKE` operators with `%`/`_`
wildcard semantics. The actual matcher is a compact recursive automaton
implemented in **`like_match.c`** (a templated header included
multiple times with different macros to produce specialized variants).
(`like.c:6-9` "A big hack of the regexp.c code!! Contributed by Keith
Parks (7/95)." [from-comment])

## The 4-variant template instantiation (`:95-134`)

`like_match.c` is `#include`d four times into `like.c`, each time with
different macros set. This is the same template-by-include technique
used in `lib/sort_template.h` and elsewhere.

| Inclusion | Macros set | Produces |
|---|---|---|
| `:95-109` | `CHAREQ=wchareq`, multibyte `NextChar` | `MB_MatchText` (multibyte general) |
| `:111-119` | `CHAREQ=byte compare`, single-byte `NextChar` | `SB_MatchText` (single-byte) |
| `:121-126` | `MATCH_LOWER` + SB | `C_IMatchText` (case-insensitive in C locale) |
| `:128-134` | UTF-8 fast `NextChar` (byte-walks continuation bytes inline) | `UTF8_MatchText` |

Generated function shape:
```c
int MatchText(const char *t, int tlen, const char *p, int plen,
              pg_locale_t locale);
/* returns LIKE_TRUE (1), LIKE_FALSE (0), or LIKE_ABORT (-1) */
```

`LIKE_ABORT` is the tri-state outcome used by the recursive `%`-handler
to short-circuit: if a sub-pattern can never match against any
suffix-extension, abort all the way back instead of trying further
splits.

## Dispatch — `GenericMatchText` (`:138`) and `Generic_Text_IC_like` (`:165`)

```c
if (max_mb_len == 1)       return SB_MatchText(...)     // SQL_ASCII, LATIN1, etc.
else if (encoding == UTF8) return UTF8_MatchText(...)   // fastest MB case
else                       return MB_MatchText(...)     // general MB
```

For **ILIKE on non-C locales**, the comment at `:80-90` reveals the
historical hack:
> "So now, we just downcase the strings using lower() and apply regular
> LIKE comparison. This should be revisited when we install better locale
> support."

So `Generic_Text_IC_like` lowercases both the haystack and the pattern
(via `str_tolower`) and runs the case-sensitive matcher. C-locale ILIKE
gets the more efficient `C_IMatchText` with fold-on-the-fly.

`OidIsValid(collation)` is enforced (`:142-152`); a missing collation
raises `ERRCODE_INDETERMINATE_COLLATION`.

## Public operators

For each of `name`, `text`, and `bytea`:
- `*like` (`LIKE`) / `*nlike` (`NOT LIKE`).
- For text/name only: `*iclike` (`ILIKE`) / `*icnlike` (`NOT ILIKE`).

```
name:    namelike/namenlike,   nameiclike/nameicnlike
text:    textlike/textnlike,   texticlike/texticnlike
bytea:   bytealike/byteanlike  (no case-insensitive variant)
```

bytea uses `SB_MatchText` directly — no encoding-awareness, since bytea
is opaque bytes.

## `wchareq` (`:57-77`)

Fast equality on one possibly-multibyte character. Single-byte-fast-path
when first bytes differ. Comment at `:79-90` is the history of the
defunct `iwchareq` — case-insensitive multibyte equality used to be
attempted character-by-character but proved hopelessly broken across
locales/Unicode, so it was removed.

## `like_escape` and `like_escape_bytea` (`:420, 439`)

Convert a pattern with a user-specified escape character to one with the
default `\` escape, by walking the pattern and emitting `\\` for every
literal escape character, etc. This is what `LIKE pat ESCAPE 'x'`
desugars to before the matcher runs.

## LIKE_ABORT — why it matters

When the matcher hits `%` followed by more pattern, it must try matching
the rest of the pattern at every position in the haystack. Naively this
is O(n*m). `LIKE_ABORT` propagates upward when a sub-pattern contains a
constraint that's globally impossible (e.g. pattern longer than
remaining haystack and no more `%`s) — saving the outer `%` loop from
trying further suffix positions. This bounds the algorithm to roughly
O(n*m) in worst case but typically much better.

## Cross-references

- `source/src/backend/utils/adt/like_match.c` — the matcher template
  (read in conjunction with this file).
- `source/src/backend/utils/adt/like_support.c` — planner support
  function for LIKE; rewrites `col LIKE 'prefix%'` to a btree-indexable
  range-bound condition.
- `source/src/backend/utils/adt/regexp.c` — proper regex; LIKE is
  considered the dumb cousin.
- `source/src/backend/utils/adt/formatting.c` — `lower()` /
  `str_tolower` used by `Generic_Text_IC_like`.

## Confidence tag tally

- `[verified-by-code]` × ~5
- `[from-comment]` × ~3

## Synthesized by
<!-- backlinks:auto -->
- [subsystems/optimizer.md](../../../../../subsystems/optimizer.md)
