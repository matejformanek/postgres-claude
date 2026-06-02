# Eval 2 — TAP test for streaming replication (BASELINE, no skill)

This needs a real running primary plus a standby, so it's a Perl TAP test using
`PostgreSQL::Test::Cluster`. Tests like this typically live under
`src/test/recovery/t/`. Name it `NNN_something.pl` where NNN keeps it ordered
relative to the existing files.

## Skeleton

Roughly:

```perl
use strict;
use warnings;
use PostgreSQL::Test::Cluster;
use Test::More;

my $primary = PostgreSQL::Test::Cluster->new('primary');
$primary->init(allows_streaming => 1);
$primary->start;

# take a base backup and start a standby
$primary->backup('mybkp');
my $standby = PostgreSQL::Test::Cluster->new('standby');
$standby->init_from_backup($primary, 'mybkp', has_streaming => 1);
$standby->start;

# Do whatever emits your WAL record
$primary->safe_psql('postgres', "SELECT trigger_my_op()");

# Wait until standby has caught up. There's a helper on the cluster
# object for this — I'd check Cluster.pm for the exact name; something
# like wait_for_catchup / wait_for_replay_catchup.

# Then check the standby state
my $out = $standby->safe_psql('postgres', "SELECT ...");
is($out, 'expected_value', 'standby applied the record');

done_testing();
```

There isn't really a "assert this WAL record type was applied" API as far as I
know — you verify the *effect* on the standby (table contents, LSN moved past
a checkpoint, a system view).

## Wiring

You'll need to make sure the meson build / Makefile in `src/test/recovery/`
picks it up. I'd grep for an existing TAP filename in that dir to find what
needs editing.

## Running just this test

Something like one of:

```bash
meson test -C build recovery/NNN_name
cd src/test/recovery && make check PROVE_TESTS=t/NNN_name.pl
```

## Failures

Logs end up under the build directory's `tmp_check` / `testrun` tree. The
Perl test driver writes a `regress_log` file per test that's the first thing
to read.
