# Public repository readiness review

Review started from commit `8aa1f59`. This report records the local validation
performed before publication; current CI results are available in the repository's
Actions tab.

## Findings addressed

| Priority | Finding | Change |
| --- | --- | --- |
| P1 | Vault member/audit administration checked the active vault rather than the vault named in the URL. | Check admin membership in the requested vault; regression tests cover foreign member reads/writes and audit access. |
| P1 | Table sources accepted item types, containers, and relation types from other vaults. Unknown IDs could also fail after a partial write. | Resolve references inside the active vault during validation and make table writes atomic. |
| P1 | Any editor in a vault could accept another user's AI action. Concurrent requests could execute an action twice. | Require conversation ownership and lock actions during acceptance/rejection. Roll back failed action writes. |
| P1 | Startup created an `admin/admin` account and could elevate an existing non-admin with the configured username. | Require an explicit provisioning password, otherwise use first-admin setup; refuse automatic promotion of existing non-admins. |
| P1 | A transaction around first-admin setup did not prevent simultaneous requests from creating multiple administrators. | Serialize setup against the site-settings row and validate input through the account serializer. |
| P2 | Public settings exposed AI provider URLs and model configuration. | Limit non-admin responses to public application settings; keep credentials write-only. |
| P2 | Development ports listened on all interfaces; production lacked HTTPS/cookie defaults and allowed unsafe explicit configuration. | Bind Compose and host Vite to loopback; restrict development hosts; enforce strong production keys, explicit hosts, HTTPS, and secure cookies. Proxy trust and HSTS domain policies are explicit settings. |
| P2 | Pinned dependencies had published security advisories. | Update vulnerable Python pins and npm dependencies/lockfile; audit both dependency trees. |
| P2 | Frontend lint failed and table refetches could overwrite an unsaved form. | Fix hook/state/type issues and initialize table editing state once per table. |
| P3 | Item-type pagination lacked explicit ordering after aggregation. | Order by name and primary key for stable pagination. |

Relevant implementation and regression coverage are in
[accounts](backend/apps/accounts/tests/), [agent](backend/apps/agent/tests/), and
[matrices](backend/apps/matrices/tests/). The Django update includes the fixes in
its [6.0.8 security release](https://www.djangoproject.com/weblog/2026/aug/04/security-releases/).
Production settings were reviewed against the
[Django deployment checklist](https://docs.djangoproject.com/en/6.0/howto/deployment/checklist/).

## Repository preparation

- Replaced stale setup documentation and the frontend scaffold README.
- Added a safe environment example and ignored local agent files, environment
  variants, keys, and database exports in Git and relevant Docker contexts.
- Added contributor/security guidance and GitHub Actions for tests, migrations,
  lint, builds, dependency audits, and full-history secret scanning.
- Added Dependabot configuration for Python, npm, Dockerfiles, and GitHub Actions.

## Validation

- **Backend:** 377 tests passed against isolated PostgreSQL 16, including concurrent
  first-admin setup and concurrent AI action acceptance. No test warnings remained.
- **Django:** system checks passed; no missing migrations. Production deployment
  checks passed with explicit test hosts, a generated key, trusted proxy settings,
  and both optional HSTS flags enabled (zero silenced checks).
- **Frontend:** clean lockfile install, ESLint with zero warnings, and production
  build passed. Docker also installed dependencies with its normal `npm ci` flow.
- **Dependencies:** npm audit and pip-audit both reported zero known vulnerabilities
  after updates, including transitive dependencies resolved by the Python audit.
- **Secrets:** Gitleaks found no leaks in all 36 Git commits or in the current
  publication candidates, including new files. Findings were redacted during scans.
- **Docker:** Compose configuration and both image builds passed. A fresh stack
  passed HTTP checks for frontend delivery, API proxying, first-admin setup,
  admin creation, JWT login, and restricted public settings. Temporary test
  databases were separate from the application's database volume.
- **Hygiene:** `git diff --check` and entrypoint shell syntax checks passed. Local
  agent settings remain on disk and are now ignored.

## Remaining owner decisions and limits

- Select a license and add its full text before presenting the project as open
  source. No license was assigned during this review.
- Review private vulnerability reporting, secret scanning, and required CI checks
  in the public repository's settings. Remote CI results are tracked separately
  from the local validation recorded here.
- A deployment must create its first admin before public exposure. AI provider
  access, proxy rate limits, and protection of stored credentials/backups remain
  operator responsibilities; see [SECURITY.md](SECURITY.md).
- HSTS subdomain/preload choices depend on the deployment domain. The default
  configuration deliberately leaves both off and reports Django W005/W021;
  [INSTALL.md](INSTALL.md) explains the choices.
- Vite reports large output chunks, including the diagram libraries. This is a
  performance follow-up, not a failed build. No complete browser interaction or
  load-testing campaign was performed.
- Automated secret and dependency scans report known patterns/advisories. They
  cannot prove that all sensitive data or security defects are absent.

## Documentation follow-up

The documentation index now covers first use, roles, configuration, public HTTPS
hosting, backups/restores, recovery, and troubleshooting. The API reference was
rewritten for the current table/AI schemas and ownership rules. Incorrect claims
about total audit coverage, universal soft deletion, and complete composition-tree
enforcement were removed. Fresh installs now have an explicit initial-vault
bootstrap procedure.

Validation includes all 59 documented API paths resolving in Django, checked
Markdown links/anchors and JSON examples, a successful first-admin/first-vault/API
walkthrough against disposable PostgreSQL, and successful syntax validation of
both Nginx configurations with a disposable certificate. The Linux deployment
recipe still requires verification on the operator's actual host/domain; this
review did not publish or configure a public service.

The documented custom-format backup was restored into a separate empty database
and the example item records were verified. Final documentation checks covered
14 Markdown files, 81 relative links/anchors, 7 JSON blocks, and 38 shell command
blocks. The final publication-file secret scan found no leaks. Temporary API and
database processes were stopped after verification.
