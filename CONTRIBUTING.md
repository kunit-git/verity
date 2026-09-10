# Contributing

Use the development instructions in [README.md](README.md). Keep changes focused,
explain the problem and resulting behavior, and include the checks you ran in your
pull request. Add regression tests for API changes, especially permission checks,
vault isolation, and invalid input.

Before submitting, run:

```bash
# From the repository root, with PostgreSQL running
source .venv/bin/activate
cd backend
python manage.py check
python manage.py makemigrations --check --dry-run
pytest -q
cd ../frontend
npm ci
npm run lint -- --max-warnings=0
npm run build
```

Commit migrations when changing Django models and update the frontend lockfile
when changing npm dependencies. Use synthetic data in tests and examples. Keep
credentials, database exports, and local agent settings out of commits.

For security reports, follow [SECURITY.md](SECURITY.md).

## Reporting bugs and proposing changes

Use the repository issue tracker for reproducible non-security bugs or proposals.
Include expected versus actual behavior, the commit (`git rev-parse HEAD`), relevant
runtime versions, and steps with synthetic data. Check existing issues first.
Discuss changes to authentication, data ownership, schema, or user workflows before
building a large feature. No response-time commitment is currently published.

## Documentation changes

The [documentation index](docs/README.md) maps guides to their audiences. Update
user/API/configuration documentation with behavior changes, and keep examples
consistent with serializers, URL routes, permissions, and the frontend labels.
Do not promise anonymous access, complete audit coverage, recovery guarantees, or
features absent from the implementation.

For documentation-only changes, check relative links/anchors, JSON/shell examples,
and command working directories. Exercise a changed setup or integration example
against disposable data. Backend behavior changes still require regression tests
and the full backend suite. Keep screenshots and examples free of private data.
