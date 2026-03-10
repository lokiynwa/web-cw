# Student Affordability Intelligence API

FastAPI coursework project for comparing student affordability using:
- rental listing data (imported from CSV)
- live crowd submissions (e.g. `PINT`, `TAKEAWAY`) with post-publication moderator review

## Live Demo Links

- Frontend: https://frontend-production-a7b4.up.railway.app
- Backend API: https://backend-production-ab5cb.up.railway.app
- Swagger/OpenAPI: https://backend-production-ab5cb.up.railway.app/docs

## 0) Final End-to-End Usage (Exam Flow)

### Local backend + local frontend

Terminal 1 (backend):

```bash
python -m venv .venv
source .venv/bin/activate
python -m pip install --upgrade pip
python -m pip install -e '.[dev]'
cp .env.example .env
./scripts/run_local.sh
```

Terminal 2 (frontend):

```bash
cd frontend
cp .env.example .env
npm ci
npm run dev
```

Open `http://127.0.0.1:5173`.

### Deployed backend + deployed frontend

1. Deploy backend service using section **9**.
2. Deploy frontend service using section **10**.
3. In frontend Railway variables, set:
```bash
VITE_API_BASE_URL=https://backend-production-ab5cb.up.railway.app/api/v1
```
4. Verify:
```bash
curl -sS https://backend-production-ab5cb.up.railway.app/api/v1/health
curl -sSI https://frontend-production-a7b4.up.railway.app | head -n 1
```

### Core product demo flow (website)

1. Open frontend dashboard and show city/area affordability outputs.
2. Register a normal user account and log in.
3. Submit one `PINT` or `TAKEAWAY` observation from the dashboard form.
4. Show the submission is `ACTIVE` immediately and reflected in analytics.
5. Log in as a moderator account.
6. Flag or remove the same submission.
7. Show analytics update to reflect moderator action (`REMOVED` excluded, `ACTIVE` included).

Notes:
- Normal website users do not need contributor API keys.
- Moderation is post-publication review, not pre-publication approval.

### MCP local usage (advanced extension)

```bash
./scripts/run_mcp_local.sh
```

With MCP Inspector:

```bash
npx @modelcontextprotocol/inspector ./scripts/run_mcp_local.sh
```

### MCP remote usage (HTTP transport)

Run backend with MCP HTTP enabled (`APP_RUNTIME_MODE=both` or `mcp`, and `MCP_HTTP_ENABLED=true`), then connect a client/Inspector to:

- `https://<your-backend-domain>/mcp`

Recommended for browser clients:
- set `MCP_HTTP_VALIDATE_ORIGIN=true`
- set `MCP_HTTP_ALLOWED_ORIGINS` to your frontend/client domains.

### MCP parity demo (optional)

Use MCP only as an advanced extension:
1. Query city analytics via REST.
2. Query equivalent tool via MCP.
3. Show matching outputs from shared service-layer logic.

### Live Demo Checklist (Oral Exam)

Before demo:
- Backend live URL: `https://backend-production-ab5cb.up.railway.app`
- Frontend live URL: `https://frontend-production-a7b4.up.railway.app`
- Swagger/OpenAPI: `https://backend-production-ab5cb.up.railway.app/docs`
- Prepare two accounts:
  - normal user account (for login + submission)
  - moderator account (role `MODERATOR` for review actions)

Exam path:
1. Show city/area affordability on the dashboard.
2. Log in as normal user.
3. Submit a `PINT` or `TAKEAWAY` value.
4. Show immediate analytics inclusion (`ACTIVE` submission).
5. Log in as moderator.
6. Flag or remove the same submission.
7. Show analytics update based on moderation state.

## 1) Quick Local Setup

Prerequisites:
- Python 3.11+
- `pip`

```bash
python -m venv .venv
source .venv/bin/activate
python -m pip install --upgrade pip
python -m pip install -e '.[dev]'
cp .env.example .env
./scripts/run_local.sh
```

API base URL: `http://127.0.0.1:8000/api/v1`

Health check:

```bash
curl http://127.0.0.1:8000/api/v1/health
```

## 2) Environment Variables

Copy `.env.example` to `.env` and adjust values as needed.

