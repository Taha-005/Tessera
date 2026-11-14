import pytest


@pytest.fixture
def env(monkeypatch, tmp_path):
    """Run in an empty folder, so no real .env is read, with every required setting set."""
    monkeypatch.chdir(tmp_path)
    monkeypatch.setenv("DATABASE_URL", f"sqlite:///{(tmp_path / 'test.db').as_posix()}")
    monkeypatch.setenv("DATA_DIR", str(tmp_path))
    monkeypatch.setenv("JWT_SECRET_KEY", "test-only-not-a-real-secret")
    return monkeypatch
