# Local, test and production

Every check runs against one environment, and what you may do depends on which. Decide that before
the first request, not after.

| Environment | What it is |
|---|---|
| **Local** | Runs on this machine or in containers you started: the dev server, a local database, emulators |
| **Test** | Shared non-production: staging, QA, dev-shared, preview/review apps, sandboxes. Other people and other runs use it |
| **Production** | Real users, real data, real money. Everything that is not provably local or test |

## Determining the environment

Work through these in order and stop at the first clear answer.

1. **The knowledge base.** Read `.besman/environments.md` in the project if it exists. It names the
   hosts, env files and resources for each environment, and it overrides every heuristic below.
2. **Hostname** of the URL or connection string:
   - `localhost`, `127.0.0.1`, `[::1]`, `0.0.0.0`, `*.local`, `*.localhost`, `*.test`, a docker
     compose service name (`db`, `api`, `redis`) → **local**.
   - A host containing `staging`, `stage`, `qa`, `test`, `dev`, `preview`, `sandbox`, `uat` →
     **test**.
   - Anything else → **treat as production** until the user says otherwise. A bare product domain,
     an `api.` subdomain, an unlabelled cloud host: production.
3. **Env file name**: `.env.local`, `.env.development` → local; `.env.staging`, `.env.test`,
   `.env.qa` → test; `.env.production`, `.env.prod` → production. A plain `.env` tells you
   nothing: read the hosts inside it.
4. **Cloud resource names**: resource groups, projects, buckets, clusters and databases suffixed
   `-dev`, `-stg`, `-qa`, `-test` → test; `-prod`, `-prd`, or no suffix → production.
5. **Payment and third-party keys**: `sk_test_`, `pk_test_`, sandbox endpoints → test mode;
   `sk_live_`, `pk_live_`, `rk_live_` → **production**, whatever host they sit next to.

Signals that disagree (a staging host with a live key, a `.env.local` pointing at a production
database) mean the stricter environment applies. Report the conflict.

## What each environment allows

| | Local | Test | Production |
|---|---|---|---|
| Read (pages, API, logs) | Freely | Freely | Only when the user explicitly asks |
| Act as a user through the UI or API | Freely | Yes, as a user would | No |
| Create fixtures, seed data | Yes, guarded | Only when the user instructs that write | Never |
| Direct DB writes | Yes, guarded | Only when the user instructs that one write | Never |
| Restart services, change config, flags | Yes | Only when the user instructs | Never |
| Load tests, fuzzing, security probes | Yes | Only when the user instructs | Never |
| Send emails, SMS, payments, webhooks | Only to sinks/test mode | Only test-mode providers and your own addresses | Never |
| Clean up | Restore what you changed | Remove what you created | Nothing to clean: you created nothing |

### Local

Full freedom, with two habits:

- **Guard** every destructive step with the environment check, so the same script cannot run
  against another target:

  ```bash
  case "$DATABASE_URL" in
    *localhost*|*127.0.0.1*|*@db:*|*@db/*) ;;
    *) echo "refusing: DATABASE_URL is not local" >&2; exit 1 ;;
  esac
  ```

- **Record and restore.** Before changing a row, a file, or a setting, save its current value;
  put it back afterwards and say so in the report. Local data is often someone's hand-built state.

### Test

Shared with other people and other runs, so collisions matter.

- Read freely; act through the API or UI the way a user would.
- No direct DB writes, fixtures, config or flag changes unless the user explicitly instructs that
  specific write. One approval covers that one write, not the next.
- Name what you create so it is recognisable (a unique prefix per run), and do not touch entities
  you did not create.
- Expect interference: another run may change the same entity. A surprising state is first a
  question of who else is there, then a defect.
- Clean up what you created, and list anything you could not remove.

### Production

- Read-only, and only when the user explicitly asks for a production check.
- Never create, modify or delete data. Never place orders, send emails, trigger payments or
  webhooks.
- Never run load tests, scanners or security probes.
- Prefer logs, telemetry and dashboards over live requests. When a request is unavoidable, make it
  a read, make one, and say why.

## A PASS belongs to one environment

Every check records the environment it ran in (name and host). A PASS in one environment never
clears another: local passing says nothing about staging, staging passing says nothing about
production.

**Prove the branch you exercised is the branch that runs in the target environment.** Code often
forks on environment:

- `if` on config values, credential presence, feature flags, `NODE_ENV`/`ASPNETCORE_ENVIRONMENT`
  or equivalents. Find each fork on the path under test and say which side your run took and which
  side the target takes.
- The local interpreter or runtime is not the deployed one: different version, bundled
  dependencies, environment variables, permissions. Importing a function locally exercises none of
  that.
- Drive the deployed entry point (the HTTP route, the queue message, the scheduled trigger), not
  the module behind it, when the claim is about the deployed environment.

## Before any action

State the environment in one line: "Target: staging (`app.staging.example.com`, from
`.env.staging`)". If the target is ambiguous (signals disagree, no knowledge base entry, an
unlabelled host), ask the user to confirm before the first request that writes anything.

## Credentials

- Find the variables a check needs by **name** in the dev env files. Never print values. Test
  presence without revealing them:

  ```bash
  set -a; . ./.env.local; set +a
  [ -n "$TEST_USER_EMAIL" ] && echo "TEST_USER_EMAIL set" || echo "TEST_USER_EMAIL missing"
  echo "API_KEY length: ${#API_KEY}"
  ```

- If one is missing, tell the user exactly which variable in which file is needed, and ask them to
  add it themselves or to sign in in the browser. Never ask for the value in chat.
- Never use production credentials for a test run, even when they are the only ones present.
- Never copy secrets between env files, and never write them into fixtures, logs, screenshots or
  the report.