Core settings:
- `APP_NAME` - API title in docs
- `APP_VERSION` - API version string
- `DEBUG` - `true/false`
- `API_PREFIX` - default `/api/v1`
- `APP_RUNTIME_MODE` - `rest` (default), `mcp`, or `both`
- `DATABASE_URL` - SQLAlchemy URL
- `AUTH_JWT_SECRET` - secret used to sign bearer tokens
- `AUTH_JWT_EXP_MINUTES` - login token expiry in minutes
- `AUTH_PASSWORD_MIN_LENGTH` - minimum password length for account registration
- `MCP_HTTP_ENABLED` - enable HTTP MCP mounting in `app.main`
- `MCP_HTTP_MOUNT_PATH` - mount path for MCP HTTP transport (default `/mcp`)
- `MCP_HTTP_STATELESS` - streamable HTTP stateless mode toggle (default `true`)
- `MCP_HTTP_VALIDATE_ORIGIN` - validate request `Origin` header for MCP HTTP
- `MCP_HTTP_ALLOWED_ORIGINS` - comma-separated allowlist (e.g. `https://your-ui.app,https://chat.openai.com`)
- `MCP_HTTP_ALLOW_REQUESTS_WITHOUT_ORIGIN` - allow non-browser clients with no `Origin` header
- `MCP_HTTP_PUBLIC_READ_TOOLS` - when `true`, read-only MCP tools can be called anonymously

API key and rate-limit settings:
- `API_KEY_ENABLED`
- `API_KEY_HEADER_NAME` (default `X-API-Key`)
- `API_KEY_SECRET`
- `RATE_LIMIT_ENABLED`
- `RATE_LIMIT_REQUESTS`
- `RATE_LIMIT_WINDOW_SECONDS`

Affordability scoring settings (optional overrides):
- Weights: `AFFORDABILITY_RENT_WEIGHT`, `AFFORDABILITY_PINT_WEIGHT`, `AFFORDABILITY_TAKEAWAY_WEIGHT`
- Rent bounds: `AFFORDABILITY_RENT_FLOOR_GBP_WEEKLY`, `AFFORDABILITY_RENT_CEILING_GBP_WEEKLY`
- Pint bounds: `AFFORDABILITY_PINT_FLOOR_GBP`, `AFFORDABILITY_PINT_CEILING_GBP`
- Takeaway bounds: `AFFORDABILITY_TAKEAWAY_FLOOR_GBP`, `AFFORDABILITY_TAKEAWAY_CEILING_GBP`

Runtime modes:
- REST API only (default): `APP_RUNTIME_MODE=rest`
- MCP over HTTP only: `APP_RUNTIME_MODE=mcp` and `MCP_HTTP_ENABLED=true`
- REST + MCP over HTTP: `APP_RUNTIME_MODE=both` and `MCP_HTTP_ENABLED=true`

MCP HTTP security model:
- Origin validation is enabled by default (`MCP_HTTP_VALIDATE_ORIGIN=true`).
- Sensitive MCP tools (write/moderation) require API keys by default.
- Read-only MCP tools can be public or authenticated depending on `MCP_HTTP_PUBLIC_READ_TOOLS`.
- API key checks reuse the same hashed `api_keys` table as REST protected endpoints.

Local stdio MCP mode (for local MCP clients) remains available:

```bash
./scripts/run_mcp_local.sh
```

## 3) Run with Docker (API + PostgreSQL)

Prerequisites:
- Docker Desktop (or Docker Engine + Compose)

Start stack:

```bash
docker compose up --build
```

Run in background:

```bash
docker compose up -d --build
```

Apply migrations in container:

```bash
docker compose exec api python -m alembic upgrade head
```

Stop stack:

```bash
docker compose down
```

Reset DB volume:

```bash
docker compose down -v
```

## 4) Dataset Source

This project uses a publicly available dataset of UK student accommodation listings sourced from Kaggle.

Chow, T. (2023) *UK Student Accommodation Dataset*. Available at:  
https://www.kaggle.com/datasets/thomaschow0716/uk-student-accomodation  
(Accessed: 18 March 2026).

Accommodation data should be downloaded from Kaggle and placed in `raw_data/`.

- Dataset link: `https://www.kaggle.com/datasets/thomaschow0716/uk-student-accomodation`
- Expected local file path: `raw_data/accommodation.csv`

If the downloaded filename differs, rename it to `accommodation.csv` or pass a custom path to the scripts below.

## 5) Import and Transform the Dataset

Put your CSV in `raw_data/` (default expected path: `raw_data/accommodation.csv`).

1. Optional audit report:

```bash
python scripts/audit_accommodation_csv.py raw_data/accommodation.csv
```

