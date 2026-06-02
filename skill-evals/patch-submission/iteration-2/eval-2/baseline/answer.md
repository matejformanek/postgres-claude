# Responding to "Waiting on Author"

You're in the standard review cycle. Here's what to do.

## 1. Address the feedback

Go through each comment from the reviewer and either fix it or, if you
disagree, reply explaining why. Don't silently ignore points.

## 2. Make the changes

Apply the test additions and fix the error-message wording on your branch.
You can either:

- Add them as new commits, or
- Amend/rebase to fold them into the original commits

The latter gives a cleaner patch series, which reviewers tend to prefer.

## 3. Generate a new patch version

Bump the version number:

```bash
git format-patch -v2 master..HEAD
```

If you've already been through several rounds, use the next number (`-v3`,
`-v4`, ...).

## 4. Post the new version

Reply to the existing thread on pgsql-hackers — don't start a new one.
Attach the new patch (plain text email, attachment, not inline) and in the
body summarize what changed since the previous version and respond to the
reviewer's points inline.

## 5. Update the CommitFest entry

Flip the status from "Waiting on Author" back to "Needs Review" so the
reviewer knows to take another look.

Then wait for the next round.
