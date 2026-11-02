from django.conf import settings
from django.core.management.base import BaseCommand, CommandError
from django.db import transaction

from apps.core.seed.builder import DemoBuilder


class Command(BaseCommand):
    help = "Build the demo department described in spec Appendix B."

    def add_arguments(self, parser):
        parser.add_argument(
            "--reset",
            action="store_true",
            help="Delete ALL terms, courses, offerings, grades and demo accounts first.",
        )
        parser.add_argument(
            "--small",
            action="store_true",
            help="10 students per cohort instead of 40 (used by the tests).",
        )
        parser.add_argument(
            "--allow-production",
            action="store_true",
            help="Allow running with DEBUG=False (staging). Passwords become random.",
        )

    def handle(self, *args, reset=False, small=False, allow_production=False, **options):
        if not settings.DEBUG and not allow_production:
            raise CommandError(
                "DEBUG is False. Seeding writes demo accounts; pass --allow-production if this really is a demo environment."
            )
        builder = DemoBuilder(students_per_cohort=10 if small else 40, random_passwords=not settings.DEBUG)
        with transaction.atomic():
            if reset:
                builder.wipe()
            elif builder.already_seeded():
                raise CommandError("Demo data already exists. Use --reset to rebuild it.")
            summary = builder.build()

        self.stdout.write(self.style.SUCCESS("Demo department ready."))
        for key, value in summary.counts.items():
            self.stdout.write(f"  {key:<12} {value}")
        self.stdout.write("")
        self.stdout.write(f"  {'Role':<24} {'Name':<16} {'Email':<40} Password")
        for p in summary.personas:
            self.stdout.write(f"  {p.role:<24} {p.name:<16} {p.email:<40} {p.password}")
        if not settings.DEBUG:
            self.stdout.write(self.style.WARNING("These passwords are shown once. Store them now."))
