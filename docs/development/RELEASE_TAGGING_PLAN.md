# Release tagging plan

Prepared 2026-11-18. **Nothing here has been executed.** Every command is for
you to run after review — tags are outward-facing and publish releases.

## Why this exists

Tags in both repos stopped tracking releases months ago:

| Repo | VERSION | Latest tag | Untagged |
|---|---|---|---|
| kast-web | 2.1.0 (this release) | `v2.0.9` (2026-05-26) | 2.0.10 – 2.0.15, plus 2.1.0 |
| kast | 3.0.52 | `v3.0.35` | 3.0.36 – 3.0.52 |

So for a release described as "coordinated kast 3.0 / kast-web 2.0", neither
repo's tags currently reflect what is deployed. `/opt/kast-web` has been
running 2.0.15 since 2026-11-09 against a tag history that ends at 2.0.9.

## Two VERSION-file anomalies you should know about before tagging

These are historical facts, not things to fix retroactively — but they change
what a tag can honestly mean.

**`2.0.14` never existed in the VERSION file.** No commit in the repository has
`VERSION` reading `2.0.14`. The release commit `37b522d` ("Release v2.0.14")
left `VERSION` at `2.0.13`.

**`2.0.15` shipped reading `2.0.13` too.** Release commit `0fe5c77` also left
`VERSION` at `2.0.13`; it was corrected afterwards by `1080cc0`
("Bump VERSION to 2.0.15") on the same day.

Net effect: anyone running 2.0.14, or 2.0.15 before `1080cc0`, saw the app
report itself as **2.0.13**. `kast_web_cli.py` reads `VERSION` directly, so
`kast-web --version` was wrong for both.

This release avoids repeating it: `VERSION` is bumped to `2.1.0` in the same
commit as the CHANGELOG heading, before the tag is cut.

## Proposed tags — kast-web

Each historical tag goes on its `Release vX.Y.Z` commit, matching how `v2.0.9`
and earlier were done.

| Tag | Commit | VERSION at that commit | Note |
|---|---|---|---|
| `v2.0.10` | `74ccbfc` | 2.0.10 | clean |
| `v2.0.11` | `795556f` | 2.0.11 | clean |
| `v2.0.12` | `4cb28b1` | 2.0.12 | clean |
| `v2.0.13` | `e69f9a5` | 2.0.13 | clean |
| `v2.0.14` | `37b522d` | **2.0.13** | VERSION never said 2.0.14 |
| `v2.0.15` | `0fe5c77` | **2.0.13** | or `1080cc0`, where VERSION reads 2.0.15 |
| `v2.1.0` | the release commit | 2.1.0 | cut after review |

**The `v2.0.15` choice is yours.** `0fe5c77` is the release commit and matches
the convention; `1080cc0` is the first commit where the version string is
actually correct. I would tag `0fe5c77` for consistency and say so in the tag
message, since the CHANGELOG entry describes `0fe5c77`'s content.

`v2.0.0` and `v1.15` appear in the CHANGELOG but have no release commit — they
predate the convention. I would leave them untagged rather than guess at a
boundary; an inaccurate tag is worse than a missing one.

### Commands

Annotated tags, to match the existing ones:

```bash
cd /home/admin/kast-web

git tag -a v2.0.10 74ccbfc -m "Release v2.0.10 — scan runners + CSRF session-expiry fix"
git tag -a v2.0.11 795556f -m "Release v2.0.11 — self-service password reset"
git tag -a v2.0.12 4cb28b1 -m "Release v2.0.12 — critical severity in ZAP progress tracking"
git tag -a v2.0.13 e69f9a5 -m "Release v2.0.13 — server ZAP execution mode"
git tag -a v2.0.14 37b522d -m "Release v2.0.14 — expanded report logo format support

Tagged retroactively on 2026-11-18. Note: the VERSION file at this commit
reads 2.0.13; it was not bumped for this release."
git tag -a v2.0.15 0fe5c77 -m "Release v2.0.15 — import logos from a URL

Tagged retroactively on 2026-11-18. Note: the VERSION file at this commit
reads 2.0.13; corrected in 1080cc0."

# Review before pushing
git tag | sort -V
git push origin v2.0.10 v2.0.11 v2.0.12 v2.0.13 v2.0.14 v2.0.15
```

Then, once you are satisfied with 2.1.0:

```bash
git tag -a v2.1.0 -m "Release v2.1.0 — viewer role enforced, public share links removed"
git push origin v2.1.0
```

## kast repo

`/home/admin/kast` is at VERSION 3.0.52 with tags ending at `v3.0.35`. I have
not examined its history, so I have not proposed a mapping — the same
release-commit convention may or may not hold there. Do the same exercise
before tagging:

```bash
cd /home/admin/kast
git log --oneline --reverse v3.0.35..HEAD | grep -iE "release|bump|version"
```

If kast-web 2.1.0 is meant to pair with a specific kast version, pin that in
both tag messages so the pairing is recoverable later.

## Why 2.1.0 and not 2.0.16

Two changes in this release are more than fixes:

- **The `viewer` role is now enforced.** Viewers previously could create and
  run scans; they no longer can. Anyone who relied on that — deliberately or
  not — sees a behaviour change.
- **Public share links are removed.** The UI advertised them; it no longer
  does.

A reader scanning version numbers should see that something changed shape, not
just that bugs were fixed.

## Before cutting 2.1.0

- [ ] Review `docs/development/OPEN_FINDINGS.md` — decide which open items, if
      any, block the release. The public-cloud entries are explicitly low
      priority as of 2026-11-18.
- [ ] Confirm the CHANGELOG `[2.1.0]` entry reads correctly for an outside
      audience.
- [ ] Decide the kast pairing, if this is still a coordinated release.
- [ ] Note that `/opt/kast-web` currently runs 2.0.15; deploying 2.1.0 is a
      separate step from tagging it.
