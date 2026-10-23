"""Tests for FastAPI application."""

from fastapi.testclient import TestClient
from web.backend.main import app

client = TestClient(app)


def test_health_endpoint():
    """Test health check endpoint returns 200."""
    response = client.get("/health")
    assert response.status_code == 200
    assert response.json() == {"status": "healthy"}


def test_cors_headers():
    """Test CORS headers are present."""
    response = client.options(
        "/health",
        headers={
            "Origin": "http://localhost:5173",
            "Access-Control-Request-Method": "GET",
        },
    )
    assert response.status_code == 200
    assert "access-control-allow-origin" in response.headers
    assert response.headers["access-control-allow-origin"] == "http://localhost:5173"


def _make_dist(tmp_path):
    tmp_path.mkdir(exist_ok=True)
    (tmp_path / "index.html").write_text("<html></html>")
    (tmp_path / "manifest.webmanifest").write_text("{}")
    return tmp_path


def test_resolve_spa_file_serves_root_files(tmp_path):
    from web.backend.main import resolve_spa_file

    dist = _make_dist(tmp_path)
    assert resolve_spa_file(dist, "manifest.webmanifest").name == "manifest.webmanifest"


def test_resolve_spa_file_falls_back_to_index(tmp_path):
    from web.backend.main import resolve_spa_file

    dist = _make_dist(tmp_path)
    assert resolve_spa_file(dist, "").name == "index.html"
    assert resolve_spa_file(dist, "playlists/42").name == "index.html"


def test_resolve_spa_file_blocks_traversal(tmp_path):
    from web.backend.main import resolve_spa_file

    dist = _make_dist(tmp_path / "dist")
    (tmp_path / "secret.txt").write_text("nope")
    assert resolve_spa_file(dist, "../secret.txt").name == "index.html"


def test_webmanifest_mime_type_registered():
    import mimetypes

    import web.backend.main  # noqa: F401

    assert mimetypes.guess_type("x.webmanifest")[0] == "application/manifest+json"
