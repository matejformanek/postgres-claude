# hstore_subs.c

## One-line summary

Subscripting handler (`hstore_subscript_handler`) for hstore allowing
`hstore_col['key']` fetch and `UPDATE t SET hstore_col['key'] = 'val'`
assignment; supports a single text subscript (no slicing, no nested
assignment), returns text (or NULL for missing keys), and merges
assignments via the same sort-merge logic as `hstore_concat`.

Source pin: `4b0bf0788b0`.

## Public API / entry points

- `hstore_subscript_handler(internal) -> internal` — returns a static
  `SubscriptRoutines` struct with `.transform`, `.exec_setup`,
  `.fetch_strict=true`, `.fetch_leakproof=true`, `.store_leakproof=false`
  (`hstore_subs.c:285-298`) [verified-by-code].
- Three static callbacks: `hstore_subscript_transform`,
  `hstore_subscript_fetch`, `hstore_subscript_assign`
  (`hstore_subs.c:42-259`) [verified-by-code].

## Key invariants

- Single subscript only; `isSlice` and `list_length != 1` are both hard
  errors (`hstore_subs.c:53-58`) [verified-by-code].
- Subscript expression is coerced to `TEXTOID` via
  `coerce_to_target_type(..., COERCION_ASSIGNMENT, COERCE_IMPLICIT_CAST)`
  (`hstore_subs.c:66-71`) [verified-by-code]. Failure ⇒
  `ERRCODE_DATATYPE_MISMATCH`.
- Result type is always `TEXTOID` with typmod `-1`
  (`hstore_subs.c:83-84`) [verified-by-code].
- Fetch: `fetch_strict = true` ⇒ NULL container short-circuits to NULL
  result by the executor BEFORE calling fetch (`hstore_subs.c:107`,
  `292-293`) [verified-by-code, from-comment].
- Fetch returns NULL for both "key not found" and "value is null"
  (`hstore_subs.c:125-129`) [verified-by-code].
- Assign: NULL subscript is forbidden (`hstore_subs.c:153-157`)
  [verified-by-code] — `ERRCODE_NULL_VALUE_NOT_ALLOWED`. NULL replacement
  value IS allowed (stores `isnull=true` pair).
- Assign on a NULL container: builds a 1-element hstore
  (`hstore_subs.c:181-185`) [verified-by-code].
- Assign on a non-NULL container: full sort-merge with the existing
  hstore (`hstore_subs.c:186-255`) [verified-by-code], structurally
  identical to `hstore_concat` in `hstore_op.c`.

## Notable internals

### Fetch path (`hstore_subs.c:94-135`)

Effectively `hstore_fetchval` inlined: detoast → `hstoreFindKey` →
return as text. Re-uses `hstoreFindKey` (`hstore_op.c:35-70`) binary
search over keylen-then-key sorted entries.

### Assign path: explicit growth math

`vsize = CALCDATASIZE(s1count + 1, VARSIZE(hs) + p.keylen + p.vallen);`
(`hstore_subs.c:205`) [verified-by-code]. This OVER-allocates: it adds
the key + value lengths to `VARSIZE(hs)` (which already includes the
HStore header + entry array + string buffer), then re-applies
`CALCDATASIZE` which adds another header + (s1count+1)*2 HEntries. So
the actual allocation is `header + 2*(s1count+1)*HEntry + VARSIZE(hs) +
keylen + vallen` — over-large by roughly `header + 2*s1count*HEntry`.
The extra is reclaimed when `HS_FINALIZE` re-sets the varlena length
based on the actual final layout. Wasteful but safe.

### Merge loop (`hstore_subs.c:215-252`)

Sort-merge with the single new pair: at each step, compare current
existing key vs new key by (keylen, memcmp). If new key is ≤, write the
new pair first (and skip the existing if equal, i.e. overwrite); else
copy the existing pair. Exactly mirrors `hstore_concat`'s logic.

## Trust boundary / Phase D surface

### Subscripting expression-injection (PROMPT-SPECIFIC)

Per task prompt: `hstore['key' || user_input]`; key normalization?

