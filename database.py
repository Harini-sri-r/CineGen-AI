"""Database configuration for CineGen AI."""

from __future__ import annotations

import os
from collections.abc import Generator
from pathlib import Path
from urllib.parse import parse_qsl, unquote, urlsplit

from dotenv import load_dotenv
from sqlalchemy import create_engine
from sqlalchemy.engine import URL
from sqlalchemy.orm import DeclarativeBase, Session, sessionmaker


load_dotenv(Path(__file__).with_name(".env"))

DEFAULT_SQLITE_URL = "sqlite:///./cinegen_ai.db"
DATABASE_URL = None


def _normalize_database_url(raw_database_url: str) -> str:
    """Normalize database URLs so special characters in passwords are escaped."""
    if raw_database_url.startswith("sqlite"):
        return raw_database_url

    try:
        parsed_url = urlsplit(raw_database_url)
    except ValueError:
        return raw_database_url

    if not parsed_url.scheme or not parsed_url.hostname:
        return raw_database_url

    try:
        port = parsed_url.port
    except ValueError:
        return raw_database_url

    database_name = unquote(parsed_url.path.lstrip("/")) if parsed_url.path else None
    query = dict(parse_qsl(parsed_url.query, keep_blank_values=True))
    return URL.create(
        drivername=parsed_url.scheme,
        username=unquote(parsed_url.username) if parsed_url.username else None,
        password=(
            unquote(parsed_url.password)
            if parsed_url.password is not None
            else None
        ),
        host=parsed_url.hostname,
        port=port,
        database=database_name,
        query=query,
    ).render_as_string(hide_password=False)


DATABASE_URL = _normalize_database_url(os.getenv("DATABASE_URL", DEFAULT_SQLITE_URL))


def _connect_args(database_url: str) -> dict[str, object]:
    if database_url.startswith("sqlite"):
        return {"check_same_thread": False}

    return {}


engine = create_engine(
    DATABASE_URL,
    connect_args=_connect_args(DATABASE_URL),
    future=True,
    pool_pre_ping=not DATABASE_URL.startswith("sqlite"),
)

SessionLocal = sessionmaker(
    autocommit=False,
    autoflush=False,
    bind=engine,
    expire_on_commit=False,
    future=True,
)


class Base(DeclarativeBase):
    """Base class for SQLAlchemy ORM models."""


def get_db() -> Generator[Session, None, None]:
    """Yield a database session for FastAPI dependencies."""
    db = SessionLocal()
    try:
        yield db
    finally:
        db.close()


def init_db() -> None:
    """Create tables only when explicitly enabled for local development."""
    if os.getenv("CINEGEN_AUTO_CREATE_DB", "false").strip().lower() not in {
        "1",
        "true",
        "yes",
        "on",
    }:
        return

    import db_models  # noqa: F401

    Base.metadata.create_all(bind=engine)
