---
path: src/tools/pg_bsd_indent/lexi.c
anchor_sha: b78cd2bda5b1a306e2877059011933de1d0fb735
loc: 721
depth: deep
---

# `src/tools/pg_bsd_indent/lexi.c` — the indenter's token scanner

## Purpose

The lexical analyser for `pg_bsd_indent`. `lexi()` reads one token from the
input buffer into the global `token` (= `s_token`) and returns an integer code
from `indent_codes.h` describing what kind of token it is (identifier, keyword,
operator, paren, comment-start, etc.). It also maintains the typedef-name table
used to recognise user types, and the `is_func_definition()` lookahead that
distinguishes a function *definition* from a *declaration*. Driven by the main
loop in [[knowledge/files/src/tools/pg_bsd_indent/indent.c]].

## Public symbols

| Symbol | Lines | Notes |
|---|---|---|
| `lexi(struct parser_state *)` | 215-675 | Scan + classify one token; returns an `indent_codes.h` code. |
| `alloc_typenames` | 677-685 | Allocate the initial 16-slot `typenames[]` array. |
| `add_typename(const char *)` | 687-721 | Insert a type name keeping `typenames[]` sorted (for `bsearch`). |

File-scope: `specials[]` keyword table (lexi.c:69-113), `chartype[128]` ASCII
class table (lexi.c:119-139), `is_func_definition()` (static, lexi.c:159-213).

## Internal landmarks

- **`specials[]`** (lexi.c:69-113): the reserved-word table mapping each keyword
  to a small integer `rwcode` (3=struct/union/enum, 4=type keyword, 5=if/while/
  for, 6=do/else, 7=switch, 8=case/default, 9=break/goto/return, 10=storage
  class, 11=typedef, 12=continue/inline/restrict). `lexi` `bsearch`es it via
  `strcmp_type` (lexi.c:141-145, 352-356).
- **`chartype[]`** (lexi.c:119-139): per-byte classification (1=alphanumeric,
  3=operator char, 0=other) used to start the alphanumeric-vs-operator branch.
- **Number scanning** (lexi.c:245-311): handles `0b`/`0x`/octal/decimal,
  exponents, and `U`/`L`/`F` suffixes.
- **Typedef recognition** (lexi.c:357-369): if a token isn't a keyword, it may
  still be a type — recognised either by the `-ta` "ends in `_t`" heuristic
  (`auto_typedefs`) or by membership in the `typenames[]` table populated from
  `-U typedefs.list` / `-T name`.
- **`is_func_definition`** (lexi.c:159-213): from the `(`, scans ahead (using
  `lookahead()` from io.c to cross line boundaries) for the first
  unparenthesised `{` (→ definition) vs `;`/`,` (→ declaration), skipping
  comments and nested parens.

## Invariants & gotchas

- **`specials[]` MUST stay alphabetically sorted**, and `rwd` must be the first
  field of `struct templ`, because `lexi` `bsearch`es it. The comment at
  lexi.c:65-68 states this. Adding a keyword out of order silently breaks
  recognition of everything after it. `[from-comment]` `[verified-by-code]`
- **`typenames[]` must stay sorted too** — `add_typename` (lexi.c:687-721)
  carefully inserts in order (taking advantage of sorted input when it can) and
  drops duplicates, precisely so the `bsearch` at lexi.c:362-364 is valid. If a
  caller bypassed `add_typename` and appended unsorted, type recognition would
  misbehave.
- **K&R blind spot.** `is_func_definition`'s own comment (lexi.c:150-157) admits
  it is fooled by K&R-style parameter declarations and by apparent comment
  starts inside string literals — judged not worth the complexity. This is one
  root cause of occasional odd indentation around unusual function signatures.
  `[from-comment]`
- `chartype[*buf_ptr & 127]` masks to 7 bits — bytes ≥ 128 (UTF-8 continuation
  bytes in identifiers/comments) fold into the low table and are treated as
  "other"; fine because comments/strings are copied verbatim elsewhere.

## Cross-refs

- [[knowledge/files/src/tools/pg_bsd_indent/indent_codes.h]] — the integer codes returned.
- [[knowledge/files/src/tools/pg_bsd_indent/io.c]] — `lookahead()`/`fill_buffer()` feeding the scan.
- [[knowledge/files/src/tools/pg_bsd_indent/indent.c]] — the consumer of `lexi`'s codes.

## Potential issues

(none beyond the documented K&R `is_func_definition` limitation, which is an
acknowledged design tradeoff, not a defect.)
