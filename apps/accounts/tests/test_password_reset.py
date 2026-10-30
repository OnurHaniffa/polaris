import re

import pytest
from django.core import mail
from django.urls import reverse

from apps.core.tests.factories import UserFactory

pytestmark = pytest.mark.django_db
LINK = re.compile(r"https?://[^/\s]+(/password-reset/[^/\s]+/[^/\s]+/)")


@pytest.fixture
def user():
    u = UserFactory(email="elif@live.acibadem.edu.tr", first_name="Elif")
    u.set_password("old-password-1")
    u.save()
    return u


def _request_link(client, email) -> str:
    response = client.post(reverse("accounts:password_reset"), {"email": email})
    assert response["Location"] == reverse("accounts:password_reset_done")
    assert len(mail.outbox) == 1
    return LINK.search(mail.outbox[0].body).group(1)


def test_reset_email_link_works_once(client, user):
    """B1 AC 3."""
    link = _request_link(client, user.email)
    assert mail.outbox[0].subject == "Reset your POlaris password"

    set_password_url = client.get(link)["Location"]  # token moves into the session
    response = client.post(
        set_password_url, {"new_password1": "a-new-Pass-2026", "new_password2": "a-new-Pass-2026"}
    )
    assert response["Location"] == reverse("accounts:password_reset_complete")
    user.refresh_from_db()
    assert user.check_password("a-new-Pass-2026")

    second = client.get(link, follow=True)  # same link again
    assert second.context["validlink"] is False
    assert "doesn't work any more" in second.text


def test_unknown_email_looks_the_same_and_sends_nothing(client):
    """No account enumeration: same redirect, no email."""
    response = client.post(reverse("accounts:password_reset"), {"email": "nobody@acibadem.edu.tr"})
    assert response["Location"] == reverse("accounts:password_reset_done")
    assert mail.outbox == []


def test_user_without_usable_password_gets_no_email(client):
    """Imported students (S3-05) get the set-password email instead."""
    u = UserFactory(email="new@live.acibadem.edu.tr")
    u.set_unusable_password()
    u.save()
    client.post(reverse("accounts:password_reset"), {"email": u.email})
    assert mail.outbox == []


def test_weak_password_rejected(client, user):
    set_password_url = client.get(_request_link(client, user.email))["Location"]
    response = client.post(set_password_url, {"new_password1": "123", "new_password2": "123"})
    assert response.status_code == 200
    user.refresh_from_db()
    assert user.check_password("old-password-1")


def test_login_page_links_to_reset(client):
    assert reverse("accounts:password_reset") in client.get(reverse("accounts:login")).text
