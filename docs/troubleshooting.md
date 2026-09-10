# Troubleshooting

[Documentation index](README.md) · [Configuration](configuration.md)

## Setup and login

| Symptom | Check and action |
| --- | --- |
| Cannot connect to localhost:5173 | Run `docker compose ps` and inspect frontend/backend logs. Wait for startup/migrations. If running on another host, use the HTTPS deployment; localhost refers to the browser's own machine. |
| Port already allocated | Another service owns 5432, 8000, or 5173. Stop the conflicting evaluation service or use a local Compose override and matching API/DB settings. Do not delete an existing database volume to fix a port conflict. |
| Setup says database unavailable | Inspect backend logs and DB health; verify host, port, name, role, and password. `db` is the hostname inside Compose; host development uses localhost. |
| Setup returns 409 | A site admin already exists. Log in or follow account recovery instead of attempting setup again. |
| Setup/login returns 429 | A setup or proxy rate limit was reached. Wait and check the client IP/proxy settings. |
| Login returns 401 | Verify credentials and that the account is active. Self-registration remains locked until a site admin unlocks it. |
| No vaults available after fresh setup | Create the initial vault with the bootstrap command in the [quick start](../README.md#quick-start-with-docker), then reload. `seed_data` alone does not create a vault. |
| A newly added user has no vault | Account activation and membership are separate. Add the active account to the intended vault in **Vaults**. |
| Provisioning ignores a password in backend/.env | `ensure_admin` reads its defaults from the process environment. Use the interactive provisioning command in INSTALL.md or explicitly export the variable. |

## Permissions and data

| Symptom | Check and action |
| --- | --- |
| API returns 403 for content | Select a vault, confirm membership, and check the vault role and lock state. Site admins also need an active vault for content APIs. |
| Vault admin cannot access another vault's members | Administration is checked against the vault in the URL; being admin of a different active vault does not grant access. |
| Changes appear in an unexpected vault | Active vault is stored on the account, so another tab or API client can change it. Use separate accounts for concurrent work in different vaults. |
| An item is missing | Check the selected vault, filters, and whether it was deleted. There is no general undelete UI; consult an operator before database recovery. |
| Table API returns 400 | Supply the current `sources` plus `columns` schema, unique source names, valid references in the active vault, and a seed as the first source. Older `column_kind`/`label` payloads are obsolete. |
| Formula is empty | Check numeric field values, source names, null traversal results, and division by zero. Formulas support arithmetic, not spreadsheet functions. |
| Document does not include all descendants | The generator has a depth limit and skips already-visited items. Check composition links and saved data. |
| Document generation is blocked | Check active-vault access and the user's mailbox limit. Remove unneeded artifacts or ask a site admin to increase the limit. |
| AI action returns 404 | The action may be missing, from another vault, or owned by another user. Only its owner can resolve it. |
| AI action returns 403 | Acceptance requires editor/admin rights in an unlocked active vault. |

## Public deployment

| Symptom | Check and action |
| --- | --- |
| 400 / DisallowedHost | `ALLOWED_HOSTS` must contain the public hostname without scheme or port, and Nginx must forward the host. Restart the backend after changing configuration. |
| Repeated HTTPS redirects | Confirm `TRUST_PROXY_HEADERS=True` only behind the trusted proxy, `X-Forwarded-Proto` is overwritten with the real scheme, and Gunicorn is not directly exposed. |
| `/api/...` returns HTML instead of JSON | Ensure `/api/` routes to Gunicorn before the SPA fallback. The frontend uses same-origin `/api/v1`. |
| A deep frontend URL returns 404 | Use the sample Nginx `try_files ... /index.html` fallback. |
| 502 Bad Gateway | Inspect `systemctl status verity`, journal logs, and the loopback Gunicorn listener. Missing production variables or a database error may stop startup. |
| Unstyled Django admin | Run `collectstatic`, publish `staticfiles/` to the dedicated static directory, and check the Nginx `/static/` alias and filesystem permissions. |
| TLS issuance/renewal fails | Verify DNS, public port 80, the ACME webroot location, and Certbot logs. Fix a stale AAAA record if the host is not serving IPv6. |
| 403 CSRF failure in Django admin | Use the same HTTPS origin and verify forwarded host/scheme. Adding a CORS origin alone does not configure Django session CSRF trust. |
| AI response times out | Check provider availability and credentials, outbound connectivity, worker capacity, and aligned Gunicorn/Nginx timeouts. Responses can be buffered by the provider adapters even with proxy buffering disabled. |
| Deploy check returns W005/W021 | These concern optional HSTS subdomain/preload policies; review the domain-specific decision in INSTALL.md rather than disabling all security checks. |

## Development checks

Run commands from the directories shown in README.md. Use Node.js 24 and install
with `npm ci` to reproduce the lockfile. Python must be 3.12+; tests require a
running PostgreSQL instance and a role allowed to create `test_<DB_NAME>`.
If pytest cannot connect, check database settings before investigating test logic.
Vite's large-chunk warning is a performance notice, not a failed TypeScript build.

## Asking for help

For a reproducible non-security bug, include the Git commit (`git rev-parse HEAD`),
OS, Python/Node or Docker versions, installation method, expected/actual behavior,
steps using synthetic data, and redacted logs. For security issues use
[SECURITY.md](../SECURITY.md). Do not attach `.env`, database dumps, bearer tokens,
AI keys, or real customer content to a public issue.
