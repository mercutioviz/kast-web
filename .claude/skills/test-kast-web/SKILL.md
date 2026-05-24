---
name: test-kast-web
description: Run end-to-end tests against the kast-web isolated test environment. Drives a real browser via Playwright MCP, exercises routes per role, and writes a markdown report. Use when the user asks to "run the kast-web tests", "smoke test kast-web", "regression test", or invokes /test-kast-web.
---

# test-kast-web

Drives the kast-web app through real browser and HTTP calls, checks behaviour against the case catalog in `cases.md`, and writes a pass/fail report to `tests/runs/`.

## Invocation

```
/test-kast-web smoke              # ~10 min, must pass before release
/test-kast-web regression         # ~45 min, run before tagging
/test-kast-web full               # ~2-3 hr, full surface + authz matrix
/test-kast-web group=auth         # one group from cases.md
/test-kast-web case=TC-SCAN-003   # one specific case
/test-kast-web --keep-env         # don't tear down at the end
```

If no tier is given, ask the user which one. Don't default — full is expensive.

## Procedure

### 1. Read configuration

Read `config.md` and `cases.md` from this skill's directory. `config.md` lists test accounts, URLs, ports, and Docker target names. `cases.md` is the case catalog filtered by tier/group/case.

### 2. Bring the test env up

Run `scripts/test-env-up.sh` from the repo root. The first run will:
- Generate `.env.test` with fresh secrets (record the admin password from the file).
- Create `/var/lib/kast-web-test/` (asks for sudo once).
- Create the venv and install requirements (slow, one-time).
- Pull and start `kw-test-juiceshop` and `kw-test-hackazon` containers.
- Seed `t_admin`.
- Start gunicorn on port 8001 and a Celery worker on Redis DB 1.

Read the admin password from `.env.test` (`TEST_ADMIN_PASSWORD=...`) — don't store it in the report. Confirm health: `curl -sf http://127.0.0.1:8001/auth/login` returns 200.

If the env is already up (pidfiles exist and processes live), reuse it.

### 3. Run cases

For each selected case:
1. Read the case spec from `cases.md` (preconditions, steps, expected, evidence).
2. Execute steps:
   - For UI cases: use Playwright MCP. Navigate to `http://127.0.0.1:8001`, log in as the role specified, perform steps, observe DOM/flash/HTTP status.
   - For HTTP-only cases (authz matrix, API contracts): use `curl` with the appropriate session cookie.
   - For DB-side-effect cases: read directly via sqlite3 against `/var/lib/kast-web-test/kast.db`.
3. Capture evidence per the spec (screenshot path, response code, DB row).
4. Record the outcome: `pass | fail | skipped | blocked`.

**Important:**
- Never aim a scan at anything other than `127.0.0.1:{juice-shop port}` or `127.0.0.1:{hackazon port}` — see CLAUDE.md.
- Skip cases that depend on prod-only state (e.g. real cloud credentials).
- If a *blocker* hits (server unreachable, login broken), abort the tier and report.

### 4. Write the report

Write to `tests/runs/YYYY-MM-DD-HHMM-<tier>.md`:

```markdown
# kast-web test run — <tier> — <timestamp>

**Result:** N passed / M failed / K skipped / J blocked
**Duration:** ...
**Env:** test (http://127.0.0.1:8001)
**Commit:** <git rev-parse --short HEAD>

## Failures

### TC-XXX-NNN: <subject>
- Role: ...
- Expected: ...
- Actual: ...
- Evidence: tests/runs/<run>/screenshots/...

## Full results

| ID | Subject | Role | Status | Notes |
|----|---------|------|--------|-------|
| TC-AUTH-001 | login happy path | t_admin | pass | |
| ... | | | | |
```

Tell the user the report path and summary line. Don't dump the full table into chat.

### 5. Tear down

Unless invoked with `--keep-env`, run `scripts/test-env-down.sh` (without `--wipe`). The test DB persists across runs so users created via the UI (TC-AUTH-010) stay available. Run with `--wipe` only when the user asks for a clean slate.

## Run pruning

Before writing a new report, delete the oldest report in `tests/runs/` if there are already 30 entries. Keep only the most recent 30.

## Modes vs scheduled

This skill is ad-hoc. For scheduled runs use `/loop`:

```
/loop 24h /test-kast-web smoke
/loop 7d /test-kast-web regression
```

`/loop` only fires while a Claude session is idle; for unattended cron-style runs, a real cron entry calling `claude --headless` is the right answer.
