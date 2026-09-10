# Security

## Reporting a vulnerability

Use the repository's **Security → Report a vulnerability** feature when it is
available. Do not include credentials, private data, or exploit details in a public
issue. If private reporting is not enabled, ask the maintainer for a private
contact channel without disclosing the vulnerability.

Include the affected commit, reproduction steps using synthetic data, impact, and
any suggested fix. There is no guaranteed response time or published support
window yet; use the latest reviewed revision and keep dependencies updated.

## Deployment boundaries

- Docker Compose runs development servers bound to localhost. Use the HTTPS
  deployment instructions in [INSTALL.md](INSTALL.md) for a public server.
- Create the first administrator before exposing a fresh installation. The setup
  endpoint intentionally allows the first visitor to create that account.
- Site administrators control users, vaults, and AI provider configuration. Treat
  these accounts as trusted operators.
- The optional AI assistant sends conversation content and requested vault data
  to the configured provider. Its API key is stored in the database; protect
  database access and backups. Enable AI only for an approved provider.
- Demo data is synthetic and uses a documented demo password. Load it only in an
  isolated evaluation installation.
- Apply rate limits at the reverse proxy, including login, registration, and AI
  requests. Application-level setup throttling uses an in-process cache and is
  not a distributed abuse-prevention service.

Operational procedures for backups, restoration, and account recovery are in
[Operations](docs/operations.md). Public HTTPS access remains authenticated;
there is no anonymous vault-sharing mode. Read the
[data-model boundaries](backend/doc/data-model.md) before relying on locking,
soft deletion, or audit logs as retention or compliance controls.

## Before publishing this repository

Review the complete Git history for credentials and private data. Deleting a secret
from the latest revision does not remove it from history; rotate any real exposed
credentials before publication. Enable private vulnerability reporting and secret
scanning in the public hosting service, and ensure CI passes on the final commit.
