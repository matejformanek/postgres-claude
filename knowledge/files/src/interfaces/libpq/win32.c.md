# win32.c

- **Source path:** `source/src/interfaces/libpq/win32.c`
- **Last verified commit:** `4b0bf0788b0`
- **Size:** 321 lines

## Purpose

> "Win32 support functions. Contains table and functions for looking up win32 socket error descriptions. But will/may contain other win32 helper functions for libpq." [lines 9-13, from-comment]

In practice **only** Winsock error-code translation lives here. Provides `winsock_strerror()` which `libpq-int.h` wires up as `SOCK_STRERROR` on Windows.

## WSError lookup table (lines 43-209)

Static array `WSErrors[]` mapping `WSAE*` Winsock error codes to English description strings. Roughly 50 entries covering the standard Winsock 2 error set: `WSAEINTR`, `WSAEBADF`, `WSAEACCES`, `WSAEFAULT`, `WSAEINVAL`, `WSAEMFILE`, `WSAEWOULDBLOCK`, `WSAEINPROGRESS`, `WSAEALREADY`, `WSAENOTSOCK`, `WSAEDESTADDRREQ`, `WSAEMSGSIZE`, `WSAEPROTOTYPE`, `WSAENOPROTOOPT`, `WSAEPROTONOSUPPORT`, `WSAESOCKTNOSUPPORT`, `WSAEOPNOTSUPP`, `WSAEPFNOSUPPORT`, `WSAEAFNOSUPPORT`, `WSAEADDRINUSE`, `WSAEADDRNOTAVAIL`, `WSAENETDOWN`, `WSAENETUNREACH`, `WSAENETRESET`, `WSAECONNABORTED`, `WSAECONNRESET`, `WSAENOBUFS`, `WSAEISCONN`, `WSAENOTCONN`, `WSAESHUTDOWN`, `WSAETOOMANYREFS`, `WSAETIMEDOUT`, `WSAECONNREFUSED`, `WSAELOOP`, `WSAENAMETOOLONG`, `WSAEHOSTDOWN`, `WSAEHOSTUNREACH`, `WSAENOTEMPTY`, `WSAEPROCLIM`, `WSAEUSERS`, `WSAEDQUOT`, `WSAESTALE`, `WSAEREMOTE`, `WSASYSNOTREADY`, `WSAVERNOTSUPPORTED`, `WSANOTINITIALISED`, `WSAEDISCON`, `WSAHOST_NOT_FOUND`, `WSATRY_AGAIN`, `WSANO_RECOVERY`, `WSANO_DATA`.

Origin attribution: "from the Frambak Bakfram LGSOCKET library guys who in turn took them from the Winsock FAQ." [line 15-16, from-comment]

`LookupWSErrorMessage` (lines 217-231) — linear scan; comment dryly: "linear but who cares, at this moment we're already in pain :)". [from-comment]

## DLL fallback chain (lines 234-266, `dlls[]`)

If the static table misses, `winsock_strerror` tries `FormatMessage` against a chain of system DLLs loaded via `LoadLibraryEx(..., LOAD_LIBRARY_AS_DATAFILE)`:

`netmsg.dll`, `winsock.dll`, `ws2_32.dll`, `wsock32n.dll`, `mswsock.dll`, `ws2help.dll`, `ws2thk.dll`, plus a final NULL entry (`{0, 0, 1}`) marking "no DLL, but always considered loaded" so `FormatMessage` falls back to `FORMAT_MESSAGE_FROM_SYSTEM` only. Each DLL is loaded at most once (the `loaded` flag at line 289 prevents repeated attempts).

## `winsock_strerror` (lines 276-320)

Strategy:

1. Lookup in the static table.
2. On miss, walk `dlls[]`, lazily loading each, and try `FormatMessage` with `FORMAT_MESSAGE_FROM_SYSTEM | FORMAT_MESSAGE_IGNORE_INSERTS` + `FORMAT_MESSAGE_FROM_HMODULE` if a DLL handle is present.
3. Forces English language: `MAKELANGID(LANG_ENGLISH, SUBLANG_DEFAULT)`.
4. If everything fails: `sprintf` an `unrecognized socket error: 0x%08X/%d` line (translatable via `libpq_gettext`).
5. On success, **always appends** the hex/decimal error code via `sprintf(strerrbuf + offs, " (0x%08X/%d)", ...)` (lines 313-317). Reserves 64 bytes at the tail for the appended code by passing `buflen - 64` to FormatMessage (line 305) and capping `offs` similarly. [verified-by-code]

## Phase D notes

[ISSUE-win32-c-001 — maybe] No bounds check on `strcpy(dest, e->description)` (line 226). The static table strings are short literals so this is safe today, but the contract with callers (`SOCK_STRERROR` macro) doesn't pass `buflen` into `LookupWSErrorMessage` — if someone adds a longer entry, `dest` overflows. The bounds discipline only kicks in for the FormatMessage path.

[ISSUE-win32-c-002 — maybe] DLL handles in the static `dlls[]` table are **never freed**. `LoadLibraryEx` results are cached for the process lifetime. Fine for a typical client; a long-lived host that periodically loads/unloads libpq (rare) keeps these DLL refs.

[ISSUE-win32-c-003 — maybe] Two of the listed fallback DLLs (`wsock32n.dll`, `ws2thk.dll`) don't exist on modern Windows (>= Vista). The lazy-loader silently skips them on `LoadLibraryEx` failure, so it's a no-op cost. Could be pruned.

[ISSUE-win32-c-004 — maybe] `MAKELANGID(LANG_ENGLISH, SUBLANG_DEFAULT)` forces English output regardless of locale, then the wrapper passes the result through `libpq_gettext`. Result: error messages mix English Windows text with translated PG prefix text on non-English systems. Probably intentional (matches the PG style for error-context strings) but worth documenting.

## Tally

`[verified-by-code]=4 [from-comment]=2 [maybe]=4`
