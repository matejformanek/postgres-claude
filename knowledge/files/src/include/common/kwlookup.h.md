# src/include/common/kwlookup.h

## Purpose

Defines the generic `ScanKeywordList` struct and the
`ScanKeywordLookup` perfect-hash lookup used by every PG keyword
table (SQL, plpgsql, ecpg).

## Role in PG

Used by both **frontend** and **backend** — anyone scanning a token
stream that needs to recognise reserved words. PL/pgSQL, ecpg, and
the main parser all use the same machinery, just with different
generated `ScanKeywordList` instances.

## Key declarations

- `typedef int (*ScanKeywordHashFunc)(const void *key, size_t keylen)`
  — perfect-hash function signature; the generator
  `src/tools/gen_keywordlist.pl` produces these.
  (`kwlookup.h:18`)
- `struct ScanKeywordList` — keyword string pool + offset table +
  hash function + counts + max length. The pool is a single
  `\0`-separated blob; `kw_offsets[i]` indexes into it.
  (`kwlookup.h:25-32`)
- `int ScanKeywordLookup(const char *str, const ScanKeywordList *)`
  — case-insensitive lookup, returns position or -1.
  (`kwlookup.h:35`)
- `static inline const char *GetScanKeyword(int n, ...)` — index into
  the string pool for the n'th keyword.
  (`kwlookup.h:38-42`)

## Phase D notes

Bounded read-only operation. The perfect-hash result is range-checked
in the .c implementation before indexing, so a hash collision with
non-keyword text cannot cause an OOB read.

## Potential issues

None — header is declaration-only.
