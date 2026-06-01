# `src/backend/regex/regexec.c`

- **Last verified commit:** `ef6a95c7c64`
- **Lines:** ~1500
- **Source:** `source/src/backend/regex/regexec.c`

## Purpose

Match a compiled `regex_t` against an input string. Single export:
`pg_regexec(re, string, len, search_start, *details, nmatch, pmatch[], flags)`.
Internally drives a lazy DFA over the compiled CNFA, with NFA-backed
fallback for back-references, lookaround, and capturing-group walks.
[from-README]

## DFA-vs-NFA strategy

> "Use the DFA when possible (which is most of the time)…": the DFA is
> built **lazily** — each `(state-set, color)` transition is computed on
> first encounter and cached as a `sset` (subset state). [from-comment]

- The DFA decides reachability/match-from-start in linear time. For
  patterns without back-refs or capturing, this is the only engine
  invoked.
- For capturing-group extraction the DFA finds a candidate match range
  in linear time, then a **second pass** walks the NFA (with the input
  restricted to that range) to find the actual subgroup boundaries.
- For back-references and lookaround (which the DFA cannot represent),
  control falls back to NFA-style matching for the affected subre —
  driven from the same `subre` tree built in `regcomp.c`.

## Key data structures

- `struct dfa` (in `regexec.c`) — the lazy DFA: ssets (state-set
  records), hash table from "active-NFA-state-bitmap" → sset, free list.
- `struct sset` — one DFA state: bitmap of active NFA states + outarcs
  indexed by color + flags. Lazily expanded on first miss.
- `struct vars` — top-level matcher context (re, search range,
  current cnfa, color map, match boundaries, etc.).
- `chr` (`pg_wchar`) — input element type. DFA arcs are by `color`,
  obtained per-char via `pg_reg_getcolor(re, chr)`.

## Spine

- `pg_regexec` — argument prep, calls `cfind` (or `find` if no
  capturing groups), runs DFA via `longest`/`shortest`, optionally
  re-walks NFA for `pmatch[]`.
- `cfind` / `find` / `cdissect` — driver functions.
- `subset` (`rege_dfa.c`) — compute next DFA state on cache miss:
  follow NFA arcs labeled with the current color, mark reachable NFA
  states, hash-lookup or allocate the resulting sset.
- `miss` / `lacon` — handle lookaround constraints by re-entering with
  a constrained sub-cnfa.
- Back-ref handling: `cbrdissect` (capture+backref dissect) — uses the
  captured substring's literal text as the match target.

## Memory management

- Per-execution allocation tracked in `regex_t->re_guts` and a
  `vars`-local scratch pool. On failure, all allocations from the
  current `pg_regexec` are freed before return.
- The DFA cache is per-execution, not retained — successive matches
  rebuild it lazily. This trades repeat-pattern speed for bounded
  memory.

## Locale

Calls `pg_set_regex_collation(re->re_collation)` at top of
`pg_regexec` so the `regc_pg_locale.c` helpers used by character-class
arcs see the right collation. The collation is captured in the
`regex_t` at `pg_regcomp` time. (See README's "design debt" note.)

## Tag tally

`[verified-by-code]` 2 / `[from-README]` 4 / `[from-comment]` 1
