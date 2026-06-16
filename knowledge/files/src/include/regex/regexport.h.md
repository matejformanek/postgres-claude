# `src/include/regex/regexport.h`

- **Last verified commit:** `e18b0cb7344`
- **Lines:** ~62
- **Source:** `source/src/include/regex/regexport.h`

Accessors that let outside code (notably `pg_trgm`'s regex-to-trigram
optimizer) walk the NFA inside a compiled regex without depending on
`regguts.h`. Exposes states (numbered 0..N-1), the initial+final
states, out-arcs per state, and the colormap. [verified-by-code]

## API / declarations

- `regex_arc_t { co, to }` — one arc; `co` is character-set color,
  `to` is destination state number. [verified-by-code]
- State enumeration:
  - `pg_reg_getnumstates(regex)` → N
  - `pg_reg_getinitialstate(regex)` → state number
  - `pg_reg_getfinalstate(regex)` → state number
  - `pg_reg_getnumoutarcs(regex, st)` → count
  - `pg_reg_getoutarcs(regex, st, arcs, arcs_len)` → fills the
    buffer.
- Color enumeration:
  - `pg_reg_getnumcolors(regex)`, `pg_reg_colorisbegin(regex, co)`,
    `pg_reg_colorisend(regex, co)`,
  - `pg_reg_getnumcharacters(regex, co)`,
    `pg_reg_getcharacters(regex, co, chars, chars_len)`.
- Constants mirrored from `regguts.h`:
  - `COLOR_WHITE = 0` — "color for chars not appearing in regex"
  - `COLOR_RAINBOW = -2` — "all colors except pseudocolors"

## Notable invariants / details

- "These macros must match corresponding ones in regguts.h" —
  COLOR_WHITE / COLOR_RAINBOW are duplicated rather than #included
  to keep `regguts.h` private. Changing either side without the
  other silently breaks pg_trgm. [from-comment]
- "Each state except the final one has some out-arcs that lead to
  successor states, each arc being labeled with a color that
  represents one or more concrete character codes. (The colors of a
  state's out-arcs need not be distinct, since this is an NFA not a
  DFA.)" — NFA, not DFA. [from-comment]
- "Color 0 is 'white' (all unused characters) and can generally be
  ignored." Callers commonly skip color 0 when enumerating.
  [from-comment]

## Potential issues

- The COLOR_WHITE/COLOR_RAINBOW duplication (`#define` here +
  `#define` in regguts.h) is exactly the brittle pattern the
  comment warns about. A grep-based reviewer can miss the link if a
  patch only touches regguts.h. [ISSUE-undocumented-invariant:
  COLOR_* duplicated between regexport.h and regguts.h (likely)]
- `pg_reg_getoutarcs` / `pg_reg_getcharacters` use caller-provided
  fixed-size buffers; the header doesn't say what happens on
  `arcs_len < pg_reg_getnumoutarcs(...)`. (Implementation truncates
  silently — see `backend/regex/regcomp.c`.) [ISSUE-doc-drift:
  truncation behavior of bounded getters not in header (nit)]

## Cross-references

<!-- issues:auto:begin -->
- [Issue register — `include-regex`](../../../../issues/include-regex.md)
<!-- issues:auto:end -->
