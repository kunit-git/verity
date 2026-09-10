# Verity frontend

React 19, TypeScript, Vite, and Tailwind CSS. See the root [README](../README.md)
for full-stack setup and [INSTALL.md](../INSTALL.md) for production deployment.

Use Node.js 24 and install the locked dependencies with `npm ci`.

```bash
npm run dev                        # http://localhost:5173
npm run lint -- --max-warnings=0
npm run build                      # static files in dist/
```

The development proxy sends `/api` to `http://127.0.0.1:8000` by default.
`VITE_API_PROXY_TARGET` overrides it for Docker, and `VITE_USE_POLLING=true`
enables file polling for bind mounts. These are build/server settings; never put
credentials in `VITE_*` variables.

For UI behavior and roles see the [user guide](../docs/user-guide.md).
Configuration and proxy requirements are in the [configuration reference](../docs/configuration.md).
