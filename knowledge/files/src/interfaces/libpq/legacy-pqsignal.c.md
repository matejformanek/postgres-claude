# legacy-pqsignal.c

- **Source path:** `source/src/interfaces/libpq/legacy-pqsignal.c`
- **Last verified commit:** `4b0bf0788b0`
- **Size:** 65 lines

## Purpose

> "This version of pqsignal() exists only because pre-9.3 releases of libpq exported pqsignal(), and some old client programs still depend on that. (Since 9.3, clients are supposed to get it from libpgport instead.)" [lines 22-25, from-comment]
>
> "libpq itself does not use this, nor does anything else in our code." [line 31, from-comment]

A pure ABI compatibility shim. Exports a `pqsignal` symbol from `libpq.so` so old binaries (linked against libpq < 9.3) still resolve. New code is meant to call `pqsignal_fe` (from `libpgport`) via the `#define`s in `src/include/port.h`.

## Semantics

Frozen at 9.2 behavior. The comment explicitly notes: "this has different behavior for SIGALRM than the version in src/port/pqsignal.c" (lines 28-29) — the legacy version refuses to set `SA_RESTART` for SIGALRM, the modern one does it differently.

Implementation:

- Non-Windows (lines 47-61): `sigaction` with `SA_RESTART` set for everything except SIGALRM, plus `SA_NOCLDSTOP` for SIGCHLD if defined.
- Windows (line 63): just `signal(signo, func)` — Win32 has no `sigaction`.

## Header-namespace trick

`src/include/port.h` does `#define pqsignal pqsignal_fe` (or `_be`) so in-tree calls go to the modern version. This file `#undef`s `pqsignal` at line 38 and forward-declares a plain `pqsignal` symbol so the linker exports the legacy name. The signature uses a local `pqsigfunc_legacy` typedef to avoid clashing with `port.h`'s `pqsigfunc`. [verified-by-code]

## Phase D notes

[ISSUE-legacy-pqsignal-001 — maybe] PG 9.3 was released 2013-09. Programs linked against pre-9.3 libpq are now 13+ years old. This file is a candidate for retirement at the next libpq SONAME bump, but no policy doc names a timeline.

## Tally

`[verified-by-code]=1 [from-comment]=3 [maybe]=1`
