# shippable.c

## One-line summary

Backend-lifespan cache deciding whether a given function / operator / type (any catalog object) is "shippable" to a remote postgres_fdw server — i.e. exists with the same semantics on the remote — keyed by `(objid, classid, serverid)` and invalidated wholesale when `pg_foreign_server` changes.

## Public API / entry points

- `bool is_builtin(Oid objectId)` (line 152) — objects with OIDs `< FirstGenbkiObjectId` are presumed built-in and shippable everywhere. [verified-by-code]
- `bool is_shippable(Oid objectId, Oid classId, PgFdwRelationInfo *fpinfo)` (line 162) — top-level entry. Built-ins return true immediately; otherwise consults the per-backend cache; on miss calls `lookup_shippable()`.

Internal:
- `lookup_shippable(objectId, classId, fpinfo)` (line 117) — asks `getExtensionOfObject` whether the object is in some extension, then membership-tests against `fpinfo->shippable_extensions`.
- `InvalidateShippableCacheCallback` (line 65) — wipes the whole hash on any `pg_foreign_server` syscache callback.
- `InitializeShippableCache` (line 92) — first-use init of the HTAB and registration of the inval callback.

## Key invariants

- INV-BUILTIN-CUTOFF: `is_builtin(oid) ⇔ oid < FirstGenbkiObjectId`. Used at `shippable.c:155` and also at `deparse.c:1194` (`deparse_type_name`'s decision to schema-qualify). Both must agree. [verified-by-code]
- INV-CACHE-KEY-SHAPE: comment at line 43 says "we assume this struct contains no padding bytes". The struct is `{Oid, Oid, Oid}` (line 41-47) — three same-typed 4-byte fields, which is padding-free in practice. If anyone ever inserts a `bool` here, `HASH_BLOBS` memcmp will start comparing uninitialized bytes. [verified-by-code]
- INV-NO-FN-LEVEL-OPTIN: comment at lines 113-115 says "right now shippability is exclusively a function of whether the object belongs to an extension declared by the user. In the future we could additionally have a list of functions/operators declared one at a time." Today: no per-object shippability declaration exists. [from-comment]

## Notable internals

- The shippable cache is per-backend, never shared. There is no upper bound on its size; in a long-running session with many distinct foreign servers the hashtable grows monotonically.
- The invalidation callback is registered on `FOREIGNSERVEROID` ONLY (line 103). Changes to extension membership (e.g. `ALTER EXTENSION foo ADD FUNCTION bar`) DO NOT invalidate this cache. The XXX comment at lines 56-62 explicitly punts on this: "We do not currently bother to check whether objects' extension membership changes once a shippability decision has been made for them." [from-comment]
- Built-in objects (OID < `FirstGenbkiObjectId`) bypass the cache entirely (line 169) — fast path.
- `lookup_shippable` does NO mutability / collation check — it only asks "is this object in a user-declared extension". The mutability/collation gates live in `deparse.c:foreign_expr_walker` and `is_foreign_expr` (see `deparse.c:287` for `contain_mutable_functions`). [verified-by-code]
- The cache stores entries even for `shippable = false`, so a single unshippable function isn't re-probed every row.

## Trust boundary / Phase D surface

- **Name-vs-OID cross-corpus pattern**: shippability is decided on the LOCAL OID. The remote server's pg_proc oid for the same logical function may differ. Postgres-fdw's escape hatch is `deparseFuncExpr` → `appendFunctionName` which emits the function BY NAME (schema-qualified for non-built-ins, `deparse.c:1194` `FORMAT_TYPE_FORCE_QUALIFY`). So the local→remote resolution is local-OID → local-extension → declared-shippable-extension-name → emit-name-and-schema. The remote then resolves the name. If a remote extension of the same name has DIFFERENT semantics (e.g. local `pg_trgm` 1.5, remote `pg_trgm` 1.3) the result may differ silently. [verified-by-code, dangerous-by-design]
- **Mutable-function gate is local**: `is_shippable` does NOT check `provolatile`. A user can declare an immutable-on-local-but-volatile-on-remote function as part of a "shippable extension" and the local planner will happily push it down. The mutability check (`contain_mutable_functions`) at `deparse.c:287` reads the LOCAL `pg_proc.provolatile` only.
- **Stale extension-membership decisions** (the line 56-62 XXX): if user adds a function to a shippable extension at the remote side but not locally, we won't ship it (safe-fail). If user REMOVES a function from a shippable extension locally without dropping the extension itself, the cached `shippable=true` entry persists until the next `pg_foreign_server` invalidation. The window for a wrong-direction decision is bounded by session lifetime in the worst case.
- **No per-server keying of shippable_extensions**: the LIST is per-server (carried in `fpinfo->shippable_extensions`), so different servers can declare different extensions shippable. The cache key includes `serverid` (line 47), so distinct decisions per server are correctly isolated.
- `lookup_shippable` calls `getExtensionOfObject` which scans `pg_depend` — comment at line 124 calls this "fairly expensive". An attacker who can populate `pg_depend` with bogus extension-membership rows could in principle confuse this; only superusers can do that, so out-of-scope.

## Cross-references

- `source/contrib/postgres_fdw/deparse.c:287` — `contain_mutable_functions` companion gate.
- `source/contrib/postgres_fdw/deparse.c:1190-1198` — `deparse_type_name`, the OTHER consumer of the `FirstGenbkiObjectId` cutoff.
- `source/contrib/postgres_fdw/option.c:159` (`ExtractExtensionList`) — turns the server `extensions` option string into the OID list this file consults.
- `source/src/backend/catalog/dependency.c` — `getExtensionOfObject`.

## Issues spotted

- [ISSUE-correctness: extension-membership changes (`ALTER EXTENSION ... ADD/DROP MEMBER`) do NOT invalidate the shippable cache. A long-lived session that has cached `shippable=true` for `myext.foo` will keep shipping it after a DBA drops it from the extension. (likely)] — `source/contrib/postgres_fdw/shippable.c:56-62` (XXX in comment confirms by-design, not a bug, but bug-class behaviour).
- [ISSUE-security: cross-cluster semantics mismatch via shippable extension. Declaring "extensions 'pg_trgm'" assumes the remote has a compatible `pg_trgm`. There is no version check, no signature compare. A privileged local user can poison remote query results by relying on this. (defense-in-depth maybe)] — `source/contrib/postgres_fdw/shippable.c:117` (lookup_shippable returns true on extension membership alone).
- [ISSUE-correctness: text-search REGCONFIG / REGDICTIONARY get a special weakened rule at `deparse.c:439-448` ("for text search objects only, weaken the normal shippability criterion to allow all OIDs below FirstNormalObjectId"). This is `FirstNormalObjectId` (16384), looser than `is_builtin`'s `FirstGenbkiObjectId`. The two cutoffs being different for the same concept is a code-smell trap for future contributors. (nit)] — `source/contrib/postgres_fdw/deparse.c:439`, `shippable.c:155`.
- [ISSUE-memory: cache grows monotonically per backend, never trimmed. A pathological workload that touches millions of distinct unshippable function OIDs (e.g. across many foreign servers) bloats the cache. No LRU. (nit)] — `source/contrib/postgres_fdw/shippable.c:100`.
- [ISSUE-defense-in-depth: `is_builtin` returns true even for things like `information_schema` types if they happened to be below `FirstGenbkiObjectId`. Comment at line 144-150 explains why TYPES are tighter via the `deparse_type_name` check; functions/operators are NOT. So an information_schema function would be presumed shippable, which is probably fine but is asymmetric. (nit)] — `source/contrib/postgres_fdw/shippable.c:144`.
