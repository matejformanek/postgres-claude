# `src/include/port/win32_port.h`

## Role

The "big" Windows compatibility header — 589 lines mapping POSIX-style
APIs onto Win32 equivalents. Read in **MinGW AND native MSVC builds**
but NOT in Cygwin (Cygwin uses its own posix layer)
`[from-comment]` `source/src/include/port/win32_port.h:6-7`.

Major responsibility groups:

1. **SSPI authentication** (`ENABLE_SSPI 1`) `[verified-by-code]`
   `source/src/include/port/win32_port.h:23`.
2. **Windows headers ordering** — `WIN32_LEAN_AND_MEAN`,
   `UMDF_USING_NTSTATUS`, includes of `winsock2.h`, `ws2tcpip.h`,
   `windows.h`, `ntstatus.h`, `winternl.h`
   `source/src/include/port/win32_port.h:46-64`.
3. **`fsync` emulated as `_commit(fd)`** — Windows has no fsync per
   se `[verified-by-code]` `source/src/include/port/win32_port.h:82-83`.
4. **IPC defines** — fake `IPC_RMID`, `IPC_CREAT`, `EIDRM`, etc.,
   needed for PG's sysv-shmem emulation on Windows
   `source/src/include/port/win32_port.h:88-110`.
5. **Signal emulation** — defines `SIGHUP`, `SIGQUIT`, `SIGTRAP`,
   `SIGABRT`, `SIGKILL`, `SIGPIPE`, `SIGALRM`, `SIGSTOP`, `SIGTSTP`,
   `SIGCONT`, `SIGCHLD`, `SIGWINCH`, `SIGUSR1`, `SIGUSR2` with
   Windows-friendly numbers (some match Unix, `SIGABRT=22` doesn't)
   `source/src/include/port/win32_port.h:155-172`.
6. **`WIFEXITED/WIFSIGNALED/WEXITSTATUS/WTERMSIG`** — Windows
   `system()` returns NT status codes; <0x100 ≡ exit, ≥0x100 ≡
   exception. Macros redefined to interpret that
   `source/src/include/port/win32_port.h:150-153`.
7. **`pgoff_t = __int64`** — Windows doesn't have 64-bit `off_t` but
   does have 64-bit-offset functions; PG defines its own type and
   maps `fseeko`/`ftello` to MSVC-only wrappers
   `source/src/include/port/win32_port.h:192-211`.
8. **Symlinks emulated via `pgsymlink`/`pgreadlink`** — uses NTFS
   junction points on newer Windows
   `source/src/include/port/win32_port.h:213-226`.
9. **`stat()` redefined** to `_pgstat64` for 64-bit `st_size` and
   junction-point-as-symlink reporting (steals `S_IFCHR` bit for
   `S_IFLNK` since neither MSVC nor MinGW provides it)
   `source/src/include/port/win32_port.h:243-334`.
10. **`O_CLOEXEC`, `O_DIRECT`, `O_DSYNC`** — borrowed bit flags
    mapped to CreateFile equivalents in `src/port/open.c`
    `source/src/include/port/win32_port.h:336-346`.

(File continues beyond the 250 lines read — also covers errno mapping,
`pgsleep`, `gethostname`, locale, and more.)

## Public API (highlights)

`[verified-by-code]` `source/src/include/port/win32_port.h:23-346`:

- `ENABLE_SSPI 1`.
- `pgoff_t = __int64`; `fseeko`/`ftello` → MSVC wrappers
  `_pgfseeko64`/`_pgftello64`.
- `extern int pgsymlink(const char *oldpath, const char *newpath)`;
  same for `pgreadlink`.
- `fsync(fd) = _commit(fd)`.
- `extern int gettimeofday(struct timeval *, void *)` (MSVC only).
- `extern int setitimer(int, const struct itimerval *, struct
  itimerval *)`.
- `extern DWORD pgwin32_get_file_type(HANDLE)`.
- `extern int _pgfstat64/_pgstat64/_pglstat64(...)`.
- Many signal numbers; W*-status macros for exit codes.

## Invariants

1. **Not read on Cygwin.** Cygwin uses `cygwin.h` instead.
2. **Win32 stat is 32-bit by default in MSVC**; PG redefines
   `struct stat` to mirror `__stat64` for 64-bit file size support
   `[from-comment]` `source/src/include/port/win32_port.h:250-253`.
3. **`S_IFLNK` steals `S_IFCHR`** — character-device stat mode
   reused as "junction point" sentinel. No real character devices
   exist in PG's working set so safe `[verified-by-code]`
   `source/src/include/port/win32_port.h:321-334`.
4. **`SIGABRT = 22`** to match Windows' value, NOT POSIX's 6
   `[verified-by-code]` `source/src/include/port/win32_port.h:161`.
   Mixing Unix-coded signal handlers with Windows tools is a known
   subtle hazard.
5. **`WIN32_LEAN_AND_MEAN + UMDF_USING_NTSTATUS`** — needed to avoid
   `windows.h` redefining `NTSTATUS` (which `ntstatus.h` needs to
   provide) and to keep windows.h's compile-time bloat down
   `[from-comment]` `source/src/include/port/win32_port.h:46-58`.
6. **`mkdir(a,b)` ignores mode bits** — Win32 has no POSIX mode
   `[verified-by-code]` `source/src/include/port/win32_port.h:79-80`.
7. **`HAVE_UNION_SEMUN` forced to 1**; `key_t = long`; `pid_t` is
   `int` only under MSVC (MinGW already has it)
   `source/src/include/port/win32_port.h:88-91,237-241`.

## Trust-boundary / Phase D surface

- **The biggest porting/security divergence in the tree.** Anything
  that touches signals, file ops, or process model on Windows hits
  this header. Edge cases:
  - **Signal numbers** don't match Unix; a hardcoded `kill(pid, 6)`
    is SIGABRT on Linux but illegal on Windows.
  - **fsync = _commit** is documented elsewhere as not flushing the
    drive cache by default. Durability on Windows mirrors macOS
    weakness.
  - **NTFS junction points** treated as symlinks — junction targets
    can be absolute Windows paths; a malicious or buggy tablespace
    setup could point at a system directory. Same risk as Unix
    symlinks but visible only on Windows.
  - **`O_DIRECT = 0x80000000`** — borrowed high bit. Open(2) on
    Windows must translate; if the value collides with a real
    `_O_*` flag in some future MSVC, breakage is silent.
- **`stat` redefinition reuses `S_IFCHR`** for symlink bit. If any
  consumer ever cares about real char devices on Windows (none do
  today), the abstraction breaks.
- **`SetFileType`/`GetFileType` wrapper** `pgwin32_get_file_type` is
  used to determine if a handle is a tty/disk/pipe — affects
  buffered vs unbuffered I/O choices.
- **`_pgstat64`'s lstat on junction points** must follow the
  reparse-tag protocol; bugs would mis-report symlink targets.
  See `src/port/win32stat.c` for the implementation (out of scope).
- **Heavy preprocessor surface** — 589 lines of `#define` and
  `#undef` create a fertile ground for token-pasting and macro-
  hygiene bugs. PG has paid down most of these but each new
  Windows-specific patch is a chance to break the macro hygiene.

## Cross-refs

- `source/src/port/win32stat.c` — `_pgstat64` etc.
- `source/src/port/open.c` — O_DIRECT/O_DSYNC translation.
- `source/src/port/pgsleep.c`, `pgsymlink.c` — counterpart .c.
- `source/src/include/port/win32ntdll.h` — dynamically-loaded NT
  functions used for `NtFlushBuffersFileEx`-style WAL flush.
- `source/src/include/port/win32.h` — sister header; runs first.

## Issues / unresolved

- **ISSUE-doc**: header doesn't summarize the "Windows fsync is
  weaker than POSIX fsync" angle; readers need to know `_commit()`
  on a buffered file does NOT flush the drive cache. The
  durability-strict path is `pg_NtFlushBuffersFileEx` from
  `win32ntdll.h`. (severity: medium, durability-narrative)
- **ISSUE-trust**: NTFS junction-point handling repurposes
  `S_IFCHR`; any future PG code that cares about char devices on
  Windows breaks. Currently safe. (severity: low)
- **ISSUE-portability**: 589 lines of macros is a large surface for
  silent compile-time conflicts when system headers change. MinGW
  vs MSVC vs WSL2 see different `<crtdefs.h>` etc. (severity: low,
  maintenance)
- **ISSUE-perf-narrative**: signal emulation goes through Windows
  event objects and a dispatcher thread; latency is much higher
  than POSIX signals. Affects pgbench/recovery-failover tests on
  Windows. Documented in `pgwin32_signal_event` (.c). (severity:
  doc-only, narrative)
