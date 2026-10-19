import pytest
from django.db import IntegrityError, transaction

from apps.accounts.models import User

pytestmark = pytest.mark.django_db


def test_login_field_is_email():
    assert User.USERNAME_FIELD == "email"
    assert not hasattr(User, "username") or User.username is None


def test_create_user_normalises_email_and_hashes_password():
    user = User.objects.create_user("Elif@LIVE.acibadem.edu.tr", "s3cret-pass", first_name="Elif")
    assert user.email == "Elif@live.acibadem.edu.tr"  # domain part lower-cased
    assert user.check_password("s3cret-pass")
    assert not user.is_staff and not user.is_superuser
    assert str(user) == "Elif <Elif@live.acibadem.edu.tr>"


def test_email_is_required():
    with pytest.raises(ValueError, match="Email is required"):
        User.objects.create_user("", "pw")


def test_create_superuser():
    admin = User.objects.create_superuser("admin@example.com", "pw")
    assert admin.is_staff and admin.is_superuser


def test_email_unique():
    User.objects.create_user("a@example.com", "pw")
    with pytest.raises(IntegrityError), transaction.atomic():
        User.objects.create_user("a@example.com", "pw")


def test_student_number_unique_but_optional():
    User.objects.create_user("x@example.com", "pw")
    User.objects.create_user("y@example.com", "pw")  # two NULL student numbers are fine
    User.objects.create_user("s1@example.com", "pw", student_number="2023-0001")
    with pytest.raises(IntegrityError), transaction.atomic():
        User.objects.create_user("s2@example.com", "pw", student_number="2023-0001")
