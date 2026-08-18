import sys
from pathlib import Path
from fastapi.testclient import TestClient

EXERCISE_ROOT = Path(__file__).resolve().parents[1]
if str(EXERCISE_ROOT) not in sys.path:
    sys.path.insert(0, str(EXERCISE_ROOT))

from app.main import app

client = TestClient(app)


def test_health_returns_ok():
    response = client.get("/health")
    assert response.status_code == 200
    assert response.json() == {"status": "ok"}


def test_items_returns_list():
    response = client.get("/items")
    assert response.status_code == 200
    assert isinstance(response.json()["items"], list)


def test_item_by_id_returns_one_item():
    response = client.get("/items/1")
    assert response.status_code == 200
    assert response.json()["id"] == 1


def test_unknown_item_returns_404():
    assert client.get("/items/9999").status_code == 404


def test_echo_returns_body_back():
    response = client.post("/echo", json={"value": "xin chao"})
    assert response.status_code == 200
    assert response.json()["received"] == {"value": "xin chao"}

    r = client.post("/echo", json={"name": "cam", "qty": 5})
    assert r.json()["received"] == {"name": "cam", "qty": 5}
    r = client.post("/echo", json={"value": "a", "extra": "b"})
    assert r.json()["received"] == {"value": "a", "extra": "b"}


def test_admin_exists_but_is_not_protected_by_the_app_itself():
    """Chốt chặn nằm ở gateway, không nằm ở app. Đây là điểm mấu chốt của bài tập."""
    assert client.get("/admin").status_code == 200


def test_debug_exists_but_is_not_protected_by_the_app_itself():
    assert client.get("/debug").status_code == 200
