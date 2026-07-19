---
path: src/port/strsep.c
anchor_sha: e18b0cb7344
loc: 78
depth: read
---

# src/port/strsep.c

## Purpose

Provides the BSD `strsep(char **stringp, const char *delim)` token
splitter for platforms whose libc lacks it. Direct port of the OpenBSD
implementation (CVS ID retained at `strsep.c:4`). Compiled only when
`configure`/meson can't find a native `strsep`. `[verified-by-code]`

Unlike `strtok`, `strsep`:
- Doesn't keep internal state — safe across threads, reentrant.
- Returns empty tokens when delimiters are adjacent (e.g., parsing
  `"a::b"` with `':'` returns `"a"`, `""`, `"b"`).
- Modifies the source string in place (writes `\0` over each delimiter).

PG uses it for delimited-string parsing in various ad-hoc spots
(notably some libpq option parsing). The empty-token semantics are
load-bearing in callers — switching to `strtok` would silently drop
empty fields.

## Public symbols

| Symbol | Site | Notes |
|---|---|---|
| `char *strsep(char **stringp, const char *delim)` | `strsep.c:49` | Returns next token, or `NULL` if `*stringp` was already `NULL` |

## Internal landmarks

- The inner loop (`strsep.c:60-76`) is a textbook two-loop scanner:
  - outer loop walks the source string one char at a time;
  - inner loop checks the current char against every delim;
  - on match, writes `\0` (unless the char was already `\0`), advances
    `*stringp` past the delimiter, returns the token start.
- The `\0`-terminator-as-delim trick (`strsep.c:67-72`): the loop also
  treats `\0` as a match against any delim list (because the inner
  loop's `do { ... } while (sc != 0)` always re-tests the `\0`-byte of
  `delim`). On `\0` match, `*stringp` is set to `NULL`, signaling "no
  more tokens" on next call.

## Invariants & gotchas

- **Mutates the input string.** Pass a writable buffer; a string
  literal will segfault.
- **`stringp` is updated in place.** Caller must re-pass the same
  `char **`, not the original `char *`.
- Empty tokens are real — `strsep("a,,b", ",")` yields `"a"`, `""`,
  `"b"`. Don't replace with `strtok` thoughtlessly.
- `delim` is treated as a *set* of single-byte delimiters, not as a
  substring. `strsep(s, "ab")` splits on either `a` or `b`.
- Multi-byte / UTF-8 safe only if the delimiter set is pure ASCII — a
  UTF-8 continuation byte in `delim` would split mid-character.

## Cross-refs

- `knowledge/files/src/port/strerror.c.md` — sibling "always compiled
  on platforms that lack X" pattern.
- BSD man page `strsep(3)` — authoritative semantics.

## Synthesized by
<!-- backlinks:auto -->
- [subsystems/port.md](../../../subsystems/port.md)
