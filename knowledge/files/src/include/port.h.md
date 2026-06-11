# `src/include/port.h`

- **Last verified commit:** `e18b0cb7344`
- **Lines:** ~585
- **Source:** `source/src/include/port.h`

The portability-shim aggregator header — defines or wraps every libc
function that varies across the supported platforms (Unix, Win32,
Cygwin, MinGW, macOS). Included by `c.h:1498` near the END of `c.h`,
not the beginning, because some of its declarations depend on
`c.h`-defined types (`pg_attribute_printf`, etc.). [verified-by-code]

The internal organization is loose. Major blocks:
1. Socket type (`pgsocket`, `PGINVALID_SOCKET`).
2. Path-handling family (`canonicalize_path`, `make_absolute_path`,
   `get_share_path`, `get_lib_path`, etc.).
3. printf/snprintf replacements with `pg_*` prefix.
4. errno groupings (`ALL_CONNECTION_FAILURE_ERRNOS`).
5. Windows-specific socket/file/process replacements.
6. Various missing-libc fallbacks (`strlcpy`, `strlcat`, `strsep`,
   `mkdtemp`, `inet_aton`, `explicit_bzero`).
7. qsort/bsearch wrappers (`pg_qsort`, `bsearch_arg`,
   `qsort_interruptible`).
8. Localization helpers (`pg_localeconv_r`, `pg_get_encoding_from_locale`).
9. Random (`pg_strong_random`).
10. Signal trampoline (`pqsignal`, `pqsigfunc`).

## API / declarations (representative sample)

### Sockets

- `pgsocket` = `int` on Unix, `SOCKET` on Win32; `PGINVALID_SOCKET`
  matches.
- `socklen_t` fallback if `HAVE_SOCKLEN_T` is unset.
- `pg_set_noblock(sock)` / `pg_set_block(sock)`.

### Path handling (`port.h:47-82`)

The whole family is in `src/port/path.c`:
- `has_drive_prefix`, `first_dir_separator`, `last_dir_separator`,
  `first_path_var_separator`.
- `join_path_components(ret, head, tail)`.
- `canonicalize_path(path)` — collapses `.`/`..`/`//`.
- `canonicalize_path_enc(path, encoding)` — encoding-aware variant.
- `make_native_path(filename)` — Win32 backslash conversion.
- `cleanup_path` — pg_upgrade-friendly cleanup.
- `path_contains_parent_reference`, `path_is_relative_and_below_cwd`,
  `path_is_safe_for_extraction`, `path_is_prefix_of_path`.
- `make_absolute_path(path)`.
- `get_progname(argv0)`.
- `get_{share,etc,include,pkginclude,includeserver,lib,pkglib,locale,
  doc,html,man}_path(my_exec_path, ret_path)` — the standard PG
  install dir queries.
- `get_home_path(ret_path)` / `get_parent_directory(path)`.
- `pgfnames(path)` / `pgfnames_cleanup(filenames)`.

Path-separator macros (`port.h:83-109`):
- `IS_NONWINDOWS_DIR_SEP(ch)`, `is_nonwindows_absolute_path(filename)`.
- `IS_WINDOWS_DIR_SEP(ch)` — accepts both `/` and `\`.
- `is_windows_absolute_path(filename)` — drive-letter aware (e.g.
  `C:\...`); the comment at `port.h:90` notes `E:abc` is treated as
  relative.
- `IS_DIR_SEP` / `is_absolute_path` — typedef to the appropriate
  variant based on `WIN32`.

### Errno grouping (`port.h:111-132`)

`ALL_CONNECTION_FAILURE_ERRNOS` — a case-statement-shaped macro
that bundles EPIPE, ECONNRESET, ECONNABORTED, EHOSTDOWN, EHOSTUNREACH,
ENETDOWN, ENETRESET, ENETUNREACH, ETIMEDOUT. Used as
`case ALL_CONNECTION_FAILURE_ERRNOS:` in a switch. The comment
flags that EPIPE/ECONNRESET often warrant separate handling.

### exec / find_*_exec (`port.h:134-151`)

- `set_pglocale_pgservice(argv0, app)`.
- `validate_exec(path)`, `find_my_exec(argv0, retpath)`,
  `find_other_exec(argv0, target, versionstr, retpath)`.
- `pipe_read_line(cmd)`.
- `PG_BACKEND_VERSIONSTR` = `"postgres (PostgreSQL) " PG_VERSION "\n"`.
- `pg_disable_aslr()` — only under `EXEC_BACKEND`.

### Platform macros (`port.h:153-167`)

- `EXE` = `".exe"` on Win/Cygwin else `""`.
- `DEVNULL` = `"nul"` on Win else `"/dev/null"`.
- `pg_usleep(microsec)`.

### Case-folding (`port.h:168-194`)

- `pg_strcasecmp`, `pg_strncasecmp` — locale-independent.
- `pg_toupper`, `pg_tolower` — full Unicode-aware.
- `pg_ascii_toupper` / `pg_ascii_tolower` — `static inline`, C/POSIX
  rules only, ASCII-fast.

### Printf family (`port.h:196-270`)

The full snprintf-replacement set:
- `USE_REPL_SNPRINTF=1` (vestigial).
- Aggressive `#undef` of libintl's potentially-replaced
  printf/snprintf/etc. (`port.h:209-232`).
