# uavc.c

## One-line summary

Userspace Access Vector Cache — local per-backend hash bucket cache of recent
AVC decisions, with retry-on-policy-reload semantics and the trusted-procedure
transition label cache piggy-backed on it.

## Public API / entry points

- `sepgsql_avc_check_perms_label(tcontext, tclass, required, audit_name,
  abort_on_violation) → bool` — `source/contrib/sepgsql/uavc.c:336-417`. **The
  central enforcement entry point.** Returns `true` iff all bits in `required`
  are allowed. On denial with `abort_on_violation=true` raises
  `ereport(ERROR, INSUFFICIENT_PRIVILEGE)`. [verified-by-code]
- `sepgsql_avc_check_perms(ObjectAddress *tobject, tclass, required,
  audit_name, abort_on_violation) → bool` — `uavc.c:419-435`. Thin wrapper:
  resolves `tobject` to a `tcontext` via `GetSecurityLabel(tobject,
  SEPGSQL_LABEL_TAG)` then delegates.
- `sepgsql_avc_trusted_proc(functionId) → char *` — `uavc.c:444-469`. Returns
  the new client label to switch to when entering a trusted procedure, or
  NULL if the proc is not a transition target.
- `sepgsql_avc_init(void) → void` — `uavc.c:487-521`. Allocates the
  `avc_mem_cxt`, zeroes the slot table, opens `selinux_status_open(1)` (mmap
  the kernel status page), registers `sepgsql_avc_exit` for `on_proc_exit`.

## Key invariants

- The cache has `AVC_NUM_SLOTS = 512` open hash buckets (`uavc.c:52`).
  `AVC_DEF_THRESHOLD = 384` is the size at which `sepgsql_avc_reclaim` runs
  (`uavc.c:54, 280`). [verified-by-code]
- Cache key = `(scontext, tcontext, tclass)` — hashed via `hash_bytes` XOR
  `tclass` (`uavc.c:67-72`).
- Cache lifetime: entire backend lifetime, with reclaim of cold entries
  triggered when count exceeds threshold (`uavc.c:91-125`).
- **Invalidation:** *only* a policy reload signal from the kernel
  (`selinux_status_updated() > 0`) flushes the cache (`uavc.c:152-161`).
  Nothing else invalidates — including DROP, RELABEL, or backend-side
  `SECURITY LABEL` changes. [verified-by-code]
- Each check loop is wrapped in
  `sepgsql_avc_check_valid(); do { ... } while (!sepgsql_avc_check_valid())`
  to make decisions atomic w.r.t. a possible policy reload mid-decision
  (`uavc.c:336-388`, comment at 127-149). [verified-by-code]

## Notable internals

`avc_cache` struct fields (`uavc.c:30-47`):

- `hash`, `scontext`, `tcontext`, `tclass` — key.
- `allowed`, `auditallow`, `auditdeny` — the AVD bitmasks.
- `permissive` — true if this rule is in a permissive *domain* (per-domain
  permissive, not the GUC).
- `hot_cache` — LRU hint; flipped to true on lookup hit and to false during
  a reclaim sweep that doesn't evict.
- `tcontext_is_valid` — false when the target's stored label failed
  `security_check_context_raw` and was substituted with `unlabeled`.
- `ncontext` — when `tclass == SEPG_CLASS_DB_PROCEDURE`, the new scontext
  to assume on procedure entry (NULL if no transition).

Reclaim algorithm (`sepgsql_avc_reclaim`, `uavc.c:91-125`):

- Walks slots starting at `avc_lru_hint`.
- For each cache in slot, evicts if `!hot_cache`, otherwise clears
  `hot_cache` (second-chance LRU).
- Advances `avc_lru_hint` modulo `AVC_NUM_SLOTS`.
- Loop bound is `avc_num_caches >= avc_threshold - AVC_NUM_RECLAIM` — so
  the function aims to bring count down by at least 16 entries.

`sepgsql_avc_compute` (`uavc.c:199-288`) — cache miss path:

1. Validate `tcontext` via `security_check_context_raw`. If invalid, the
   computation uses `sepgsql_avc_unlabeled()` instead. The cache entry
   records `tcontext_is_valid = false`. [verified-by-code]
2. Call `sepgsql_compute_avd` (selinux.c) for the actual AVD.
3. If `tclass == SEPG_CLASS_DB_PROCEDURE`, also call `sepgsql_compute_create
   (..., SEPG_CLASS_PROCESS, NULL)` to determine the
   trusted-procedure transition label. If that label equals the current
   scontext, `ncontext` is freed and set NULL (no transition).
