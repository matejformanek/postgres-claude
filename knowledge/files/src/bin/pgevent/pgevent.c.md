# `src/bin/pgevent/pgevent.c`

- **Last verified commit:** `e18b0cb7344`
- **Lines:** ~160
- **Source:** `source/src/bin/pgevent/pgevent.c`

A tiny Windows DLL that registers PostgreSQL as a Windows Event Log
source so that `ereport()` output flowing through `write_eventlog()`
(in the postmaster on Windows) has a registered message file to point
at. Implements the standard self-registration ABI (`DllRegisterServer` /
`DllUnregisterServer` / `DllInstall` / `DllMain`), invoked by
`regsvr32`. [verified-by-code]

## API / entry points

- `DllInstall(BOOL bInstall, LPCWSTR pszCmdLine)` — `regsvr32 /i:NAME`
  hook. Copies `pszCmdLine` (the wide-char event-source name) into
  `event_source[]`, then — only on install — calls
  `DllRegisterServer()` to actually do the work. The header comment
  (lines 44-54) documents the "ugly hack" needed because `regsvr32 /i`
  invokes `DllRegisterServer` BEFORE `DllInstall` during install, but
  in the reverse order during uninstall. The recommended invocation is
  `regsvr32 /n /i` (the `/n` suppresses the implicit
  `DllRegisterServer` call). [from-comment]
- `DllRegisterServer()` — `GetModuleFileName` to find own DLL path,
  then `RegCreateKey` under
  `HKLM\SYSTEM\CurrentControlSet\Services\EventLog\Application\<event_source>`
  with `EventMessageFile = <dll path>` and `TypesSupported = ERROR |
  WARNING | INFORMATION`. Pops a `MessageBox` on each failure step.
  [verified-by-code]
- `DllUnregisterServer()` — `RegDeleteKey` on the same path.
  [verified-by-code]
- `DllMain(hModule, reason, lpReserved)` — stashes the hModule on
  `DLL_PROCESS_ATTACH`. [verified-by-code]

## Notable invariants / details

- `event_source[256]` — the Windows registry key max is 255 chars;
  the buffer is 256 to leave room for the null. [from-comment]
- `_snprintf` is used (line 83, 136) which is the old non-C99 Windows
  variant that does NOT guarantee a NUL terminator on truncation. Buffer
  is 400 chars so realistically can't overflow with the fixed prefix +
  255-char event-source name (~340 chars max). [verified-by-code]
- Every failure path returns `SELFREG_E_TYPELIB`, which is the
  conventional "generic registration failure" HRESULT.
  [verified-by-code]
- The event-source key in the registry contains the DLL's *current*
  install path; moving the DLL after registration breaks event lookup
  until re-registered. [from-comment]

## Potential issues

- `pgevent.c:42` — `wcstombs(event_source, pszCmdLine, sizeof(event_source))`
  uses the deprecated `wcstombs` (no max output bytes). If `pszCmdLine`
  encodes to more than 256 bytes, this corrupts the stack past
  `event_source`. Practical exploitation requires a malicious
  `regsvr32 /i:LONG_NAME` invocation. [ISSUE-security: unbounded
  wide-to-multibyte conversion (maybe)]
- `pgevent.c:83`, `pgevent.c:136` — `_snprintf` doesn't NUL-terminate
  on truncation. `RegCreateKey` / `RegDeleteKey` would then read past
  the buffer. Mitigated by the size math noted above but a `snprintf`
  or `strlcpy` discipline would be cleaner.
  [ISSUE-security: _snprintf NUL-termination footgun (nit)]
- `pgevent.c:75`, `pgevent.c:88`, etc. — `MessageBox` pops a modal on
  every failure step. If `regsvr32` is invoked silently as part of an
  installer, the modal stalls the installer. Standard practice for
  self-registration, but worth noting.
  [ISSUE-style: modal failure UX from installer context (nit)]
- `pgevent.c:42` — no error check on `wcstombs`'s `(size_t)-1` return
  for invalid wide-character sequences. Result would be a partial
  conversion or leftover stale `event_source` contents.
  [ISSUE-correctness: wcstombs return not checked (nit)]
- `pgevent.c:56` — `if (bInstall) DllRegisterServer();` — return code
  ignored, so even if registration fails, `DllInstall` returns `S_OK`.
  `regsvr32` then reports success. [ISSUE-correctness: install failure
  masked (likely)]
- No code-path handles `regsvr32 /u` (uninstall without `/i`). That's
  by convention; user is expected to use `/u /i:NAME` so we get the
  right name. Without `/i`, `event_source` stays at `DEFAULT_EVENT_SOURCE`
  and we delete the default key, which may not be what was registered.
  [verified-by-code]
