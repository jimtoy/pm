import importlib

from fastapi.testclient import TestClient


def test_hello_returns_expected_message():
    from app.main import app

    client = TestClient(app)
    response = client.get("/api/hello")
    assert response.status_code == 200
    assert response.json() == {"message": "Hello from FastAPI"}


def test_root_serves_static_index(tmp_path, monkeypatch):
    fixture_dir = tmp_path / "static"
    fixture_dir.mkdir()
    (fixture_dir / "index.html").write_text("<html><body>fixture page</body></html>")

    monkeypatch.setenv("STATIC_DIR", str(fixture_dir))
    import app.main as main_module

    importlib.reload(main_module)

    client = TestClient(main_module.app)
    response = client.get("/")
    assert response.status_code == 200
    assert "fixture page" in response.text

    monkeypatch.delenv("STATIC_DIR", raising=False)
    importlib.reload(main_module)
