---
path: src/port/strlcat.c
anchor_sha: 4b0bf0788b066a4ca1d4f959566678e44ec93422
loc: 61
depth: deep
---

# src/port/strlcat.c

## Purpose

Provides `strlcat(char *dst, const char *src, size_t siz)` — OpenBSD's bounded
string concatenation. Appends `src` to `dst`, where `siz` is the **full size of
the `dst` buffer** (not the space remaining — the key difference from
`strncat`). Copies at most `siz-1` total bytes and always NUL-terminates unless
`siz <= strlen(dst)` (i.e. `dst` was already unterminated within the window).
Returns `strlen(src) + MIN(siz, strlen(initial dst))`; truncation iff
`retval >= siz`. Compiled into libpgport only where libc lacks it.
`[verified-by-code]`

## Public symbols

| Symbol | Site | Notes |
|---|---|---|
| `size_t strlcat(char *dst, const char *src, size_t siz)` | `strlcat.c:34` | `siz` is total buffer size; returns intended length |

## Internal landmarks

- Find end of `dst` within the window (`strlcat.c:42-45`) — walks at most `siz`
  bytes, computing `dlen` (existing length) and `n` (space remaining).
- Early-out (`:47-48`) — if no room remains, returns `dlen + strlen(s)` (the
  length the result *would* have been) without writing.
- Append loop (`:49-57`) — copies `src` while leaving room for the terminator.
- Terminate (`:58`) and return intended length (`:60`).

## Invariants & gotchas

- **`siz` is the whole buffer**, matching `strlcpy`'s convention and *opposite*
  to `strncat`'s "space remaining" argument. Passing the remaining space is the
  classic misuse and produces overruns; PG code consistently passes
  `sizeof(buf)`.
- If `dst` is not NUL-terminated within the first `siz` bytes, the function
  cannot find the end and returns `siz + strlen(src)` without appending — the
  truncation signal still fires (`retval >= siz`).

## Cross-refs

- `knowledge/files/src/port/strlcpy.c.md` — sibling bounded copy.

## Synthesized by
<!-- backlinks:auto -->
- [subsystems/port.md](../../../subsystems/port.md)
