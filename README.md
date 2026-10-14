# besman

Project-independent code review for Claude Code. One skill, `review`, runs four review subagents in
parallel over a diff, then the project's own linters, tests and SAST, and merges everything into one
verdict and one GitHub review.

| Subagent | Judges |
|---|---|
| `review-best-practices` | Whether it is good code, measured against the code around it |
| `review-security` | How the change can be abused: access control, injection, secrets, SSRF, XSS, disclosure |
| `review-implementation` | Whether it does what the ticket asked, and nothing it did not |
| `review-standards` | Conformance to the rules the project wrote down (CLAUDE.md, CONTRIBUTING, docs) |

## Install

In a Claude Code chat:

```
/plugin marketplace add bes-man/besman
/plugin install besman@besman
```

Claude Code 2.1.275 and later also take one command: `/plugin install besman --marketplace bes-man/besman`.

From a shell: `claude plugin marketplace add bes-man/besman`, then `claude plugin install besman@besman`.

Then `/reload-plugins` or start a new session.

Without a marketplace, a single file: `bash install-besman.sh` (into `~/.claude`) or
`bash install-besman.sh --project <dir>` (into one project's `.claude`). Build it with `./build.sh`.

To have everyone who opens a project get it, commit to that project's `.claude/settings.json`:

```json
{
  "extraKnownMarketplaces": {
    "besman": { "source": { "source": "github", "repo": "bes-man/besman" } }
  },
  "enabledPlugins": { "besman@besman": true }
}
```

## Use

```
/besman:review                        the current branch
/besman:review --pr 812               a pull request
/besman:review 3994                   find the pull requests for a ticket
/besman:review --no-publish           report locally, post nothing
```

Needs `git`, `gh` (authenticated) and `python3`; `jq` for publishing; `semgrep` is used when installed.
Posting to GitHub always asks first in an interactive session, and is always `COMMENT`, never an
approval.

## What it runs and where data goes

Everything runs locally with your own credentials; besman sends nothing to any service of its own.

- `git` on the repository under review: fetch, diff, log. Never pushes, never merges.
- `gh` to read the pull request, its checks and comments, and the ticket if it is a GitHub issue.
- Your project's own linters and tests, and `semgrep` if installed, scoped to the changed files.
- Writes working files to `/tmp/rv/`.
- Posts to GitHub only in phase 5: one pull-request review (`COMMENT`, never approve or request
  changes) and optionally a check run. Interactive sessions show the exact text and ask first.

## License

MIT