- `pg_vsnprintf`, `pg_snprintf`, `pg_vsprintf`, `pg_sprintf`,
  `pg_vfprintf`, `pg_fprintf`, `pg_vprintf`, `pg_printf` — all
  `pg_attribute_printf`-annotated.
- `#define vsnprintf pg_vsnprintf` ... `printf(...) pg_printf(__VA_ARGS__)`
  redirect everything.
  `printf` uses `__VA_ARGS__` form so format-attribute checks still
  work; the comment at `port.h:252-258` notes the function-pointer
  hazard.
- `pg_pread` / `pg_pwrite` — direct on Unix; Win32 uses pgport
  replacement that doesn't shift file position.
- `pg_strfromd(str, count, precision, value)` — float→string.

### Strerror (`port.h:272-282`)

- `pg_strerror` wraps `strerror` for robustness; `#define strerror
  pg_strerror`.
- `pg_strerror_r(errnum, buf, buflen)` — GNU-style return.
- `PG_STRERROR_R_BUFLEN = 256`.
- `pg_strsignal(signum)`.
- `pclose_check(stream)`.

### Time-zone globals (`port.h:286-293`)

- `TIMEZONE_GLOBAL` and `TZNAME_GLOBAL` map to `_timezone`/`_tzname`
  on Windows, `timezone`/`tzname` elsewhere.

### Windows-only (`port.h:295-413`)

- `pgrename(from, to)`, `pgunlink(path)` — atomic-rename + retries for
  Win32 "file in use" races. `#define rename pgrename`,
  `#define unlink pgunlink`.
- `pgsymlink`, `pgreadlink` — symlinks-as-junction-points on Win32.
- `lseek` → `_lseeki64` for 64-bit offsets (`port.h:342-343`).
- `ftruncate` → `_chsize_s`.
- `pgwin32_open`, `pgwin32_fopen` — open()/fopen() replacements
  allowing deletion of open files.
- `pgwin32_system`, `pgwin32_popen` — double-quoting trick to survive
  cmd.exe parsing.
- `PG_IOLBF` — `_IOLBF` on Unix, `_IONBF` on Windows because
  Windows setvbuf crashes on _IOLBF.

### Misc fallbacks (`port.h:420-475`)

- `pgoff_t` = `off_t` on Unix.
- `getpeereid(sock, &uid, &gid)`.
- `explicit_bzero` — secure zeroing.
- `pg_strtof` — buggy-strtof shim.
- `link(src, dst)` — Win32 only.
- `mkdtemp`, `inet_aton`, `strlcat`, `strlcpy`, `strsep`,
  `timingsafe_bcmp` — libc gaps.

### qsort etc (`port.h:488-509`)

- `pg_qsort`, `pg_qsort_strcmp`, `#define qsort(a,b,c,d) pg_qsort(...)`.
- `qsort_arg_comparator` typedef.
- `qsort_arg(base, nel, elsize, cmp, arg)`,
  `qsort_interruptible(...)` — calls CHECK_FOR_INTERRUPTS periodically.
- `bsearch_arg(...)`.

### Locale / encoding / random / dir / signal

- `pg_localeconv_r(lc_monetary, lc_numeric, &output)` /
  `pg_localeconv_free(lconv)`.
- `pg_get_encoding_from_locale(ctype, write_message)`.
- `pg_codepage_to_encoding(cp)` — Win32 backend only.
- `pg_inet_net_ntop(af, src, bits, dst, size)`.
- `pg_strong_random_init`, `pg_strong_random(buf, len)`.
  `pg_backend_random` alias for backward compat.
- `pg_check_dir(dir)`, `pg_mkdir_p(path, omode)`.
- `pqsignal_fe` / `pqsignal_be` — frontend vs backend pqsignal
  trampoline. Macro `pqsignal` picks based on FRONTEND.
- `PG_SIG_DFL` / `PG_SIG_IGN` — function-pointer-typed casts of
  `SIG_DFL`/`SIG_IGN` to avoid -Wcast-function-type.
- `escape_single_quotes_ascii(src)` — for SQL-literal escaping.
- `wait_result_to_str`, `wait_result_is_signal`,
  `wait_result_is_any_signal`, `wait_result_to_exit_code`.

### Unix-presence assumptions (`port.h:565-583`)

`#ifndef WIN32` blob defines `HAVE_GETRLIMIT`, `HAVE_POLL`,
`HAVE_POLL_H`, `HAVE_READLINK`, `HAVE_SETSID`, `HAVE_SHM_OPEN`,
`HAVE_SYMLINK` unconditionally — these are no longer probed at
configure time on Unix-likes.

