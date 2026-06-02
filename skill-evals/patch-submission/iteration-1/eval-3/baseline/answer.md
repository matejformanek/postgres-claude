# Small numeric.c bug fix — process

For a one-line fix with a regression test, the process is essentially the
same as for any change, just lighter-weight:

1. Make sure the fix is on top of current `master` and the test suite
   passes.
2. Generate the patch with `git format-patch -v1 master..HEAD`.
3. Email it to **pgsql-hackers@lists.postgresql.org** — plain text, patch
   attached (not inline). In the body, describe the bug, the fix, and note
   that you've included a regression test.
4. Register the patch in the current CommitFest at
   <https://commitfest.postgresql.org/>.

You can probably skip the "post a design discussion first" step that
larger features need — for an obvious bug fix, the patch itself is enough.

For something this small a committer may pick it up quickly. If the bug
exists in older branches too, a committer will decide whether to backpatch
— you don't need to do that yourself.

A few things to avoid:
- No HTML email
- Don't paste the patch in the body
- Reply on the same thread for any revisions, don't start new threads

Bypassing -hackers and emailing a committer directly is not the norm — the
mailing-list trail matters.
