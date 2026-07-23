from datetime import datetime

from fastapi.testclient import TestClient

from app.db.users import (
    DuplicateUserProfileError,
    UserProfileRecord,
    normalize_profile_name,
)
from app.main import app


def user_record(
    user_id: str = "d6ecb5a4-40b7-4bfe-a55f-4086fb9fd0b4",
    display_name: str = "Shiva",
) -> UserProfileRecord:
    return UserProfileRecord(
        id=user_id,
        display_name=display_name,
        created_at=datetime(2026, 7, 23, 12, 30),
    )


def test_profile_name_normalization_is_case_and_space_insensitive() -> None:
    assert normalize_profile_name("  Shiva   Chandra ") == "shiva chandra"


def test_users_endpoint_lists_profiles(monkeypatch) -> None:
    async def fake_fetch():
        return [user_record()]

    monkeypatch.setattr("app.main.fetch_user_profiles", fake_fetch)
    monkeypatch.setattr("app.main.settings.routewise_api_key", "")
    client = TestClient(app)

    response = client.get("/users")

    assert response.status_code == 200
    assert response.json()["users"][0]["display_name"] == "Shiva"


def test_users_endpoint_creates_trimmed_profile(monkeypatch) -> None:
    async def fake_create(display_name: str):
        assert display_name == "Shiva Chandra"
        return user_record(display_name=display_name)

    monkeypatch.setattr("app.main.create_user_profile", fake_create)
    monkeypatch.setattr("app.main.settings.routewise_api_key", "")
    client = TestClient(app)

    response = client.post("/users", json={"display_name": "  Shiva   Chandra  "})

    assert response.status_code == 201
    assert response.json()["display_name"] == "Shiva Chandra"


def test_users_endpoint_rejects_duplicate_profile(monkeypatch) -> None:
    async def fake_create(display_name: str):
        raise DuplicateUserProfileError("A user with this display name already exists.")

    monkeypatch.setattr("app.main.create_user_profile", fake_create)
    monkeypatch.setattr("app.main.settings.routewise_api_key", "")
    client = TestClient(app)

    response = client.post("/users", json={"display_name": "Shiva"})

    assert response.status_code == 409
    assert "already exists" in response.json()["detail"]


def test_users_endpoint_deletes_profile(monkeypatch) -> None:
    async def fake_delete(user_id: str):
        return user_id == "d6ecb5a4-40b7-4bfe-a55f-4086fb9fd0b4"

    monkeypatch.setattr("app.main.delete_user_profile", fake_delete)
    monkeypatch.setattr("app.main.settings.routewise_api_key", "")
    client = TestClient(app)

    response = client.delete("/users/d6ecb5a4-40b7-4bfe-a55f-4086fb9fd0b4")

    assert response.status_code == 204


def test_users_endpoint_requires_configured_api_key(monkeypatch) -> None:
    monkeypatch.setattr("app.main.settings.routewise_api_key", "secret")
    client = TestClient(app)

    response = client.get("/users")

    assert response.status_code == 401
