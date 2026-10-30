import pytest
from django.urls import reverse

from apps.accounts.forms import GENERIC_LOGIN_ERROR
from apps.core.tests.factories import MembershipFactory, ProgramFactory, UserFactory

pytestmark = pytest.mark.django_db


def _user(email, password):
    user = UserFactory(email=email)
    user.set_password(password)
    user.save()
    return user


def test_login_with_email(client):
    user = _user("can.aydin@acibadem.edu.tr", "correct horse")
    MembershipFactory(user=user, program=ProgramFactory(), role="instructor")
    response = client.post(
        reverse("accounts:login"),
        {"username": "can.aydin@acibadem.edu.tr", "password": "correct horse"},
    )
    assert response.status_code == 302
    assert response["Location"] == reverse("home")


@pytest.mark.parametrize(
    ("email", "password"),
    [
        ("can.aydin@acibadem.edu.tr", "wrong"),  # right email, wrong password
        ("nobody@acibadem.edu.tr", "correct horse"),  # unknown email
    ],
)
def test_wrong_credentials_give_one_generic_message(client, email, password):
    """B1 AC 2: the message doesn't reveal whether the email exists."""
    _user("can.aydin@acibadem.edu.tr", "correct horse")
    response = client.post(reverse("accounts:login"), {"username": email, "password": password})
    assert response.status_code == 200
    assert GENERIC_LOGIN_ERROR in response.text


def test_inactive_account_gets_the_same_message(client):
    user = _user("gone@acibadem.edu.tr", "correct horse")
    user.is_active = False
    user.save()
    response = client.post(
        reverse("accounts:login"), {"username": user.email, "password": "correct horse"}
    )
    assert GENERIC_LOGIN_ERROR in response.text


def test_logged_out_user_is_sent_to_login_then_back(client):
    """B1 AC 5."""
    target = reverse("catalog:teaching")
    response = client.get(target)
    assert response.status_code == 302
    assert response["Location"] == f"{reverse('accounts:login')}?next={target}"

    user = _user("x@acibadem.edu.tr", "pw-123456")
    MembershipFactory(user=user, program=ProgramFactory(), role="instructor")
    response = client.post(
        f"{reverse('accounts:login')}?next={target}",
        {"username": "x@acibadem.edu.tr", "password": "pw-123456", "next": target},
    )
    assert response["Location"] == target


def test_next_to_another_site_is_ignored(client):
    _user("x@acibadem.edu.tr", "pw-123456")
    response = client.post(
        reverse("accounts:login"),
        {"username": "x@acibadem.edu.tr", "password": "pw-123456", "next": "https://evil.example/"},
    )
    assert response["Location"] == reverse("home")


def test_logout_is_post_only(client):
    client.force_login(UserFactory())
    assert client.get(reverse("accounts:logout")).status_code == 405
    assert client.post(reverse("accounts:logout"))["Location"] == reverse("accounts:login")