Looking at fetch: `key = DatumGetTextPP(sbsrefstate->upperindex[0])` and
the lookup uses raw `VARDATA_ANY(key), VARSIZE_ANY_EXHDR(key)` against
`hstoreFindKey` (`hstore_subs.c:118-123`) [verified-by-code]. **No
key normalization.** The fetch is a byte-for-byte memcmp inside
`hstoreFindKey`. So `hstore['admin' || E'\x00malicious']` would search
for the literal `admin\0malicious` (7+1+9 bytes including NUL), NOT
`admin`. This is the correct behavior — hstore keys are arbitrary byte
strings, and embedded NULs are legitimate (although `hstore_in` text
syntax can't produce them, `hstore_recv` binary can).

Assignment side: `hstoreCheckKeyLen` is applied
(`hstore_subs.c:165, 177`) [verified-by-code], so length is bounded.
Embedded NULs in keys ARE allowed at assignment (no validation against
them).

No SQL-injection-style concern here — the subscripting AST node carries
the raw text Datum, not a string interpolated into any parser.
`[verified-by-code]`. The "expression-injection" framing from the task
prompt looks like a false-alarm category given how subscripting works.

### `fetch_leakproof = true`, `store_leakproof = false`

`hstore_subs.c:293-294` [verified-by-code]. The comments explain:
- `fetch_leakproof = true`: fetch returns NULL on bad subscript (no
  ereport at runtime). Verified: the only ereport in the fetch path is
  in `transform` which runs at parse time, not at execution time.
- `store_leakproof = false`: assignment CAN ereport
  (`hstoreCheckKeyLen`, `hstoreCheckValLen`, NULL-subscript).

This affects security-barrier views and RLS: a fetch can appear in a
WHERE clause without leaking row contents via error messages, but
assignment cannot.

### `hstoreCheckKeyLen` on subscript assignment

`hstore_subs.c:165` checks `VARSIZE_ANY_EXHDR(key)` against
`HSTORE_MAX_KEY_LEN`. Good. Equivalently for value at line 177. Same
1 GiB cap as everywhere else.

### Memory bound on huge subscript assignment

`palloc(vsize)` (`hstore_subs.c:206`) where `vsize` is over-estimated as
described above. Both the new key and the existing hstore are bounded
by varlena's 1 GB cap, so `vsize ≤ ~2.something GB`. `palloc` (and
`MaxAllocSize = 1 GB`) will reject before reaching the OS allocator.
`[ISSUE-memory: subscript assignment overestimates allocation by
~header+entries*2; harmless but could mean an in-range existing hstore +
modest new key triggers MaxAllocSize rejection that hstore_concat would
not (nit)]`.

### Subscript that finds a null value

If `HSTORE_VALISNULL(entries, idx)` is true at fetch, return NULL
(`hstore_subs.c:125-129`). This is indistinguishable from "key not
found", which is intentional: there's no way to ask "is this key
present with value NULL" via subscripting (use `defined(hs, 'k')` or
`hs ? 'k'` instead).

## Cross-references

- `executor/execExpr.h`, `nodes/subscripting.h`,
  `parser/parse_coerce.h`, `parser/parse_expr.h` — subscripting framework.
- `hstore_op.c.md` — `hstore_concat` (the merge pattern this file
  duplicates) and `hstore_fetchval` (the lookup this file inlines).
- `utils/adt/jsonbsubs.c` — sibling jsonb subscripting handler for
  comparison (jsonb supports nested paths; hstore does not).

## Issues spotted

- `[ISSUE-memory: subscript assignment overestimates allocation by
  header+entries*2; harmless on its own but reduces effective MaxAllocSize
  budget (nit)]`
- `[ISSUE-api-shape: fetch returns NULL for both "key not found" and "key
  present with null value"; users must use `defined()`/`?` to distinguish.
  This is documented behavior but worth flagging for any audit that
  expected indistinguishable NULL semantics (nit)]`
- `[ISSUE-documentation: file-header comment says "the result of
  subscripting an hstore is just a text string (the value for the key)"
  but doesn't mention that null hstore values return SQL NULL not empty
  text — minor doc gap (nit)]`