2. Import immutable raw rows (`import_batches` + `raw_listings`):

```bash
python scripts/import_accommodation_raw.py raw_data/accommodation.csv
```

3. Transform raw rows into cleaned rows (`cleaned_listings`):

```bash
python scripts/transform_raw_to_cleaned.py --cleaning-version v1
```

Notes:
- Run migrations first (`python -m alembic upgrade head`).
- Transform is safe to rerun for the same `cleaning_version` (no duplicate cleaned rows for the same raw row/version).

## 6) Authentication Model

Primary website auth model:
- Users register and log in with account credentials (`/api/v1/auth/register`, `/api/v1/auth/login`).
- Frontend uses bearer token auth for protected submission and moderation workflows.
- New submissions are `ACTIVE` immediately and included in analytics.
- Moderators review after publication and can set `FLAGGED`, `REMOVED`, or restore `ACTIVE`.
- Submission ownership is enforced: normal users can manage only their own submissions; moderators can manage all.

Protected endpoints:
- Website users should use bearer token auth for submission write/update/delete and moderation actions.
- Public read analytics endpoints remain open for demo browsing without login.

Legacy API keys (optional):
- API keys are still supported for developer/admin/MCP scenarios.
- They are no longer required for normal website usage.
- Keys can be created with:

```bash
python scripts/create_api_key.py --name contributor-local --role contributor
python scripts/create_api_key.py --name moderator-local --role moderator
```

Only hashed keys are stored in the database.

Moderation transition model (post-publication):
- `ACTIVE -> FLAGGED`
- `ACTIVE -> REMOVED`
- `FLAGGED -> ACTIVE`
- `FLAGGED -> REMOVED`
- `REMOVED -> ACTIVE`

## 7) Run Tests

Run lint (if configured) + full test suite:

```bash
./scripts/test.sh
```

Useful subsets:

```bash
./scripts/test.sh tests/test_cleaning_logic.py -q
./scripts/test.sh tests/test_affordability_logic.py -q
./scripts/test.sh tests/test_api_integration.py -q
```

## 8) API Documentation

Primary coursework API docs (PDF):
- `docs/api-documentation.pdf`

Regenerate the PDF from FastAPI OpenAPI schema:

```bash
./scripts/export_api_docs_pdf.sh
```

Secondary interactive docs (when server is running):
- Swagger UI: `http://127.0.0.1:8000/docs`
- ReDoc: `http://127.0.0.1:8000/redoc`

Concise markdown reference for coursework write-up:
- `docs/API_REFERENCE.md`

## 9) Railway Deployment (Backend Only)

Monorepo-style backend service setup (Railway UI):

1. Service root directory:
- `.` (this repo root is the backend)

2. Build and start:
- Build Command:
```bash
python -m pip install --upgrade pip && python -m pip install -e '.[dev]'
```
- Start Command:
```bash
./scripts/start.sh
```

3. Required backend variables:
```bash
APP_RUNTIME_MODE=rest
DEBUG=false
API_PREFIX=/api/v1
CORS_ALLOWED_ORIGINS=https://frontend-production-a7b4.up.railway.app
RUN_MIGRATIONS_ON_START=true
DATABASE_URL=${{Postgres.DATABASE_URL}}
AUTH_JWT_SECRET=<secure-random-secret>
```

4. PostgreSQL linkage:
- Add a PostgreSQL service in the same Railway project.
- In backend service variables, set `DATABASE_URL` as a reference to the Postgres service `DATABASE_URL`.

5. Public domain:
- Backend service -> `Settings` -> `Networking` -> `Generate Domain`.

6. Verify deployment (3 commands):
```bash
export BASE_URL="https://backend-production-ab5cb.up.railway.app"
curl -sS "$BASE_URL/api/v1/health"
curl -sSI "$BASE_URL/docs" | head -n 1
curl -sS "$BASE_URL/openapi.json" | grep -E '"title"|"version"' | head -n 2
```

Expected:
- health returns JSON with `status: "ok"`
- docs responds `HTTP/2 200`
- openapi output includes API title/version

Notes:
- `scripts/start.sh` uses Railway `PORT`, runs migrations (if enabled), then starts Uvicorn in production mode.
- Railway Postgres URL formats (`postgres://` / `postgresql://`) are normalized in app config.
- `AUTH_JWT_SECRET` must be set to a non-default value for Railway startup.

## 10) Railway Deployment (Frontend Service)

