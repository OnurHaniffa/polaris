import pytest

pytestmark = pytest.mark.django_db

PASSWORD = "a-long-test-password"


@pytest.fixture
def user(django_user_model):
    return django_user_model.objects.create_user(
        "elif@live.acibadem.edu.tr", PASSWORD, first_name="Elif", last_name="Yıldız"
    )


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


def test_home_requires_login(client):
    response = client.get("/")
    assert response.status_code == 302
    assert response["Location"] == "/login/?next=/"


def test_login_with_email_then_home(client, user):
    assert client.get("/login/").status_code == 200
    response = client.post("/login/", {"username": user.email, "password": PASSWORD})
    assert response.status_code == 302
    assert response["Location"] == "/"
    home = client.get("/")
    assert b"Welcome to POlaris" in home.content
    assert b"X-CSRFToken" in home.content  # HTMX gets the CSRF token from <body>


def test_wrong_password_is_rejected(client, user):
    response = client.post("/login/", {"username": user.email, "password": "nope"})
    assert response.status_code == 200
    assert not response.wsgi_request.user.is_authenticated
