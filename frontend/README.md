# FinGuard control panel (frontend)

React 18 + TypeScript + Vite 5 + Tailwind CSS 3 + Recharts + react-router 6.

## Run

```bash
npm install
npm run dev        # http://localhost:5173, proxies /api and /v1 to http://localhost:8000
npm run build      # tsc --noEmit && vite build -> dist/
npm run lint       # eslint (typescript-eslint + react-hooks)
npm test           # vitest smoke tests (pages mount with a mocked fetch)
```

Start the backend first (see `docs/api-contract.md`), e.g.
`FINGUARD_ADMIN_PASSWORD=pw uvicorn app.main:app --port 8000`, then sign in with that password.
Use "Seed demo apps" and "Generate simulated traffic" on the Overview page to get data.

## Docker

`Dockerfile` builds with Node and serves `dist/` with nginx (`nginx.conf`): SPA history fallback,
`/api/` and `/v1/` proxied to `http://backend:8000` (compose service name `backend`), buffering off for `/v1/`.

## Notes

- Every figure comes from the API; no API keys live in the frontend.
- The Demo page keeps its last results in `localStorage` so it still works if the backend is unreachable.
- Demo shortcuts: arrows (prev/next), R (run current), A (run all), P (presentation), Esc (exit).
