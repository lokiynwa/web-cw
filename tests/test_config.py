"""Configuration behavior tests."""

from app.config import Settings


def test_database_url_normalizes_postgres_scheme() -> None:
    settings = Settings(database_url="postgres://user:pass@localhost:5432/dbname")
    assert settings.database_url == "postgresql+psycopg://user:pass@localhost:5432/dbname"


def test_database_url_normalizes_postgresql_without_driver() -> None:
    settings = Settings(database_url="postgresql://user:pass@localhost:5432/dbname")
    assert settings.database_url == "postgresql+psycopg://user:pass@localhost:5432/dbname"


def test_database_url_preserves_explicit_driver() -> None:
    settings = Settings(database_url="postgresql+psycopg://user:pass@localhost:5432/dbname")
    assert settings.database_url == "postgresql+psycopg://user:pass@localhost:5432/dbname"