## Notable invariants / details

- The `#undef vsnprintf` etc. block (`port.h:209-232`) is required
  because libintl's gettext-replacement scheme may have already
  done its own #define before port.h gets loaded. PG runs second
  and wins. [from-comment]
- `printf` uses `__VA_ARGS__` form deliberately to preserve
  `pg_attribute_printf` checking at call sites. Function pointers
  to printf will NOT do what you want — you must use `pg_printf`
  explicitly (`port.h:252-258`). [from-comment]
- `pg_pread`/`pg_pwrite` on Win32 have the **side effect** of
  changing the file position — the macro pg_-prefix is a deliberate
  warning. Direct use of `pread`/`pwrite` in PG code is a bug.
  [from-comment]
- `ALL_CONNECTION_FAILURE_ERRNOS` macro relies on switch-case syntax;
  it expands to "EPIPE: case ECONNRESET: ..." which only works inside
  a switch. Wrong context = syntax error. [from-comment]
- `pgrename`/`pgunlink` are NOT no-ops on Unix even though they're
  declared as `#define rename pgrename` only on Windows — Unix uses
  raw libc.
- The `pg_disable_aslr` declaration is `#ifdef EXEC_BACKEND` —
  meaning it exists on Windows and on Unix dev builds with
  `--enable-exec-backend`. The function lowers security
  intentionally. [from-comment]
  [ISSUE-security: `pg_disable_aslr` deliberately weakens process
  ASLR; only intended for EXEC_BACKEND devs (confirmed)]
- `pg_strong_random` is the canonical CSPRNG. `pg_prng` (`utils/`) is
  NOT secure (`sampling.h:16-23`, A15 echo). Mixing them is a known
  source of bugs.
- `qsort_interruptible` calls `CHECK_FOR_INTERRUPTS()` periodically —
  use it for user-data sorts (large query results); plain `qsort`
  for fixed-size internal arrays. No header-level rule
  distinguishes them.
- `pqsignal_fe` vs `pqsignal_be` — different files in src/port. The
  macro `pqsignal` chooses based on FRONTEND. Mis-link (e.g.
  linking pqsignal_be into a frontend) silently picks the wrong
  signal-handling discipline. [verified-by-code]

## Potential issues

- `port.h:147-150` — `pg_disable_aslr` is a deliberately-insecure
  developer-only function. Header gives no "DO NOT USE" warning,
  only the `#ifdef EXEC_BACKEND` gate. [ISSUE-security:
  pg_disable_aslr should be more loudly marked dev-only (likely)]
- `port.h:209-232` — the libintl `#undef` block must be reapplied if
  libintl is updated to use new printf macro names. Easy to miss.
  [ISSUE-stale-todo: libintl printf-replacement undef list is
  hand-maintained against libintl ABI (nit)]
- `port.h:267` — `#define printf(...) pg_printf(__VA_ARGS__)` ONLY
  works for the macro-call form; taking `&printf` as a function
  pointer gets the libc one. Documented in comment but easy to
  miss. [ISSUE-api-shape: `&printf` function pointer silently
  bypasses pg_printf (likely)]
- `port.h:489` — `qsort` macro redirect to `pg_qsort` means any
  in-tree code that explicitly wants libc qsort can't get it. New
  contrib that wants libc behavior must `#undef qsort` first.
  [ISSUE-api-shape: `qsort` macro override is sticky (nit)]
- `port.h:531` — `pg_strong_random_init()` is required before first
  `pg_strong_random` call in most platforms — but the header doesn't
  say so. The contract is in pg_strong_random.c. [ISSUE-documentation:
  pg_strong_random init contract not in header (maybe)]
- `port.h:511-515` — `pg_localeconv_r` takes locale names by string;
  silently uses C locale on platform-recognition failure.
  [ISSUE-correctness: pg_localeconv_r failure mode opaque (nit)]
- `port.h:531-536` — `pg_backend_random` is a `#define` alias for
  `pg_strong_random`. Code that wants a weaker but faster
  per-backend PRNG must NOT use this name. [ISSUE-style:
  pg_backend_random alias misleading (nit)]
- `port.h:553` — `pqsigfunc` is `typedef void (*)(SIGNAL_ARGS)` where
  SIGNAL_ARGS comes from c.h — a 2-argument signal handler. Standard
  Unix signal handlers take 1 arg; the PG dispatch wrapper bridges
  the gap. New code that bypasses pqsignal and calls libc `signal`
  directly gets the wrong arg count. [ISSUE-defense-in-depth:
  pqsignal vs libc signal not flagged at header (likely)]
- `port.h:575-583` — the unconditional HAVE_* on Unix is convenient
  but a hypothetical Unix-like without `setsid` would silently link
  fail. [ISSUE-style: HAVE_* unconditional on Unix; documentation
  trust-the-platform (nit)]
