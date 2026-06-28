"""Tests for authentication and JWT session behavior."""

from fastapi.testclient import TestClient
from sqlalchemy import select

from app import app
from db_models import RefreshToken, User
from tests.conftest_saas import (
    auth_headers,
    clear_test_database_override,
    register_user,
    use_test_database,
)


def test_register_hashes_password_and_returns_jwt_pair(tmp_path) -> None:
    SessionLocal = use_test_database(tmp_path)
    client = TestClient(app)

    data = register_user(client)

    assert data["token_type"] == "bearer"
    assert data["access_token"]
    assert data["refresh_token"]
    assert data["user"]["email"] == "creator@example.com"

    with SessionLocal() as db:
        user = db.scalar(select(User).where(User.email == "creator@example.com"))
        assert user is not None
        assert user.password_hash != "strong-password-123"
        assert user.password_hash.startswith("$2")
        assert db.scalar(select(RefreshToken).where(RefreshToken.user_id == user.id))

    clear_test_database_override()


def test_login_me_refresh_and_logout_flow(tmp_path) -> None:
    use_test_database(tmp_path)
    client = TestClient(app)
    registered = register_user(client)

    login_response = client.post(
        "/auth/login",
        json={
            "email": "creator@example.com",
            "password": "strong-password-123",
            "remember_me": True,
        },
    )
    login_data = login_response.json()

    assert login_response.status_code == 200
    assert client.get("/auth/me", headers=auth_headers(login_data)).status_code == 200

    refresh_response = client.post(
        "/auth/refresh",
        json={"refresh_token": login_data["refresh_token"]},
    )
    refreshed = refresh_response.json()

    assert refresh_response.status_code == 200
    assert refreshed["access_token"] != login_data["access_token"]
    assert refreshed["refresh_token"] != login_data["refresh_token"]

    logout_response = client.post(
        "/auth/logout",
        json={"refresh_token": refreshed["refresh_token"]},
        headers=auth_headers(refreshed),
    )
    assert logout_response.status_code == 200

    reuse_response = client.post(
        "/auth/refresh",
        json={"refresh_token": refreshed["refresh_token"]},
    )
    assert reuse_response.status_code == 401

    assert registered["user"]["id"] == refreshed["user"]["id"]
    clear_test_database_override()


def test_protected_route_requires_token(tmp_path) -> None:
    use_test_database(tmp_path)
    client = TestClient(app)

    response = client.get("/api/dashboard")

    assert response.status_code == 401
    clear_test_database_override()
