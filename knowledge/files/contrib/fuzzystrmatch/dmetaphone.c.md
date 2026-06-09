# source/contrib/fuzzystrmatch/dmetaphone.c

**Source pin:** master @ 4b0bf07. 1443 LOC. Largely a direct port of
the Text::DoubleMetaphone Perl module (Maurice Aubrey, 2000) based
on Lawrence Philips' C++ implementation.

## Role

Double Metaphone: produces a primary + alternate phonetic encoding
for each input word. Used as a coarser-grained fuzzy-match key than
classical Metaphone (also handles non-English names).

## Public API (SQL-callable)

- `dmetaphone(text)` → text — primary code only
  [source/contrib/fuzzystrmatch/dmetaphone.c:132]
- `dmetaphone_alt(text)` → text — alternate code only
  [source/contrib/fuzzystrmatch/dmetaphone.c:161]

Both call `DoubleMetaphone(str, collid, codes[])` internally — they
each compute both codes and throw one away. Header comment at line
42-47 acknowledges this inefficiency.

## Invariants

- INV: `DoubleMetaphone` outer loop terminates when
  `primary->length >= 4 && secondary->length >= 4`, OR when the
  input is exhausted
  [verified-by-code source/contrib/fuzzystrmatch/dmetaphone.c:437].
- INV: input is uppercased via `str_toupper` using the function's
  collation argument (collid)
  [verified-by-code dmetaphone.c:288, called from line 422].
- INV: input is padded with 5 spaces so the algorithm can safely
  index `current + 4` without bounds-checking inside hot path
  [verified-by-code dmetaphone.c:415].
- INV: `metastring` is a growable buffer; `MetaphAdd` calls
  `IncreaseBuffer` when needed [dmetaphone.c:391-395]; buffer
  grows by `add_length + 10` per realloc [dmetaphone.c:276-278].
- INV: `META_FREE` is **NO-OP in the in-backend build**
  [verified-by-code dmetaphone.c:201]. Memory is reclaimed via
  memory-context cleanup. Comment at 196-199: "Don't do pfree -
  it seems to cause a SIGSEGV sometimes - which might have just
  been caused by reloading the module in development." Tom Lane
  cited as authority for context-cleanup-only model.
- INV: `StringAt` uses varargs terminated by empty string `""`
  [dmetaphone.c:374]. **The variadic list MUST end with `""`** or
  the iteration runs off the end.
- INV: code output strings are short ASCII letters (P, K, F, X,
  etc.) per Double Metaphone rules.

## Notable internals

- The algorithm is a giant switch over `GetAt(original, current)`
  with deeply nested `if (StringAt(...))` rule checks per letter.
  Each rule advances `current` by 1-3 to skip past the digraph
  it consumed.
- `SlavoGermanic` test [dmetaphone.c:313-326] modulates Slavic-vs-
  Germanic alternate codes by substring presence of W/K/CZ/WITZ.
- ISO-8859-1 letter `\xc7` (Ç) is special-cased [dmetaphone.c:471].
- Backend build: `META_MALLOC` = `palloc`, `META_REALLOC` =
  `repalloc`. Standalone build (`-DDMETAPHONE_MAIN`) uses libc.

## Trust-boundary / Phase-D surface

1. **Input length not bounded at SQL entry.** Unlike
   `metaphone()` (which caps at 255 bytes), `dmetaphone()` has
   no explicit length cap. `text_to_cstring` allocates a copy
   bounded by text varlena size (1GB default). The outer loop
   in `DoubleMetaphone` terminates as soon as BOTH codes reach
   length 4 — but a malicious input could be designed where
   neither code grows fast (e.g., all silent letters or all
   characters that produce no metaph output), in which case
   the loop runs O(input_length).
2. **No CHECK_FOR_INTERRUPTS in the main loop.** The loop body
   does constant work per iteration, so a 100MB input would
   spin for a few seconds with no cancel point. Defense-in-depth
   would add one CFI per outer iteration.
3. **`MetaphAdd` + `IncreaseBuffer` growth is `add_length + 10`
   per call.** Each rule adds at most 1-2 chars to each
   metastring, but for an input that never satisfies the
   `length >= 4` terminator, the buffers keep growing. In the
   backend build, memory is held until function exit (META_FREE
   is no-op). For a long-lived backend running batch
   normalization, this is amortized via context reset, but a
   single mega-call can briefly hold input_length * 2 bytes.
4. **`free_string_on_destroy = 0` on `primary`/`secondary`**
   [dmetaphone.c:419-420]: the OUTPUT metastrings deliberately
   leak their `->str` because the caller (`dmetaphone()` SQL
   wrapper) reads `codes[0]/codes[1]` directly. Comment at
   line 196 explains. Combined with the no-op META_FREE this
   is correct, but it means the buffer is reachable only via
   the codes[] pointers — subtle.
5. **`str_toupper` uses the caller's collation (collid).** Unlike
   `_metaphone` (ASCII-only), `dmetaphone` IS collation-aware.
   Collation drift between training data and query yields
   non-deterministic results. Echo of A13 citext concern.
6. **Side-channel pattern same as metaphone/soundex** — any user
   with SELECT can compute `dmetaphone(secret_col)` to enumerate
   phonetic signatures.
7. **`StringAt` varargs terminator is `""` (empty string).** If
   a future maintainer accidentally omits the terminating `""`
   in a call, the macro walks past the end of the va_list.
   Search shows ~hundreds of `StringAt` calls. C correctness
   depends on rigorous code review. Not a current bug, but a
   maintenance hazard.

## Cross-refs

- `source/contrib/fuzzystrmatch/fuzzystrmatch.c` — sibling
  classical Metaphone + Soundex + Levenshtein
- `source/contrib/fuzzystrmatch/daitch_mokotoff.c` — alternate
  phonetic coding with more rules

## Issues

- [ISSUE-Phase-D: no CHECK_FOR_INTERRUPTS in DoubleMetaphone loop (med)] —
  source/contrib/fuzzystrmatch/dmetaphone.c:437-(end of main loop) —
  for adversary inputs that never grow primary/secondary fast,
  the loop runs O(input_length) with no cancel point.
- [ISSUE-Phase-D: no input length cap at SQL entry (low)] —
  source/contrib/fuzzystrmatch/dmetaphone.c:143,172 — unlike
  `metaphone()` (255-byte cap), `dmetaphone()` accepts any text
  size. Adversary can pass 1GB and pin CPU.
- [ISSUE-Style: META_FREE is no-op, relies on context cleanup (low)] —
  source/contrib/fuzzystrmatch/dmetaphone.c:201 — acknowledged
  in comment; memory accumulates within a single call (bounded
  by input size).
- [ISSUE-Style: StringAt varargs `""` terminator is a footgun (low)] —
  source/contrib/fuzzystrmatch/dmetaphone.c:353-379 — variadic
  iteration depends on caller appending `""`. Hundreds of call
  sites; rigorous review only.
- [ISSUE-Phase-D: phonetic-coding side channel (low)] — same
  family as fuzzystrmatch.c soundex/metaphone.
