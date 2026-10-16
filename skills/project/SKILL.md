---
name: project
description: Creates and maintains the project knowledge base `.besman/` that the besman `test` and `review` skills read their standards, rules, constraints and environments from, and records the user's own rules into it. Use when the user wants to set up, refresh, show or add to the project's knowledge base, or says "remember this rule for this project", "add a rule", "load the project knowledge".
---

# The project knowledge base

`.besman/` is a directory at the root of the user's project. It holds what a reviewer or a tester
must know about this project and cannot read off the code: the standards, the rules, the
constraints, the environments and the test accounts. `/besman:test` and `/besman:review` read it at
the start of every run; this skill creates it, refreshes it, and writes the user's rules into it.

**Everything in it is written to be read by an agent in the middle of a task**: short, specific,
one rule per line, each with where it came from. A paragraph of background is a rule nobody applies.

## Invocation

```
/besman:project                          show what the knowledge base holds, and what is missing
/besman:project init                     create .besman/ from the project, then ask for what cannot be found
/besman:project refresh                  re-scan the project and update what changed, keeping user rules
/besman:project rule "<rule>"            record one of the user's rules
/besman:project env                      (re)write environments.md with the user
/besman:project show <file>              print one file
```

A plain sentence works too: "запомни правило: …", "add to the knowledge base that …" is a `rule`.

## Where it lives

The project root is the git top level of the repository the user is in
(`git rev-parse --show-toplevel`). For a workspace of several repositories with no common git root,
ask once where `.besman/` should go, and record the answer in its `project.md`.

```
.besman/
  README.md          what this directory is, who reads it, how to change it (generated)
  project.md         stack, repositories, services, how to build, run and test each
  environments.md    local / test / production: URLs, env files, what is allowed in each
  standards.md       coding, API, testing and documentation standards, with their sources
  constraints.md     hard limits: performance budgets, compatibility, compliance, forbidden things
  rules.md           the user's own rules, newest last, never rewritten by a refresh
  testing.md         frameworks, commands, BDD runner, e2e setup, test accounts (variable NAMES only)
  pitfalls.md        traps this project has already fallen into, one per entry
  local/             personal notes, gitignored
```

`.besman/local/` is added to the project's `.gitignore`. Everything else is meant to be committed,
so the whole team and every colleague's Claude reads the same rules. Say so to the user after
`init`, and let them decide whether to commit.

## Secrets never enter the knowledge base

`.besman/` names variables, never their values. `testing.md` says "the e2e suite reads
`E2E_BUYER_EMAIL` and `E2E_BUYER_PASSWORD` from `.env.test.local`", not the email and password.
When scanning env files, read **names only**:

```bash
sed -n 's/^\(export \)\{0,1\}\([A-Za-z_][A-Za-z0-9_]*\)=.*/\2/p' .env.example .env.development 2>/dev/null | sort -u
```

If the user pastes a secret while dictating a rule, do not write it. Write the rule with the variable
name, and tell them the value belongs in their env file.

## `init` and `refresh`: build it from the project

Do the scan yourself, read-only. For each file, collect facts with their source (`file:line` or the
command that produced them), then write the file.

| File | Read from |
|---|---|
| `project.md` | README, `CLAUDE.md`, `AGENTS.md`, manifests (`package.json`, `pyproject.toml`, `*.csproj`/`*.sln`, `go.mod`, `Cargo.toml`, `pom.xml`/`build.gradle`), `docker-compose*.yml`, `Makefile`/`justfile`/`Taskfile`, the monorepo layout |
| `environments.md` | env file **names** and variable **names** (`.env*`), compose files, deploy and CI workflows (`.github/workflows`, `.gitlab-ci.yml`, `azure-pipelines.yml`), infrastructure code, any URL in the README. See below: this file is always confirmed with the user |
| `standards.md` | `CONTRIBUTING.md`, PR templates, `docs/`, linter and formatter configs (what they enforce is listed as enforced by tooling, not as a rule to review), architecture decision records |
| `constraints.md` | docs on performance, SLOs, compatibility and supported versions, compliance (PII, retention, licences), `engines`/`requires-python`/target frameworks, anything written as "must"/"never" |
| `testing.md` | test folders and configs (`jest.config`, `vitest.config`, `pytest.ini`/`conftest.py`, `playwright.config`, `*.feature`, `cucumber`/`behave`/`pytest-bdd`/`SpecFlow`/`Reqnroll`/`godog`), CI test jobs, e2e auth setup, seed and fixture scripts |
| `pitfalls.md` | docs named pitfalls/gotchas/known-issues, recurring fix commits (`git log --oneline --grep -iE 'fix|hotfix|revert' -n 200`), post-mortems |

Write only what you found. Where a section has nothing, write `Not documented. Ask:` and the one
question that would fill it, rather than inventing a plausible default. A knowledge base that guesses
is worse than an empty one, because the skills that read it will trust it.

On `refresh`: regenerate the scanned files, **keep `rules.md` untouched**, keep any line marked
`(user)` in the other files, and show the user a short diff of what changed.

## `environments.md`: always confirmed by the user

The test skill decides what it may do from this file, so a wrong line here can send a write to
production. Draft it from the scan, then **ask the user to confirm it**, one question round:

```markdown
# Environments

| | Local | Test | Production |
|---|---|---|---|
| Web URL | http://localhost:3000 | https://staging.example.com | https://example.com |
| API URL | http://localhost:8080 | https://api.staging.example.com | https://api.example.com |
| Env file | .env.local | .env.staging | (CI secrets only) |
| Data store | docker compose `db` | managed, shared with QA | managed |
| Identity provider app | dev app | staging app | production app |
| How to recognise it | localhost, compose service names | `staging` in host | anything else |
| Allowed | anything, with record/restore | act through the API/UI as a user; no direct data writes | read-only, and only when asked |
| Test accounts | E2E_USER_EMAIL / E2E_USER_PASSWORD in .env.test.local | same names in .env.staging.local | none |
```

Anything the user does not confirm stays marked `(unconfirmed)`, and the test skill treats an
unconfirmed host as production.

## `rule`: record the user's rule

1. Restate the rule in one line, imperative, specific enough to check: "API errors are RFC 7807
   problem details", not "errors should be good".
2. Pick its scope: which file, which area (`api`, `db`, `ui`, `tests`, `security`, `perf`, …), and
   whether it binds `review`, `test` or both.
3. If it contradicts an existing rule, show both and ask which wins; never keep two contradicting
   lines.
4. Append to `rules.md`:

```markdown
- [api][review,test] API errors are returned as RFC 7807 problem details. (user, 2026-10-16)
```

5. Read the line back to the user.

Rules in `rules.md` outrank `standards.md`, and both outrank the skills' built-in defaults. Only the
ticket's own acceptance criteria outrank `rules.md` for the scope of that ticket.

## Showing it

`/besman:project` with no argument lists each file with its line count and last change, then lists what
is missing: an environment row still `(unconfirmed)`, a `Not documented. Ask:` line, a test command
that no longer exists in the manifests. Offer to fix the gaps one question at a time.

## How the other skills use it

- `/besman:test` reads `environments.md` first and refuses to act on an environment it cannot place;
  reads `testing.md` for commands, the BDD runner, the e2e setup and the account variable names;
  `constraints.md` for thresholds; `pitfalls.md` as error-guessing input; `rules.md` always.
- `/besman:review` passes `standards.md`, `constraints.md`, `rules.md` and `pitfalls.md` to its lenses
  under `Project rules:`.

When either skill learns something durable during a run (an environment trap, a missing test
account, a recurring defect), it offers to record it here with this skill; it never writes
`.besman/` silently.
