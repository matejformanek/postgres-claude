# `src/include/regex/regguts.h`

- **Last verified commit:** `e18b0cb7344`
- **Lines:** ~564
- **Source:** `source/src/include/regex/regguts.h`

Internal interface for the Henry Spencer regex engine — definitions
of the compile-time NFA representation (`state`, `arc`, `nfa`), the
compacted runtime NFA (`cnfa`, `carc`), the colormap (`colormap`,
`colordesc`, `colormaprange`), character sets (`cvec`), the
subexpression tree (`subre`), and the opaque "guts" stored behind
`regex_t.re_guts`. Pulled in via `#include "regcustom.h"` so PG's
allocator + interrupt overrides take effect. [verified-by-code]

## API / declarations

### Misc constants

- `NOTREACHED 0`, `DUPMAX = _POSIX2_RE_DUP_MAX (255)`,
  `DUPINF = DUPMAX+1 (256)`.
- `REMAGIC 0xfed7` — magic for `pg_regex_t.re_magic`.
- Lookaround types: `LATYPE_AHEAD_POS=03`, `LATYPE_AHEAD_NEG=02`,
  `LATYPE_BEHIND_POS=01`, `LATYPE_BEHIND_NEG=00`. Predicates
  `LATYPE_IS_POS(la) := (la)&01`, `LATYPE_IS_AHEAD(la) := (la)&02`.
  [verified-by-code]
- Debug: `FDEBUG`/`MDEBUG` macros, enabled under `REG_DEBUG`.

### Bitmaps and char classes

- `UBITS = CHAR_BIT * sizeof(unsigned)`, `BSET(uv,sn)`,
  `ISBSET(uv,sn)`.
- `enum char_classes { CC_ALNUM, CC_ALPHA, CC_ASCII, CC_BLANK,
  CC_CNTRL, CC_DIGIT, CC_GRAPH, CC_LOWER, CC_PRINT, CC_PUNCT,
  CC_SPACE, CC_UPPER, CC_XDIGIT, CC_WORD }`. `NUM_CCLASSES=14`.

### Colormap (chr → color equivalence-class)

- `typedef short color`; `MAX_COLOR=32767`, `COLORLESS=-1`,
  `RAINBOW=-2`, `WHITE=0` (zero relied on across the code).
  [from-comment]
- `colordesc { nschrs, nuchrs, sub, arcs, firstchr, flags }` —
  `flags ∈ { FREECOL=01, PSEUDO=02, COLMARK=04 }`. `NOSUB=COLORLESS`
  marks no-open-subcolor. Free colors are linked through their `sub`
  field. [from-comment]
- `colormaprange { cmin, cmax, rownum }` — must be nonempty,
  nonoverlapping, sorted ascending. [from-comment]
- `colormap { magic=CMMAGIC=0x876, v, ncds, max, free, cd, locolormap
  (chr ≤ MAX_SIMPLE_CHR), classbits[NUM_CCLASSES], numcmranges,
  cmranges, hicolormap (2D high-chr table), maxarrayrows/hiarrayrows/
  hiarraycols, cdspace[NINLINECDS=10] }`. Inline space for up to 10
  colordescs avoids a malloc on small regexes. [verified-by-code]
- `GETCOLOR(cm, c)` — fast path uses `locolormap[c - CHR_MIN]` when
  `c <= MAX_SIMPLE_CHR`, else falls back to `pg_reg_getcolor`.
  Multi-evaluation warning on `c`. [from-comment]

### Character sets (cvec)

- `cvec { nchrs, chrspace, chrs, nranges, rangespace, ranges,
  cclasscode }` — `cclasscode` carries the class enum (e.g. CC_ALPHA)
  if this cvec was constructed from a `[[:alpha:]]` expression;
  otherwise -1. `newcvec`-allocated cvecs put both arrays after the
  struct (immutable size). [from-comment]

### NFA (compile-time)

- `arc { type, co, from, to, outchain, outchainRev, inchain,
  inchainRev, colorchain, colorchainRev }`. `freechain := outchain`
  reuses the slot for free-list linkage; "we do not maintain
  freechainRev". [from-comment]
- `arcbatch { next, narcs, a[FLEX] }` — bulk allocator;
  `FIRSTABSIZE=64`, `MAXABSIZE=1024` (doubling).
- `state { no, flag, nins, nouts, ins, outs, tmp, next, prev }`.
  `next` reused for free-state chaining when `no = FREESTATE = -1`.
  [from-comment]
- `statebatch { next, nstates, s[FLEX] }`; `FIRSTSBSIZE=32`,
  `MAXSBSIZE=1024`.
- `nfa { pre, init, final, post, nstates, states (live chain),
  slast, freestates, freearcs, lastsb, lastab, lastsbused,
  lastabused, cm, bos[2], eos[2], flags, minmatchall, maxmatchall,
  v, parent }`. `parent` chains for nested NFAs of lookaround
  constraints. [verified-by-code]

### Compacted NFA (runtime)

- `carc { co, to }` — terminator is `co=COLORLESS`. LACON arcs encode
  the lookaround index as `co = cnfa.ncolors + lacon_no`, so a
  greater-than test discriminates them. [from-comment]
