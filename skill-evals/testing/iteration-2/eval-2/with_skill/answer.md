# Eval 2 — TAP test for streaming replication catching a WAL record (WITH SKILL)

Step 2 of the decision tree: initdb + standby + replication → **TAP test**.
Recovery/replication tests live in `source/src/test/recovery/t/NNN_name.pl`.
Pick the next free `NNN`; **don't renumber** existing tests (breaks backports).

## Wire-in

`source/src/test/recovery/meson.build` (and the `Makefile` if present in that
dir). The SKILL's wiring table lists this explicitly.

## Skeleton (based on `001_stream_rep.pl`)

```perl
use strict;
use warnings FATAL => 'all';
use PostgreSQL::Test::Cluster;
use PostgreSQL::Test::Utils;
use Test::More;

my $primary = PostgreSQL::Test::Cluster->new('primary');
$primary->init(allows_streaming => 1);
$primary->start;

$primary->backup('bk');
my $standby = PostgreSQL::Test::Cluster->new('standby');
$standby->init_from_backup($primary, 'bk', has_streaming => 1);
$standby->start;

# Operation that emits your WAL record
$primary->safe_psql('postgres', 'SELECT my_thing()');

# Sync — preferred form:
$primary->wait_for_replay_catchup($standby);
# or, explicitly:
my $lsn = $primary->lsn('insert');
$standby->poll_query_until('postgres',
    "SELECT pg_last_wal_replay_lsn() >= '$lsn'::pg_lsn");

# Verify standby state
my $r = $standby->safe_psql('postgres', 'SELECT ...');
is($r, 'expected', 'standby replayed the record');

$standby->stop('fast');
$primary->stop('fast');
done_testing();
```

## Honest caveat

TAP tests verify **replicated state** (table contents, LSN advance), **not
WAL-record identity**. There is no `assert_wal_record_of_type('XLOG_FOO')` API.
If you really need to inspect the record itself, shell out to `pg_waldump`
from a separate step.

## Single test, fast

```bash
meson test -C build --suite recovery NNN_name -v
# or
cd source/src/test/recovery && make check PROVE_TESTS=t/NNN_name.pl
```

## When it fails

`build/testrun/recovery/NNN_name/log/regress_log_*` is the Perl-side log — read
that **before** the postmaster logs. Set `PG_TEST_NOCLEAN=1` to keep
`tmp_check/` around even on success.

## House style

Only `IPC::Run` outside Perl 5.14 core; everything else must be core.
`done_testing();` at the end.
