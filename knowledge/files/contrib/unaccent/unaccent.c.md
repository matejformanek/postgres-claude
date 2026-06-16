# contrib/unaccent/unaccent.c

Source pin: `4b0bf0788b066a4ca1d4f959566678e44ec93422`.

## Role

Implements the `unaccent` text-search dictionary template — strips
accents (and applies user-defined character replacements) using a
byte-indexed trie. Also provides the standalone `unaccent(text)` /
`unaccent(dict, text)` SQL function for direct calls outside the
tsvector pipeline. [verified-by-code]
`source/contrib/unaccent/unaccent.c:336-433` (lexize/init),
`:438-502` (unaccent_dict wrapper).

## Public API (SQL-callable)

- `unaccent_init(internal) → internal` — text-search dictionary
  template init hook (`:336-375`).
- `unaccent_lexize(internal, internal, int4, internal) → internal` —
  lexize hook (`:377-433`).
- `unaccent_dict(text)` / `unaccent_dict(regdictionary, text)` —
  user-facing wrapper (`:438-502`). [verified-by-code]

## Invariants

- Trie node is `TrieChar[256]` indexed by raw byte value (`:43-48,
  :63`). One node per byte position. The trie pays no attention to
  multibyte char boundaries (`:38-42` comment) — correct as long as
  both rules and input are validly encoded in the current encoding;
  partial-char matches cannot occur because the next byte would
  always be a valid continuation byte. [verified-by-code, from-comment]
- `placeChar` warns and skips on duplicate source strings — first
  rule wins (`:72-74`). Not a hard error. [verified-by-code]
- Rules file path: `get_tsearch_config_filename(basename, "rules")`
  (`:104`). The basename is enforced by `ts_utils.c:49` to match
  `[a-z0-9_]+` — **rejecting `/`, `\`, `:`, `.`**. So a user cannot
  escape `$sharepath/tsearch_data/` via the basename. [verified-by-code]
- Rule-file encoding: the comment says the file is "UTF8" and
  `pg_do_encoding_conversion()` is called inside `tsearch_readline`
  (`:113-117`). Lines whose conversion fails are silently skipped
  via `PG_TRY` / `PG_CATCH` on `ERRCODE_UNTRANSLATABLE_CHARACTER`
  (`:278-294`). All other errors re-thrown. [verified-by-code]
- `unaccent_init` requires exactly one `Rules` parameter; rejects
  duplicates or any unrecognized parameter (`:349-372`).
  [verified-by-code]

## Notable internals

- Trie memory growth: each rule allocates up to `srclen` 2 KB nodes
  (`TrieChar[256]` = 8 bytes/entry * 256 = 2048 bytes per node) plus
  the replacement string. Worst case is the rule "abcdefghij…" (100
  bytes) consuming 100 * 2048 = 200 KB of nodes plus padding. The
  bundled `unaccent.rules` (~16 KB) materializes to a few MB of
  trie. **No upper bound** on rule count or trie size — adversarial
  rules file with N distinct prefixes consumes N * 2 KB.
  [ISSUE-DoS-low, verified-by-code]
- Rule-line state machine: 5 states + 2 error markers (`:134-145`).
  Quoted target supports `""` for literal quote. State `-1` for two
  strings, `-2` for unterminated quote — both → WARNING + skip, not
  ERROR. [verified-by-code]
- `findReplaceTo` (`:310-334`) does longest-match by walking the trie
  greedily, remembering the deepest match with `replaceTo`. Linear
  in `srclen`. [verified-by-code]
- `unaccent_dict` (`:438-502`) — 1-arg variant looks up the dict named
  `"unaccent"` in the function's own schema (`:454`). The 2-arg
  variant takes a `regdictionary` and calls
  `lookup_ts_dictionary_cache` (`:474`). [verified-by-code]

## Trust-boundary / Phase-D surface

- **Privilege to install a custom unaccent dictionary** — controlled
  by ordinary tsearch dictionary creation rules: `CREATE TEXT SEARCH
  DICTIONARY` requires superuser unless template is installed by
  superuser with permission. The Rules file is read from
  `$sharepath/tsearch_data/<basename>.rules` — placed there by a
  filesystem admin. **A non-superuser cannot drop a new file**, but
  CAN reference any existing `*.rules` file by basename. Combined
  with `dict_xsyn` and `dict_synonym` looking in the same dir, the
  attack model is "files an admin already placed". [from-comment,
  inferred]
- **Path traversal blocked** at `ts_utils.c:49` — basename limited to
  `[a-z0-9_]+`. Cannot reach files outside `tsearch_data/`.
  [verified-by-code]
- **Encoding-skip silently drops lines** — lines untranslatable in
  current locale are silently dropped (`:284-288`). A user who
  changes server encoding can have a dict suddenly behave
  differently. [from-comment]
- **Quoted-string parser** (`:200-219`) — `trglen` grows only when
  `*ptr` is processed; if the `for` loop's `ptrlen = pg_mblen_cstr`
  returns 0 (malformed encoding) the loop would infinite-spin, but
  the encoding-conversion already happened so `pg_mblen_cstr` should
  see valid mb chars. Defense in depth would assert `ptrlen > 0`.
  [ISSUE-robustness-low]
- **Trie memory unbounded** — see Notable internals. A rules file
  with 100 000 distinct prefixes of length 50 → ~10 GB trie. Admin
  has to ship the file, so attacker model requires filesystem write,
  but pg_upgrade preserving a malicious file would matter. [ISSUE-DoS-low]
- **`placeChar` duplicate-rule WARNING** is reported once per
  duplicate, not aggregated (`:72-74`). A maliciously-crafted file
  with 1 M duplicates would spam server log. [ISSUE-DoS-low]

## Cross-refs

- `source/src/backend/tsearch/ts_utils.c:33-61` —
  `get_tsearch_config_filename` enforces the basename allowlist.
- `source/src/backend/tsearch/dict_synonym.c`,
  `source/src/backend/tsearch/dict_thesaurus.c` — sibling
  dictionaries using the same `get_tsearch_config_filename` pattern.
- `source/contrib/dict_xsyn/dict_xsyn.c` — sibling with same trust
  surface.
- A12 / A13 corpus entries on tsearch dictionary loading.

<!-- issues:auto:begin -->
- [Issue register — `unaccent`](../../../issues/unaccent.md)
<!-- issues:auto:end -->

## Issues

- `[ISSUE-DoS-low: adversarial unaccent.rules file with many long
  prefixes grows the trie unboundedly — no MaxAllocSize check on
  total node count] (low)` —
  `source/contrib/unaccent/unaccent.c:56-89` (placeChar) +
  `:96-302` (initTrie)
- `[ISSUE-DoS-low: malformed rules file with N duplicates produces N
  WARNINGs, spamming the server log] (low)` —
  `source/contrib/unaccent/unaccent.c:71-74`
- `[ISSUE-correctness: lines untranslatable in current locale are
  silently skipped (PG_CATCH on ERRCODE_UNTRANSLATABLE_CHARACTER) —
  server-encoding change can change dictionary semantics without
  warning] (low)` — `source/contrib/unaccent/unaccent.c:278-294`
- `[ISSUE-robustness-low: parser loop assumes pg_mblen_cstr > 0;
  malformed encoding post-conversion could infinite-loop on
  ptrlen=0] (low)` — `source/contrib/unaccent/unaccent.c:157-159`
