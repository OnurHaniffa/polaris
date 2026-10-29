from django.conf import settings
from django.contrib.auth.decorators import login_required
from django.core.cache import cache
from django.db import connection
from django.http import Http404, JsonResponse
from django.shortcuts import render


def healthz(request):
    """Used by Docker, Caddy and the CD smoke test (spec §10.3). Public, no login."""
    status = {"db": "ok", "cache": "ok"}
    try:
        connection.ensure_connection()
    except Exception:  # noqa: BLE001
        status["db"] = "down"
    try:
        cache.set("healthz", "1", 5)
    except Exception:  # noqa: BLE001
        status["cache"] = "down"
    code = 200 if all(v == "ok" for v in status.values()) else 503
    return JsonResponse(status, status=code)


@login_required
def home(request):
    """Placeholder until S2-01, which replaces it with the role-based redirect."""
    return render(request, "core/home.html")


def styleguide(request):
    """Every component on one page, so you can check the design system by eye.
    Only exists while DEBUG is on."""
    if not settings.DEBUG:
        raise Http404
    from decimal import Decimal as D

    examples = [D("86"), D("84.95"), D("59.94"), None]
    return render(request, "core/styleguide.html", {"examples": examples, "threshold": D("60")})
