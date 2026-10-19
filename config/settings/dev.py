from .base import *  # noqa: F403

DEBUG = True
ALLOWED_HOSTS = ["localhost", "127.0.0.1"]
# Django 6.1 configures email with MAILERS (EMAIL_BACKEND is deprecated). Dev prints emails.
MAILERS = {"default": {"BACKEND": "django.core.mail.backends.console.EmailBackend"}}
INSTALLED_APPS += ["debug_toolbar"]  # noqa: F405
MIDDLEWARE.insert(0, "debug_toolbar.middleware.DebugToolbarMiddleware")  # noqa: F405
INTERNAL_IPS = ["127.0.0.1"]
# run Celery tasks inline (no worker needed) until Sprint 5
CELERY_TASK_ALWAYS_EAGER = env.bool("CELERY_EAGER", default=True)  # noqa: F405
