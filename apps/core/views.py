from django.core.cache import cache
from django.db import connection
from django.http import JsonResponse


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
