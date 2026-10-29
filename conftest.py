"""Fixtures every test file can use without importing them."""

import pytest

from apps.accounts.models import ProgramMembership
from apps.core.tests.factories import MembershipFactory, ProgramFactory, UserFactory
from apps.core.tests.scenarios import elif_scenario


@pytest.fixture
def client_as(client, db):
    """client_as("instructor") → a test client logged in as a fresh user with that role.

    Accepts "student", "instructor", "head" or "admin". The user is available as
    client.user so the test can attach offerings to them."""

    def login(role, program=None):
        if role == "admin":
            user = UserFactory(is_staff=True, is_superuser=True)
        else:
            user = UserFactory()
            MembershipFactory(
                user=user,
                program=program or ProgramFactory(),
                role=ProgramMembership.Role(role),
            )
        client.force_login(user)
        client.user = user
        return client

    return login


@pytest.fixture
def elif_data(db):
    return elif_scenario()
