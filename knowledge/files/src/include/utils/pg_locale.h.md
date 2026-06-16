# `utils/pg_locale.h` — pg_locale_t and the collation/ctype provider abstraction

**Verified against source pin `4b0bf0788b0`** (path:
`source/src/include/utils/pg_locale.h`)

## Role

The big locale header. Defines `pg_locale_t` (discriminated union over
libc / ICU / builtin providers), the vtables `collate_methods` and
`ctype_methods` each provider must implement, and the
`pg_str{lower,title,upper,fold}` / `pg_str{coll,xfrm}` / `pg_isw*` /
`pg_tow*` wrappers that the rest of the backend (citext, pg_trgm,
text comparison, LIKE) calls. Also publishes the LC_* category GUCs
and the localised day/month name cache.

## Public API

- `LOCALE_NAME_BUFLEN = 128` — `source/src/include/utils/pg_locale.h:18`.
- `UNICODE_CASEMAP_LEN = 3`, `UNICODE_CASEMAP_BUFSZ = 3 * MAX_MULTIBYTE_CHAR_LEN`
  — `:31-32`. Tied to Unicode 16.0.0 §5.18.2.
- GUC externs: `locale_messages`, `locale_monetary`, `locale_numeric`,
  `locale_time`, `icu_validation_level` — `:35-39`.
- Localised name caches: `localized_abbrev_days[]`, `localized_full_days[]`,
  `localized_abbrev_months[]`, `localized_full_months[]` — `:42-45`.
- `pg_locale_t = pg_locale_struct *` opaque-ish pointer — `:60`.
- `struct collate_methods` — `:63-96`. Required ops: `strncoll`, `strnxfrm`;
  optional: `strxfrm_prefix`. Flag `strxfrm_is_safe` says whether `strnxfrm`
  output is trustworthy for equality.
- `struct ctype_methods` — `:98-131`. Case mapping (`strlower/title/upper/fold`,
  `downcase_ident`), `wc_is*` predicates, `wc_to{upper,lower}`.
- `struct pg_locale_struct` — `:147-175`: flags (`deterministic`,
  `collate_is_c`, `ctype_is_c`, `is_default`), pointers to method
  vtables, plus a union over builtin / libc `locale_t` / ICU `UCollator+
  UCaseMap+locale_t`.
- `init_database_collation`, `pg_database_locale`,
  `pg_newlocale_from_collation(Oid collid)` — `:177-179`.
- Wrappers: `pg_strlower/title/upper/fold`, `pg_downcase_ident`,
  `pg_strcoll`, `pg_strncoll`, `pg_strxfrm_enabled`, `pg_strxfrm`,
  `pg_strnxfrm`, `pg_strxfrm_prefix*`, `pg_strnxfrm_prefix` — `:183-209`.
- Per-codepoint: `pg_iswdigit/alpha/alnum/upper/lower/graph/print/punct/
  space/xdigit/cased`, `pg_towupper`, `pg_towlower` — `:211-223`.
- Builtin/ICU validation: `builtin_locale_encoding`,
  `builtin_validate_locale`, `icu_validate_locale`, `icu_language_tag`,
  `report_newlocale_failure` — `:227-231`.
- `wchar2char` — `:234`. Note: takes libc `wchar_t`, not `pg_wchar`.

## Invariants

- `pg_locale_t` is allocated once per collation OID and cached for the
  process lifetime; the catalog never reloads a collation entry during
  a session. [inferred from API; `pg_newlocale_from_collation` is the only
  factory]
- `collate_is_c` / `ctype_is_c` flags MUST NOT report false negatives.
  Code like `wchar2char` short-circuits when they are true.
  [from-comment, `:144-145`]
- For the default collation, separate static cache variables exist; the
  pg_collation catalog row is not consulted. [from-comment, `:140-143`]
- `strxfrm_is_safe == false` means the planner is allowed to call the
  method for estimation but the executor must NOT trust its output for
  equality. [from-comment, `:89-95`]
- Builtin provider: `casemap_full` flag indicates whether full Unicode
  case mapping (1→N codepoints) is in effect for this locale. [verified-by-
  code, `:161-163`]
- ICU members exist only under `#ifdef USE_ICU` — `:165-173`. A non-ICU
  build cannot dispatch to ICU provider; collation lookups on ICU rows
  will error in `pg_newlocale_from_collation`. [inferred]

## Notable internals

- The discriminated-union layout (`:157-174`) is what lets a single
  `pg_locale_t` flow through the entire backend without branching on
  provider at every call site — the function-pointer indirection through
  `collate` / `ctype` does the dispatch.
