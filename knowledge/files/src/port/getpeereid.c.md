---
path: src/port/getpeereid.c
anchor_sha: 4b0bf0788b066a4ca1d4f959566678e44ec93422
loc: 78
depth: deep
---

# src/port/getpeereid.c

## Purpose

Provides a BSD-style `getpeereid(int sock, uid_t *uid, gid_t *gid)` for
platforms that lack it. Returns the effective uid/gid of the process on the
other end of a **Unix-domain socket** connection. This is the kernel-attested
peer identity behind `peer` authentication (`pg_hba.conf` `peer` method) and
`getpeereid`-based local trust decisions — the OS, not the client, tells us who
connected, so it cannot be spoofed at the protocol level. `[verified-by-code]`

## Public symbols

| Symbol | Site | Notes |
|---|---|---|
| `int getpeereid(int sock, uid_t *uid, gid_t *gid)` | `getpeereid.c:33` | 0 on success; -1 with `errno` on failure (`ENOSYS` if unsupported) |

## Internal landmarks

Four mutually-exclusive platform arms:

1. **`SO_PEERCRED`** (Linux, `getpeereid.c:35-45`) — `getsockopt(SO_PEERCRED)`
   filling a `struct ucred`.
2. **`LOCAL_PEERCRED`** (Debian/kFreeBSD, `:46-57`) — `struct xucred`; also
   validates `cr_version == XUCRED_VERSION`.
3. **`HAVE_GETPEERUCRED`** (Solaris, `:58-72`) — `getpeerucred()` +
   `ucred_geteuid`/`ucred_getegid`, freeing the `ucred_t`; rejects `(uid_t)-1`.
4. **No implementation** (`:73-77`) — sets `errno = ENOSYS`, returns -1.

## Invariants & gotchas

- **Unix-domain sockets only.** On a TCP socket these calls fail; peer auth is
  inherently a local-socket feature.
- Each arm double-checks the returned `socklen` equals `sizeof(cred struct)`
  before trusting the values (`:41`, `:52`) — a short read would otherwise
  yield uninitialized identity.
- Identity is **kernel-attested**: this is a security-relevant trust anchor.
  Callers (`auth.c` peer method) treat the returned uid as authoritative.

## Cross-refs

- `knowledge/subsystems/libpq-backend.md` — where peer auth consumes this.
- `knowledge/files/src/port/getaddrinfo.c.md` — N/A (deleted upstream at this
  anchor; was the IPv4/IPv6 name-resolution shim).
