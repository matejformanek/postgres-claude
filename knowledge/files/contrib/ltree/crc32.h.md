# crc32.h

## One-line summary

Two-line public header for `crc32.c`: declares `ltree_crc32_sz(buf, size)` and a `crc32(buf)` convenience macro for null-terminated input.

## Public API / entry points

- `extern unsigned int ltree_crc32_sz(const char *buf, int size)` (line 7) — see `crc32.c`.
- `#define crc32(buf) ltree_crc32_sz((buf), strlen(buf))` (line 10) — null-terminated wrapper.

## Key invariants

- INV-CRC32-MACRO-CLASH: the `crc32` macro at line 10 occupies a very generic name in the global namespace. Any `.c` file including `ltree.h`/`crc32.h` cannot use a local function or variable called `crc32`. Currently used only inside the ltree directory, but a transitive include via `ltree.h` could surprise. `[verified-by-code]`

## Notable internals

None — pure header.

## Trust boundary / Phase D surface

Nothing in this file. See `crc32.c.md` for the full picture.

## Cross-references

- `source/contrib/ltree/crc32.c` — the implementation.
- `source/contrib/ltree/ltree.h` — does NOT include `crc32.h` itself; callers include both.
- Callers including `crc32.h`: `ltree_io.c:11`, `ltxtquery_io.c:10`, `ltree_gist.c:11`, `_ltree_gist.c:13`.

<!-- issues:auto:begin -->
- [Issue register — `ltree`](../../../issues/ltree.md)
<!-- issues:auto:end -->

## Issues spotted

- [ISSUE-API-shape: the `crc32(buf)` macro shadows any function/variable named `crc32` in callers' scope (line 10). Trivial in current usage but a footgun if someone adds a generic `crc32` helper to a shared header. (nit)] — `source/contrib/ltree/crc32.h:10`.
- [ISSUE-doc: `ltree_crc32_sz` is declared without a header-side comment explaining the `LOWER_NODE` two-path behavior. A reader of just this header would not know that the CRC is case-fold-aware on most builds and byte-literal on MSVC. (nit)] — `source/contrib/ltree/crc32.h:6-7`.

## Synthesized by
<!-- backlinks:auto -->
- [subsystems/contrib-ltree.md](../../../subsystems/contrib-ltree.md)
