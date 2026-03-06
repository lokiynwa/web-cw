# Student Affordability Intelligence API

FastAPI coursework project for comparing student affordability using:
- rental listing data (imported from CSV)
- moderated crowd submissions (e.g. `PINT`, `TAKEAWAY`)

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
- `DATABASE_URL` - SQLAlchemy URL

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

## 6) API Keys for Protected Endpoints

Public read endpoints are open. Write/moderation endpoints require `X-API-Key`.

Create contributor key:

```bash
python scripts/create_api_key.py --name contributor-local --role contributor
```

Create moderator key:

```bash
python scripts/create_api_key.py --name moderator-local --role moderator
```

Store the printed raw key securely; only hashes are stored in DB.

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
