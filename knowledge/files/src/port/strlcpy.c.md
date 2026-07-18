---
path: src/port/strlcpy.c
anchor_sha: 4b0bf0788b066a4ca1d4f959566678e44ec93422
loc: 71
depth: deep
---

# src/port/strlcpy.c

## Purpose

Provides `strlcpy(char *dst, const char *src, size_t siz)` — OpenBSD's
"strncpy done right". Copies at most `siz-1` bytes from `src` and **always**
NUL-terminates `dst` (unless `siz == 0`). Returns `strlen(src)`; the caller
detects truncation by testing `retval >= siz`. Compiled into libpgport only on
platforms that don't provide a native `strlcpy`. This is the bounded string
copy used pervasively across the backend and frontend in preference to
`strncpy` (which does not NUL-terminate on truncation) and `strcpy` (which is
unbounded). `[verified-by-code]`

## Public symbols

| Symbol | Site | Notes |
|---|---|---|
| `size_t strlcpy(char *dst, const char *src, size_t siz)` | `strlcpy.c:45` | Returns source length; truncation iff retval >= siz |

## Internal landmarks

- Copy loop (`strlcpy.c:52-59`) — copies until either `siz-1` bytes are written
  or the source NUL is hit.
- Truncation tail (`:62-68`) — if room ran out, writes the terminating NUL (if
  `siz != 0`) and then walks the rest of `src` purely to compute its full
  length for the return value.
- Return (`:70`) — `s - src - 1`, the source length excluding the NUL.

## Invariants & gotchas

- **Always NUL-terminates** except the degenerate `siz == 0` case (in which it
  writes nothing and returns the source length). This is the property that
  makes it safer than `strncpy`.
- The return value is `strlen(src)`, **not** the number of bytes copied. Code
  that wants "did it fit" must compare `>= siz`.
- Walking the rest of `src` on truncation costs an extra `strlen` over the
  unread tail — irrelevant for the short identifiers/paths it is used on.

## Cross-refs

- `knowledge/files/src/port/strlcat.c.md` — sibling bounded concatenation.
- `knowledge/files/src/port/tar.c.md` — a representative `strlcpy` consumer
  (tar header field fills).

## Synthesized by
<!-- backlinks:auto -->
- [subsystems/port.md](../../../subsystems/port.md)
