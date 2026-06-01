# `src/backend/regex/regcomp.c`

- **Last verified commit:** `ef6a95c7c64`
- **Lines:** ~2640
- **Source:** `source/src/backend/regex/regcomp.c`

## Purpose

Compile a regex pattern (in `pg_wchar`) into the internal `regex_t`.
`pg_regcomp(re, pattern, len, flags, collation)` is the single export;
everything else is static and reached via `#include` of the `regc_*.c`
fragments (lex, color, NFA, locale, cvec). [from-README]

## Pipeline

1. **Lex** — `regc_lex.c` tokenizes; PG runs in `REG_ADVANCED` flavor
   (mostly POSIX ERE with PCRE extensions).
2. **Parse + NFA construction** — recursive-descent in `regcomp.c`
   itself (`parsebranch`, `parseqatom`, `parseatom`). Emits an NFA
   built from `regc_nfa.c` primitives (`newstate`, `newarc`,
   `cparc`...).
3. **Color machinery** — `regc_color.c` partitions the input alphabet
   into "colors": equivalence classes such that any two characters in
   the same color either both match or both don't match every arc in
   the NFA. NFA arcs are labeled with colors rather than characters,
   so the alphabet is logarithmic in DFA state size.
4. **NFA optimization** — `regc_nfa.c` runs `optimize`, `pullback`,
   `pushfwd`, `fixempties`, `cleanup` — epsilon removal, dead-state
   pruning, useless-arc elimination.
5. **Subexpression labeling** — `subre` tree records capturing-group
   structure for `regexec.c` to refer back to.
6. **CNFA flattening** — `compact` (`regc_nfa.c`) lowers the in-memory
   NFA to a compact `cnfa` (contiguous arrays) better suited to the DFA
   builder in `regexec.c`. Lookaround/back-ref subexpressions get
   their own sub-cnfas attached to the `subre` tree.

## Important data

- `struct guts` (in `regex_t.re_guts`) — top-level compiled rep:
  cmap (colormap), search cnfa, root subre.
- `struct colormap` (`regc_color.c`) — multi-level radix lookup char →
  color. Two-level for low chars, hash for hi chars.
- `struct subre` — node in the parse tree; holds either an embedded
  cnfa (leaf) or pointers to children (capture/alternation/iteration).
- `struct cvec` — character set used during charclass parsing.
- `struct nfa`, `struct state`, `struct arc` — working NFA during
  compilation (discarded after `compact`).

## Locale awareness

`regc_locale.c` + `regc_pg_locale.c` provide bracket-expression
character-class lookups (`[:alpha:]` etc.) against the active
collation. `pg_set_regex_collation(colloid)` is called by `regcomp` to
stash the locale state used by these helpers — the unfortunate global
state called out in the README.

## Stack-depth guard

Recursion-heavy paths (parse, NFA optimization) call
`check_stack_depth()` so a maliciously deep pattern can't overflow.

## Exports beyond `pg_regcomp`

- `pg_reg_getcolor(re, chr)` — used by `regexec.c` to translate input
  chars to colors during DFA execution.
- `pg_set_regex_collation(colloid)` — also called by `regexec.c`
  before matching to ensure locale state matches.

## Tag tally

`[verified-by-code]` 2 / `[from-README]` 6