Deploy the React/Vite frontend as a separate Railway service from the same monorepo.

1. Service root directory:
- `frontend`

2. Build and start:
- Build Command:
```bash
npm ci
npm run build:prod
```
- Start Command:
```bash
npm run start
```

3. Required frontend variable:
```bash
VITE_API_BASE_URL=https://backend-production-ab5cb.up.railway.app/api/v1
```

`npm run build:prod` now validates `VITE_API_BASE_URL` in Railway builds and fails fast if missing/placeholder.

4. Domain:
- Frontend service -> `Settings` -> `Networking` -> `Generate Domain`.

5. Quick verification:
```bash
export FRONTEND_URL="https://frontend-production-a7b4.up.railway.app"
curl -sSI "$FRONTEND_URL" | head -n 1
curl -sS "$FRONTEND_URL" | head -n 5
```

Expected:
- returns `HTTP/2 200`
- serves the built SPA HTML.

## 10.1) Seed Railway PostgreSQL (One-time / On-demand)

Railway deploy does not auto-seed coursework data. After backend deploy, run the dataset pipeline explicitly from your machine against the remote PostgreSQL URL.

```bash
scripts/seed_remote_db.sh \
  --database-url "<your-railway-postgres-database-url>" \
  --csv-path raw_data/accommodation.csv \
  --cleaning-version v1
```

This runs:
1. `alembic upgrade head`
2. raw import (`import_batches` + `raw_listings`)
3. cleaned transform (`cleaned_listings`)

## 10.2) Fastest Railway Deployment Sequence

1. Create Railway Postgres service.
2. Deploy backend service (root `.`) with `./scripts/start.sh`.
3. Set backend vars including `DATABASE_URL` + `AUTH_JWT_SECRET`.
4. Generate backend domain and verify `/api/v1/health`.
5. Deploy frontend service (root `frontend`) with `npm run build:prod` and `npm run start`.
6. Set `VITE_API_BASE_URL` to backend `/api/v1` URL.
7. Run `scripts/seed_remote_db.sh` once to load dataset into Railway Postgres.
8. Verify backend + frontend endpoints from Section 9/10.

## 11) MCP Support

This project includes MCP server support in addition to REST.

What MCP means here:
- The same affordability/rent/cost business logic is exposed as MCP tools.
- You can run MCP in local stdio mode for local clients and MCP Inspector.
- You can also expose MCP over HTTP (streamable HTTP transport) for hosted environments.

Available MCP tools (current):
- `get_city_rent_analytics`
- `get_area_rent_analytics`
- `list_city_areas_by_affordability`
- `get_city_cost_analytics`
- `get_affordability_score`

### Local MCP Server (stdio)

Run local MCP stdio server:

```bash
./scripts/run_mcp_local.sh
```

Equivalent command:

```bash
python -m app.mcp.server
```

### Connect with MCP Inspector

Inspector can start your local stdio server command directly.

From project root:

```bash
npx @modelcontextprotocol/inspector ./scripts/run_mcp_local.sh
```

Or with Python module command:

```bash
npx @modelcontextprotocol/inspector python -m app.mcp.server
```

For HTTP mode (`APP_RUNTIME_MODE=mcp` or `both` with `MCP_HTTP_ENABLED=true`), start the FastAPI app and connect Inspector using Streamable HTTP URL:
- `http://127.0.0.1:8000/mcp`

### MCP Auth and Security

MCP HTTP security is configurable with environment variables:
- Origin validation: `MCP_HTTP_VALIDATE_ORIGIN`, `MCP_HTTP_ALLOWED_ORIGINS`, `MCP_HTTP_ALLOW_REQUESTS_WITHOUT_ORIGIN`
- Public read toggle: `MCP_HTTP_PUBLIC_READ_TOOLS`

Auth model:
- API key checks reuse the same `api_keys` table and hashed key model used by REST.
- Read-only tools can be anonymous when `MCP_HTTP_PUBLIC_READ_TOOLS=true`.
- Sensitive tools are protected by default (contributor or moderator key required).
- Current exposed MCP tools are read-only; write/moderation tool names are pre-classified for secure defaults.

### Architecture Note

The frontend calls REST endpoints only. REST routers and MCP tools both call the same service-layer functions in `app/services/`.

Flow:

`Frontend UI -> REST routers -> services -> database`

`MCP client -> MCP tools -> services -> database`

This keeps business rules centralized and outputs consistent across UI, REST, and MCP transports.
