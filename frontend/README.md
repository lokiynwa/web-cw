# Frontend (React + Vite)

Minimal coursework-demo frontend for the Student Affordability Intelligence API.

## Run locally

```bash
cd frontend
cp .env.example .env
npm install
npm run dev
```

Default local URL: `http://127.0.0.1:5173`

## Environment

- `VITE_API_BASE_URL`: API base path/URL used by the client (default `/api/v1`)
- `VITE_DEV_PROXY_TARGET`: backend target for dev proxy (default `http://127.0.0.1:8000`)

When `VITE_API_BASE_URL=/api/v1`, Vite proxy forwards API calls to the backend during development.
