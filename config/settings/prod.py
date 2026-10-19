from .base import *  # noqa: F403

DEBUG = False
CSRF_TRUSTED_ORIGINS = env.list("CSRF_TRUSTED_ORIGINS")  # noqa: F405
SECURE_PROXY_SSL_HEADER = ("HTTP_X_FORWARDED_PROTO", "https")  # Caddy terminates HTTPS
SECURE_SSL_REDIRECT = True
SECURE_REDIRECT_EXEMPT = [r"^healthz$"]
SESSION_COOKIE_SECURE = True
CSRF_COOKIE_SECURE = True
SECURE_HSTS_SECONDS = 3600  # raise to 1 year once everything works
SECURE_HSTS_INCLUDE_SUBDOMAINS = True
SILENCED_SYSTEM_CHECKS = ["security.W021"]  # HSTS preload: not for a student project domain
# EMAIL_URL like smtp+tls://user:password@smtp.provider.com:587 → Django 6.1 MAILERS
_email = env.email_url("EMAIL_URL")  # noqa: F405
_options = {}
if _email["EMAIL_BACKEND"].endswith("smtp.EmailBackend"):
    _options = {
        "host": _email["EMAIL_HOST"],
        "port": _email["EMAIL_PORT"],
        "username": _email["EMAIL_HOST_USER"],
        "password": _email["EMAIL_HOST_PASSWORD"],
        "use_tls": _email.get("EMAIL_USE_TLS", False),
        "use_ssl": _email.get("EMAIL_USE_SSL", False),
    }
MAILERS = {"default": {"BACKEND": _email["EMAIL_BACKEND"], "OPTIONS": _options}}
DEFAULT_FROM_EMAIL = env("DEFAULT_FROM_EMAIL", default="POlaris <noreply@example.com>")  # noqa: F405
LOGGING = {
    "version": 1,
    "handlers": {"console": {"class": "logging.StreamHandler"}},
    "root": {"handlers": ["console"], "level": "INFO"},
}
