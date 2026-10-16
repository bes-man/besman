# besman

Project-independent code review and testing for Claude Code, with a per-project knowledge base.

| Skill | Does |
|---|---|
| `/besman:kb` | Creates `.besman/` in your project: standards, rules, constraints, environments, test setup. Records your own rules (`/besman:kb rule "..."`). The other two skills read it every run |
| `/besman:review` | Four review subagents in parallel over a diff, the project's linters, tests, SAST and dependency audit, one verdict, one GitHub review |
| `/besman:test` | Verifies a task before and after the change with the same inputs: every test case worth checking, Gherkin where it belongs, backend efficiency measured, UI driven live through Playwright and with the cursor in a real browser, strict local / test / production separation |

| Subagent | Judges |
|---|---|
| `review-best-practices` | Good code against the code around it; overcomplication with the simpler version; deprecated APIs |
| `review-security` | Access control, injection, secrets, SSRF, XSS, disclosure; vulnerable dependencies and outdated crypto |
| `review-implementation` | Whether it does what the ticket asked, and nothing it did not |
| `review-standards` | Conformance to the project's written rules, `.besman/` first |
| `test-survey` | What automated tests already cover, and the gaps |
| `test-designer` | Every test case for this task, by technique; Gherkin for business-facing behaviour |
| `test-efficiency` | Backend efficiency (N+1, unbounded reads, indexes, chatty calls, timeouts), errors, overcomplication |
| `test-verifier` | Requirement trace, concurrency and authorisation, from the code |

Start in a project with `/besman:kb init`.

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
/besman:kb init                       build .besman/ from the project, confirm environments with you
/besman:kb rule "API errors are RFC 7807 problem details"
/besman:review                        review the current branch
/besman:review --pr 812               review a pull request
/besman:test 3994                     test a ticket's branch locally, before and after
/besman:test --env test               verify on the test environment (no direct data writes there)
```

Needs `git`, `gh` (authenticated) and `python3`; `jq` for publishing; `semgrep` and the dependency
audit tools are used when installed; Playwright MCP and/or Claude in Chrome for UI testing.
Posting to GitHub always asks first in an interactive session, and is always `COMMENT`, never an
approval.

## What it runs and where data goes

Everything runs locally with your own credentials; besman sends nothing to any service of its own.

- `git` on the repository under review: fetch, diff, log. Never pushes, never merges.
- `gh` to read the pull request, its checks and comments, and the ticket if it is a GitHub issue.
- Your project's own linters and tests, and `semgrep` if installed, scoped to the changed files.
- Writes working files to `/tmp/rv/` and `/tmp/tv/`, and the knowledge base to `.besman/` in your
  project (only through `/besman:kb`, never silently). Secrets are never written there, only
  variable names.
- `/besman:test` builds and runs your project locally, drives a browser, and calls your local or
  test environment as a test user. It never writes to production, never uses production
  credentials for a test run, and asks you to sign in or add a token to your dev env file when
  access is missing; it never asks for a secret in the chat.
- Posts to GitHub only in phase 5: one pull-request review (`COMMENT`, never approve or request
  changes) and optionally a check run. Interactive sessions show the exact text and ask first.

## License

MIT
