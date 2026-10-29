"""Smoke test: every admin page opens. Catches typos in list_display, search_fields etc.,
which Django only notices when the page is rendered."""

import pytest
from django.contrib import admin
from django.urls import reverse

from apps.core.tests.scenarios import elif_scenario

pytestmark = pytest.mark.django_db

MODELS = [m for m in admin.site._registry if m._meta.app_label not in {"auth"}]


@pytest.mark.parametrize("model", MODELS, ids=lambda m: m._meta.label)
def test_admin_changelist_and_change_pages_open(admin_client, model):
    elif_scenario()
    opts = model._meta
    url = reverse(f"admin:{opts.app_label}_{opts.model_name}_changelist")
    assert admin_client.get(url, {"q": "x"}).status_code == 200
    obj = model.objects.first()
    if obj is not None:
        url = reverse(f"admin:{opts.app_label}_{opts.model_name}_change", args=[obj.pk])
        assert admin_client.get(url).status_code == 200


def test_admin_can_add_a_user(admin_client):
    url = reverse("admin:accounts_user_add")
    assert admin_client.get(url).status_code == 200
    response = admin_client.post(
        url,
        {
            "email": "new@live.acibadem.edu.tr",
            "first_name": "Yeni",
            "last_name": "Kişi",
            "usable_password": "true",
            "password1": "a-long-Password-123",
            "password2": "a-long-Password-123",
            # the membership inline's "management form" (0 rows filled in)
            "memberships-TOTAL_FORMS": "0",
            "memberships-INITIAL_FORMS": "0",
        },
    )
    assert response.status_code == 302
