"""Database bootstrap script placeholder."""

from app.db import Base, engine


def create_tables() -> None:
    """Create all registered database tables."""
    Base.metadata.create_all(bind=engine)


if __name__ == "__main__":
    create_tables()
