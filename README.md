# Student Affordability Intelligence API

FastAPI coursework skeleton with modular architecture and extension points for services and repositories.

## Project Structure

- `app/main.py`: FastAPI app entrypoint and factory
- `app/config.py`: environment-based settings
- `app/db.py`: database engine/session setup
- `app/models/`: ORM models package
- `app/schemas/`: Pydantic schemas package
- `app/routers/`: API route registration and endpoints
- `app/services/`: service layer stubs
- `app/repos/`: repository layer stubs
- `scripts/`: utility scripts (run server, bootstrap DB)
- `tests/`: test suite

## Quickstart

```bash
python -m venv .venv
source .venv/bin/activate
pip install -e '.[dev]'
cp .env.example .env
./scripts/start.sh
```

Run tests:

```bash
pytest
```

## Docker Compose (Local API + PostgreSQL)

Start the local stack:

```bash
docker compose up --build
```

Run detached:

```bash
docker compose up -d --build
```

Stop and remove containers:

```bash
docker compose down
```

Stop and remove containers plus Postgres data volume:

```bash
docker compose down -v
```

Verify API health:

```bash
curl http://localhost:8000/api/v1/health
```

The API container is wired to PostgreSQL through:

```text
DATABASE_URL=postgresql+psycopg://student:student@postgres:5432/student_affordability
```
