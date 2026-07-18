---
path: src/port/pg_localeconv_r.c
anchor_sha: e18b0cb7344
loc: 368
depth: read
---

# src/port/pg_localeconv_r.c

## Purpose

Thread-safe replacement for POSIX `localeconv(3)`, which is notoriously
multithreading-hostile (it returns a pointer to a static `struct lconv`
that any concurrent call can clobber). PG needs locale-specific
number/currency separators for `to_char`/`numeric_out`/money types, but
must be safe to call from any backend without disturbing global locale
state. This file implements one shared API over four mutually incompatible
OS interfaces. `[verified-by-code]` `[from-comment]`

## Public symbols

| Symbol | Site | Notes |
|---|---|---|
| `int pg_localeconv_r(const char *lc_monetary, const char *lc_numeric, struct lconv *output)` | `pg_localeconv_r.c:231` | Fills caller's lconv; returns 0 on success, -1 with errno on failure |
| `void pg_localeconv_free(struct lconv *lconv)` | `:104` | Free the strdup'd string members |

## Internal landmarks

Four platform arms in `pg_localeconv_r`, picked by `#ifdef` cascade:

1. **Glibc with `MON_THOUSANDS_SEP` extension** (`:111-148`,
   `pg_localeconv_from_langinfo`) — uses thread-safe `nl_langinfo_l()` for
   each lconv field. Driven by the `table[]` array (`:63-85`) that maps each
   `struct lconv` member to (category, nl_item, type) tuples. `[verified-by-code]`
2. **macOS / BSD with `localeconv_l()`** (`:325`) — creates two `locale_t`
   objects (one each for LC_MONETARY/LC_NUMERIC) via `newlocale(LC_ALL_MASK, ...)`,
   calls `localeconv_l()` per category, frees the locales.
3. **POSIX fallback** (`:337-361`) — `uselocale()` + plain `localeconv()`
   protected by a `pthread_mutex_t` "Big Lock". The Big Lock is a static
   `PTHREAD_MUTEX_INITIALIZER`; it only protects calls **inside this
   function**, not third-party libraries elsewhere in the process that
   might also call `localeconv()` and clobber its buffer. `[from-comment]`
4. **Windows** (`:235-296`) — `_configthreadlocale(_ENABLE_PER_THREAD_LOCALE)`
   puts `setlocale()` into thread-local mode, then uses ordinary
   `setlocale`/`localeconv`. Wide-string `_wsetlocale` is used to capture and
   restore originals so non-ASCII locale names survive intermediate encoding
   changes. `[from-comment]`

## Invariants & gotchas

- **POSIX is undefined when LC_NUMERIC/LC_MONETARY codeset disagrees with
  LC_CTYPE.** All four arms set LC_ALL to the target locale for each
  category to dodge this; the resulting struct's "decimal_point",
  "thousands_sep", "grouping" are encoded in LC_NUMERIC's codeset and the
  rest in LC_MONETARY's. `[from-comment]`
- **String members are heap-allocated (strdup'd).** Caller must call
  `pg_localeconv_free()` on success or leak. Character members live in the
  struct itself, no free needed.
- The Big Lock fallback's `pthread_mutex_t` is process-global — never call
  this function from a signal handler, and don't hold any other lock
  pre-this call from a different thread.
- `pg_localeconv_free` only frees the **string fields**. Mistakenly calling
  it on an output from the WIN32 arm is fine because the WIN32 arm also
  strdup's via `pg_localeconv_copy_members`. `[verified-by-code]`
- On the WIN32 arm, on early-failure paths we restore LC_CTYPE,
  LC_MONETARY, LC_NUMERIC individually using captured wide strings — this
  is needed because the intermediate `setlocale(LC_ALL, ...)` calls could
  fail mid-way, and a partial unwind via narrow strings could lose info
  in non-ASCII locale names. `[from-comment]`

## Cross-refs

- `source/src/backend/utils/adt/pg_locale.c` — primary caller; consumes the
  output to drive `to_char`, money type, numeric formatting.
- `source/src/include/port.h` — prototype.
- `knowledge/idioms/` — thread-safety conventions in `libpgport`.

## Synthesized by
<!-- backlinks:auto -->
- [subsystems/port.md](../../../subsystems/port.md)
