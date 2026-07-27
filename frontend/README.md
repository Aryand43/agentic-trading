# Frontend

React + Vite + Tailwind + Recharts dashboard for the trading pipeline.

## Separation of concerns

| Layer | Role |
|---|---|
| `src/types` | Shared response shapes |
| `src/api` | HTTP client only |
| `src/hooks` | UI state / loading / errors |
| `src/components` | Presentational widgets |
| `App.tsx` | Composition |

Talks to `api/` (FastAPI). Does not import or modify Python `src/`.

## Dev

From repo root, start the API, then:

```bash
npm install
npm run dev
```