4. Allocate the `avc_cache` in `avc_mem_cxt` (a child of `TopMemoryContext`,
   `uavc.c:495-497`). [verified-by-code]
5. Insert at head of bucket via `lcons` (newest-first).

`sepgsql_avc_check_perms_label` core:

```
do {
    result = true;
    cache = sepgsql_avc_lookup(scontext, tcontext or unlabeled, tclass);
    denied = required & ~cache->allowed;
    audited = (sepgsql_get_debug_audit())
              ? (denied ? denied : required)
              : (denied ? denied & cache->auditdeny
                        : required & cache->auditallow);
    if (denied) {
        if (!sepgsql_getenforce() || cache->permissive)
            cache->allowed |= required;      /* permissive widening */
        else
            result = false;
    }
} while (!sepgsql_avc_check_valid());
```

The "permissive widening" at `uavc.c:384` is subtle: in non-enforcing mode,
the cache entry's `allowed` mask is **mutated to include the requested
bits** so that subsequent identical checks won't re-audit. This is purely
audit-volume control — a future enforcing check on this same key after a
policy reload (which would `avc_reset`) would re-decide.

Audit firing logic at `uavc.c:397-409`:

- Skip if `audited == 0`.
- Skip if `audit_name == SEPGSQL_AVC_NOAUDIT`.
- Skip if `sepgsql_get_mode() == SEPGSQL_MODE_INTERNAL` (bgworker/early
  startup — silently no audit).

## Trust boundary / Phase D surface

- **`sepgsql_avc_check_perms_label` is THE permission check.** Every other
  file in sepgsql funnels through this function (directly or via
  `sepgsql_avc_check_perms`). If it ever returns true incorrectly, all of
  MAC is bypassed. Auditing this function is the highest-leverage Phase D
  review item. [verified-by-code]

- **Permissive widening mutates the cache** (`uavc.c:384`). A
  non-enforcing decision permanently flips that cache entry to "allowed"
  until policy reload. **Implication**: if an admin transitions the
  cluster from PERMISSIVE → DEFAULT *without* a policy reload (e.g.,
  switches sepgsql.permissive=off and SIGHUPs), existing backends still
  carry cache entries whose `allowed` was widened in PERMISSIVE mode.
  Those cached widenings persist until the entry is reclaimed or the
  policy reloads. **This is a confused-state risk.**
  [ISSUE-security: permissive-mode cache widening (uavc.c:384) persists
  across mode flip from PERMISSIVE→DEFAULT in long-lived backends; new
  checks within the same key get the widened result until cache reclaim
  or policy reload (likely)]

- **Cache invalidation is policy-reload-only.** Adding `SECURITY LABEL` to
  an object does *not* invalidate cache entries that reference the
  object's *old* tcontext — but those entries are keyed by tcontext
  string, so the new SetSecurityLabel changes the GetSecurityLabel
  result, and the next lookup uses the new tcontext (a new cache key).
  So the old entry just becomes garbage that will eventually reclaim.
  No stale-decision risk from SECURITY LABEL changes. [verified-by-code]

- **`selinux_status_updated()` is mmap-driven.** If the kernel status page
  was opened in fallback (netlink) mode (`uavc.c:516`), the update
  detection may lag. The retry loop only re-checks after the lookup, so
  one query could use a stale decision and audit it. [inferred]

- **`sepgsql_avc_unlabeled()` is cached forever** (`uavc.c:170-191`) until
  `avc_reset`, and `avc_reset` resets it to NULL — *but the call to
  `sepgsql_avc_unlabeled` after reset re-allocates*. If `MemoryContextReset
  (avc_mem_cxt)` happens, the `avc_unlabeled` C-pointer is dangling.
  Checking: `sepgsql_avc_reset` (`uavc.c:78-86`) does `MemoryContextReset
  (avc_mem_cxt); ... avc_unlabeled = NULL;` — the explicit nulling
  prevents the dangling read. [verified-by-code]

- **`sepgsql_avc_check_valid` recursion** — the function may be called
  twice per check (before the do-loop, and as the loop test). It calls
  `selinux_status_updated() > 0`. If a policy reload happens *between*
  the lookup and the second check_valid, the result is discarded and the
  loop retries. Correct, but a pathological reload storm could spin.
  [inferred]

