import pytest

pytestmark = pytest.mark.django_db


def test_healthz(client):
    response = client.get("/healthz")
    assert response.status_code == 200
    assert response.json() == {"db": "ok", "cache": "ok"}


def test_healthz_reports_a_dead_cache(client, monkeypatch):
    def broken(*args, **kwargs):
        raise ConnectionError("redis is down")

    monkeypatch.setattr("apps.core.views.cache.set", broken)
    response = client.get("/healthz")
    assert response.status_code == 503
    assert response.json()["cache"] == "down"
