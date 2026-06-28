"""Shared SaaS test helpers."""

from __future__ import annotations

from collections.abc import Generator

from sqlalchemy import create_engine
from sqlalchemy.orm import Session, sessionmaker

import db_models  # noqa: F401
from database import Base, get_db
from app import app


def use_test_database(tmp_path) -> sessionmaker[Session]:
    """Override FastAPI DB sessions with a temporary SQLite database."""
    engine = create_engine(
        f"sqlite:///{tmp_path / 'cinegen_test.db'}",
        connect_args={"check_same_thread": False},
        future=True,
    )
    TestingSessionLocal = sessionmaker(
        autocommit=False,
        autoflush=False,
        bind=engine,
        expire_on_commit=False,
        future=True,
    )
    Base.metadata.create_all(bind=engine)

    def override_get_db() -> Generator[Session, None, None]:
        db = TestingSessionLocal()
        try:
            yield db
        finally:
            db.close()

    app.dependency_overrides[get_db] = override_get_db
    return TestingSessionLocal


def clear_test_database_override() -> None:
    """Clear FastAPI dependency overrides after a test."""
    app.dependency_overrides.clear()


def register_user(client, email: str = "creator@example.com") -> dict:
    """Register a user and return the token response."""
    response = client.post(
        "/auth/register",
        json={
            "username": email.split("@", 1)[0],
            "email": email,
            "password": "strong-password-123",
        },
    )
    assert response.status_code == 201
    return response.json()


def auth_headers(token_response: dict) -> dict[str, str]:
    """Build bearer auth headers."""
    return {"Authorization": f"Bearer {token_response['access_token']}"}