- `cnfa { nstates, ncolors, flags, pre, post, bos[2], eos[2],
  stflags (per-state byte vector), states (vector of carc* into
  arcs), arcs (single block), minmatchall, maxmatchall }`. flags:
  `HASLACONS=01`, `MATCHALL=02`, `HASCANTMATCH=04` ("appears in nfa
  flags, but never in cnfas").
- Per-state flag in `stflags`: `CNFA_NOPROGRESS=01`.
- "trivial" NFAs that match all strings in a length range are flagged
  `MATCHALL` and use `minmatchall`/`maxmatchall` — e.g. `.*` →
  min=0, max=DUPINF; `.+` → min=1, max=DUPINF. [from-comment]
- `ZAPCNFA(cnfa)` macro — full memset in `REG_DEBUG`, else just
  `nstates=0`. `NULLCNFA(cnfa) := nstates == 0`. [from-comment]

### Compile-space governor

- `REG_MAX_COMPILE_SPACE = 500000 * (sizeof(state) + 4*sizeof(arc))`
  — empirical 4 arcs/state ratio. "Do not raise this so high as to
  allow more than INT_MAX/8 states or arcs, or you risk integer
  overflows in various space allocation requests." [from-comment]

### subre (subexpression tree)

- `subre { op, flags, latype, id, capno, backno, min, max, child,
  sibling, begin, end, cnfa, chain }`. `op` ∈ `{'=', 'b', '(', '.',
  '|', '*'}` (DFA, backref, capture, concat, alt, iter).
  [from-comment]
- Flags: `LONGER=01`, `SHORTER=02`, `MIXED=04`, `CAP=010`,
  `BACKR=020`, `BRUSE=040` (referenced by some backref),
  `INUSE=0100`. Computed combinators: `UPPROP=MIXED|CAP|BACKR`,
  `LMIX/SMIX/UP/MESSY/PREF/PREF2/COMBINE` macros.

### Generic function dispatch

- `fns { free(regex_t*), stack_too_deep(void) }` —
  `regex_t.re_fns` points to one of these. PG's instance routes
  `stack_too_deep` to PG's per-thread/per-backend stack-depth check.
  [inferred]
- `STACK_TOO_DEEP(re)` macro.

### The opaque "guts"

- `guts { magic=GUTSMAGIC=0xfed9, cflags, info, nsub, tree, search
  (cnfa), ntree, cmap, compare (chr-compare function pointer),
  lacons[], nlacons }`. `lacons` is 1-indexed (slot 0 unused).
  [from-comment]

### Exported prototypes (regcomp.c → regexec.c)

- `pg_set_regex_collation(Oid)`,
- `pg_reg_getcolor(struct colormap *, chr)`.

## Notable invariants / details

- All sentinel values relied on: `WHITE=0` (multiple call sites
  assume zero is the default color), `COLORLESS=-1` as
  list-terminator in `carc`, `RAINBOW=-2` as a "matches any concrete
  char" pseudo-color. [from-comment]
- Free arcs reuse the `outchain` slot for the free-chain — must NOT
  walk `outchainRev` on a freed arc. [from-comment]
- `cnfa.states[n]` indexes into a SINGLE malloc'd `cnfa.arcs` block
  — partial frees are not legal. [from-comment]
- `lacons[0]` is intentionally unused — lookaround numbering starts
  at 1. [from-comment]
- `REG_MAX_COMPILE_SPACE` charges only states + arcs against the
  budget; cmaps + final compacted NFA are free. [from-comment]
- `HASCANTMATCH` "appears in nfa structs' flags, but never in cnfas"
  — invariant a reviewer of compaction logic must preserve.
  [from-comment]

## Potential issues

- `COLOR_WHITE` / `COLOR_RAINBOW` are duplicated in `regexport.h`
  with an explicit "must match" comment. Easy to drift in a patch
  that only touches one side. [ISSUE-undocumented-invariant: two
  copies of color constants (likely)]
- `subre.flags` is a `char` carrying a 7-bit space (`INUSE=0100` is
  bit 6); on signed-char platforms (PowerPC), sign extension could
  flip results of `MESSY(f)` if any bit ≥ 0x80 were ever added.
  Today no flag uses 0x80. [ISSUE-undocumented-invariant: subre.flags
  must stay signed-char-safe (maybe)]
- `REG_MAX_COMPILE_SPACE` enforced only at the granularity of
  state+arc count; a pathological regex that allocates huge cvecs
  (locale character class explosion) is not charged.
  [ISSUE-question: cvec memory not in compile-space budget (maybe)]
- "REALLOC_ARRAY" overflow-check TODO from regcustom.h actually
  lives here, in the fallback definitions (lines 84-86): "XXX this
  definition does not provide the desired overflow check". PG's
  override avoids this, but the upstream-syncability is the issue.
  [ISSUE-stale-todo: REALLOC_ARRAY overflow XXX in fallback path
  (nit)]
- `STACK_TOO_DEEP` indirect-call-via-fns adds a function-pointer
  hop on every recursion guard; minor perf cost but the indirection
  is mandated by Spencer's "fns" pluggability. [ISSUE-question: is
  the fns indirection still load-bearing for any non-PG caller?
  (nit)]
