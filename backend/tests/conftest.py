import pytest


@pytest.fixture(autouse=True)
def db_path(tmp_path, monkeypatch):
    """Point every test at its own throwaway SQLite file, never the real dev DB."""
    path = tmp_path / "test.db"
    monkeypatch.setenv("DB_PATH", str(path))
    return path