- **`SEPGSQL_AVC_NOAUDIT` bypass.** Callers passing `SEPGSQL_AVC_NOAUDIT`
  suppress audit unconditionally (`uavc.c:398`). The only current
  caller is `sepgsql_needs_fmgr_hook` (label.c:297) for the
  "should-I-care-about-this-function" probe. Reasonable, but creates a
  precedent: future contributors may use NOAUDIT casually and create
  audit-gap bugs. [ISSUE-audit-gap: NOAUDIT sentinel suppresses audit
  unconditionally; future misuse risk (nit)]

- **The check is per-(s,t,class) tuple, not per-object-instance.** Two
  tables with the same label generate one cache entry. Audit_name is
  formatted per-call but the decision applies to all instances. **This
  is the correct SELinux model**, but means audit records may name
  different objects with identical decisions — a forensic challenge if
  the log doesn't carry the tuple OID. [verified-by-code]

- **`sepgsql_avc_exit` only calls `selinux_status_close()`**
  (`uavc.c:476-480`). It does not pfree the cache — relying on
  `TopMemoryContext` teardown. Fine in practice; but a long-lived
  backend that gets a SIGTERM mid-query never reaches normal exit. The
  mmap region is per-process so this leaks at the OS level; acceptable.
  [verified-by-code]

- **Parallel-worker handling.** No special-cased code for parallel
  workers in this file. Each parallel worker has its own backend → its
  own uavc cache. The client label is initialized via
  `sepgsql_init_client_label` (label.c) using `getcon_raw` for the
  server label until authentication, but parallel workers don't undergo
  authentication. The worker's `client_label_peer` is the *server's*
  context, not the originating client's. [ISSUE-security:
  sepgsql_init_client_label in parallel-worker context yields the
  server context as scontext, not the originating client's — DML
  permission checks in parallel workers see the wrong subject;
  needs verification against parallel infrastructure but the code path
  reads that way (likely)]

- **Trusted-procedure cache poisoning.** `cache->ncontext` is computed
  *once at miss time* via `sepgsql_compute_create(..., SEPG_CLASS_PROCESS,
  NULL)`. If the policy changes the transition rule for a (s,t) pair
  *without* reloading the policy globally, the stale `ncontext` is
  returned. SELinux policy changes always do a reload, so this is fine
  in practice — relies on libselinux invariants. [inferred]

## Cross-references

- selinux.c — `sepgsql_compute_avd`, `sepgsql_compute_create`.
- label.c — `sepgsql_get_client_label` is the scontext source for every
  check; `sepgsql_needs_fmgr_hook` calls `sepgsql_avc_trusted_proc`.
- `source/src/backend/commands/seclabel.c` — `GetSecurityLabel` is the
  tcontext source in `sepgsql_avc_check_perms`.
- libselinux: `selinux_status_open`, `selinux_status_updated`,
  `selinux_status_close`, `security_get_initial_context_raw`,
  `security_check_context_raw`.

## Issues spotted

- `[ISSUE-security: permissive-mode cache widening (uavc.c:384)
  permanently mutates the cached `allowed` mask; survives flipping
  sepgsql.permissive from on→off without a policy reload (likely)]`
- `[ISSUE-security: parallel workers initialize client_label_peer to the
  server context, not the originating client's label; sepgsql DML checks
  in parallel workers may use the wrong subject (likely)]`
- `[ISSUE-audit-gap: SEPGSQL_MODE_INTERNAL silently disables audit
  emission in this function (uavc.c:399); bgworkers (autovacuum) thus
  run with no audit trail (confirmed)]`
- `[ISSUE-audit-gap: SEPGSQL_AVC_NOAUDIT sentinel suppresses audit
  unconditionally; current single use is justified but pattern is
  fragile (nit)]`
- `[ISSUE-concurrency: avc_reclaim's second-chance LRU eviction is
  O(slots * entries) worst-case; large caches can stall a query mid-
  permission-check (nit)]`
- `[ISSUE-memory: cache entries live until reclaim or policy reload —
  on systems with rare reloads, the cache grows to AVC_DEF_THRESHOLD
  (384 entries) per backend; pgbench fan-out of unique (s,t) tuples
  could be a fingerprint signal (nit)]`
- `[ISSUE-correctness: sepgsql_avc_check_valid is called both before
  and as the loop condition; under a reload storm the loop could
  spin indefinitely (unverified)]`
- `[ISSUE-defense-in-depth: invalidation is policy-reload-only — there
  is no "purge cache" SQL function for admins (nit)]`
- `[ISSUE-documentation: uavc.c does not document that
  `permissive` cache field reflects the SELinux *permissive domain*
  policy attribute, distinct from the `sepgsql.permissive` GUC and
  from `sepgsql_getenforce()` returning false; three concepts all
  named "permissive" (likely)]`
