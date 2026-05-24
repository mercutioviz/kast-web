# Test environment reference

Static reference data for the test harness. Source of truth for case files in `cases.md`.

## URLs and ports

| What | Where |
|---|---|
| kast-web (test) | `http://127.0.0.1:8001` |
| Login page | `http://127.0.0.1:8001/auth/login` |
| Juice Shop (scan target) | `http://127.0.0.1:3000` |
| Hackazon (scan target) | `http://127.0.0.1:8888` |
| Test DB (sqlite) | `/var/lib/kast-web-test/kast.db` |
| Test results dir | `/var/lib/kast-web-test/results` |
| Test Redis DB | `redis://127.0.0.1:6379/1` |

## Test accounts

`t_admin` is seeded by `utils/seed_test_admin.py` on env-up. All other accounts are created via the admin UI during **TC-AUTH-010** and persist across runs.

| Username | Role | Email | Used for |
|---|---|---|---|
| t_admin | admin | t_admin@test.local | Admin pages, all scan modes, user mgmt, settings |
| t_power | power_user | t_power@test.local | Active + passive scans, config overrides, ownership transfers |
| t_user | user | t_user@test.local | Passive-only scans, "own" data |
| t_viewer | viewer | t_viewer@test.local | Read-only negative tests |
| t_user2 | user | t_user2@test.local | Receiving shares; cross-tenant authz |

Admin password is in `.env.test` (`TEST_ADMIN_PASSWORD=...`). Use the same password for all created test users to keep automation simple.

## Containers

| Name | Image | Loopback port |
|---|---|---|
| kw-test-juiceshop | bkimminich/juice-shop | 3000 |
| kw-test-hackazon | mutzel/all-in-one-hackazon | 8888 |

## Process pidfiles

| What | Pidfile | Log |
|---|---|---|
| gunicorn | `/tmp/kw-test-flask.pid` | `/tmp/kw-test-flask.log` |
| celery worker | `/tmp/kw-test-celery.pid` | `/tmp/kw-test-celery.log` |

## Scan-target conventions

Active scans go against `127.0.0.1:3000` (Juice Shop) — well-known vulns, expects to be attacked.
Passive scans default to `127.0.0.1:8888` (Hackazon) so we exercise both targets across the suite.
Never set the target to anything else from a test case.

## Outcomes vocabulary

- **pass** — observed behaviour matches expected
- **fail** — observed differs from expected; defect candidate
- **skipped** — case intentionally not run (e.g. live AI; cloud apply)
- **blocked** — infrastructure prevented the case from running (env down, target unreachable)

`blocked` is louder than `skipped`: any blocker on a smoke-tier case aborts the run.