- `wchar2char` comment "converts from libc's wchar_t, *not* pg_wchar"
  (`:233`) is a load-bearing distinction; mixing them silently corrupts
  multibyte text.

## Trust-boundary / Phase D surface

- **A7 echo**: the `pg_strlower` / `pg_strtitle` / `pg_strupper` etc. take
  `size_t srclen` but no MaxAllocSize check at this layer; callers
  (`formatting.c`, citext) supply user input lengths. The ICU casemap
  expansion is up to 3x (`UNICODE_CASEMAP_LEN`), so a `srclen` of 700MB
  with full casemap can blow past MaxAllocSize. [ISSUE-resource:
  pg_str{lower,upper,fold} have no input-length cap; multiplies up to 3x
  via UNICODE_CASEMAP_LEN (likely)]
- `pg_newlocale_from_collation(Oid collid)` is the
  catalog→pg_locale_t resolver — it is the ONLY validation point for
  collation correctness. If callers cache `pg_locale_t` themselves
  (citext does — A13 finding) they can outlive
  `pg_collation` invalidations. [ISSUE-correctness: pg_locale_t caching
  outside this module bypasses invalidation events (likely)]
- `default_collation_oid` mentioned in comment (`:142`) but not exposed as
  a header symbol; nonetheless the DEFAULT collation has a special
  cache path. A14 pg_trgm pins `DEFAULT_COLLATION_OID` literally;
  changes to that OID would silently break pg_trgm. [ISSUE-correctness:
  DEFAULT_COLLATION_OID is a magic literal pinned in callers
  (cross-ref A14) (maybe)]
- `icu_validation_level` GUC is `PGC_USERSET` — anyone can set it to
  `warning` and bypass strict locale validation on CREATE COLLATION /
  CREATE DATABASE. [ISSUE-security: icu_validation_level downgrades
  bypass validation at PGC_USERSET (maybe)]
- `pg_perm_setlocale` (`:48`) wraps libc `setlocale()` which is **process-
  global, not thread-safe, and not reentrant**. Any future move toward
  threading inside the backend will require ripping this out. [ISSUE-api-shape:
  pg_perm_setlocale bakes a process-global libc dependency into the locale
  API (nit)]
- `strxfrm_is_safe == false` documentation says "incorrect results are
  acceptable" for the planner (`:91-93`). This is a load-bearing trust
  boundary — a careless refactor that uses the planner-path output for
  equality would silently corrupt results. [ISSUE-correctness:
  strxfrm_is_safe semantics rely on caller discipline (maybe)]

## Cross-refs

- `knowledge/files/src/include/utils/pg_locale_c.h.md` — C/POSIX fast-path
  bypass.
- `knowledge/files/src/include/utils/formatting.h.md` — uses
  `pg_str{lower,upper,...}` via `str_tolower` etc.
- A7 (pg_locale_icu input-length finding), A13 (citext default-collation
  asymmetry), A14 (pg_trgm pinned `DEFAULT_COLLATION_OID`).

<!-- issues:auto:begin -->
- [Issue register — `include-utils`](../../../../issues/include-utils.md)
<!-- issues:auto:end -->

## Issues

1. [ISSUE-resource: `pg_str{lower,upper,fold,title}` accept caller-supplied
   `srclen` with no MaxAllocSize check; ICU casemap multiplies up to 3x
   (likely)] — `source/src/include/utils/pg_locale.h:183-194`.
2. [ISSUE-correctness: `pg_locale_t` cached by external modules (citext)
   outlives pg_collation invalidations (likely)] —
   `source/src/include/utils/pg_locale.h:179`.
3. [ISSUE-security: `icu_validation_level` is PGC_USERSET; downgrade
   bypasses CREATE COLLATION / CREATE DATABASE validation (maybe)] —
   `source/src/include/utils/pg_locale.h:39`.
4. [ISSUE-correctness: `DEFAULT_COLLATION_OID` is pinned by callers (A14
   pg_trgm) and the cache here has a separate static path (maybe)] —
   `source/src/include/utils/pg_locale.h:140-143`.
5. [ISSUE-api-shape: `pg_perm_setlocale` baked into a process-global,
   non-thread-safe libc call (nit)] —
   `source/src/include/utils/pg_locale.h:48`.
6. [ISSUE-correctness: `strxfrm_is_safe` semantics rely on caller discipline
   to not reuse planner-path output for equality (maybe)] —
   `source/src/include/utils/pg_locale.h:89-95`.
