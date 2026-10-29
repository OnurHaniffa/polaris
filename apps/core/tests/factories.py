"""One factory per model (spec §4.8). Use them in every test instead of objects.create():
a factory fills every required field with something valid, so a test only states the
fields it actually cares about.

    student = UserFactory()
    offering = OfferingFactory(course__code="CSE 311")
    grade = GradeFactory(score=Decimal("90"))      # also creates assessment, enrollment, ...
"""

import datetime
from decimal import Decimal

import factory
from django.utils import timezone

from apps.accounts.models import ProgramMembership, User
from apps.catalog.models import (
    Course,
    CourseOffering,
    Enrollment,
    Program,
    ProgramOutcome,
    ProgramOutcomeSet,
    Term,
)
from apps.grading.models import Grade
from apps.outcomes.models import Assessment, AssessmentLOWeight, LearningOutcome, LOPOWeight

PASSWORD = "polaris-test-pass"  # every factory user can log in with this


class UserFactory(factory.django.DjangoModelFactory):
    class Meta:
        model = User
        skip_postgeneration_save = True

    email = factory.Sequence(lambda n: f"user{n}@live.acibadem.edu.tr")
    first_name = factory.Faker("first_name", locale="tr_TR")
    last_name = factory.Faker("last_name", locale="tr_TR")
    password = factory.PostGenerationMethodCall("set_password", PASSWORD)

    @factory.post_generation
    def _save_password(obj, create, extracted, **kwargs):
        if create:
            obj.save(update_fields=["password"])


class ProgramFactory(factory.django.DjangoModelFactory):
    """The data migration (S1-05) creates the real program "CSE" in every test database.
    Factories make test programs TST0, TST1, ... so tests never depend on, or collide with,
    the seeded one."""

    class Meta:
        model = Program
        django_get_or_create = ("code",)

    code = factory.Sequence(lambda n: f"TST{n}")
    name = factory.LazyAttribute(lambda o: f"Program {o.code}")
    attainment_threshold = Decimal("60")


class ProgramOutcomeSetFactory(factory.django.DjangoModelFactory):
    class Meta:
        model = ProgramOutcomeSet

    program = factory.SubFactory(ProgramFactory)
    label = factory.Sequence(lambda n: f"Curriculum {n}")
    effective_from_year = 2020
    is_active = True


class ProgramOutcomeFactory(factory.django.DjangoModelFactory):
    class Meta:
        model = ProgramOutcome

    po_set = factory.SubFactory(ProgramOutcomeSetFactory)
    number = factory.Sequence(lambda n: n % 30 + 1)
    short_name = factory.LazyAttribute(lambda o: f"Outcome {o.number}")
    description = factory.Faker("sentence")


class TermFactory(factory.django.DjangoModelFactory):
    """get_or_create on code: every OfferingFactory() in a test shares one "2026F" term.
    To get a different term, pass a different code: TermFactory(code="2025F", status="closed").
    OfferingFactory(term__status="closed") works on its own, but if a 2026F term already
    exists in that test, the existing one is reused with its existing status."""

    class Meta:
        model = Term
        django_get_or_create = ("code",)

    code = "2026F"
    name = "Fall 2026"
    starts_on = datetime.date(2026, 9, 28)
    ends_on = datetime.date(2027, 1, 22)
    status = Term.Status.OPEN


class CourseFactory(factory.django.DjangoModelFactory):
    class Meta:
        model = Course

    program = factory.SubFactory(ProgramFactory)
    code = factory.Sequence(lambda n: f"CSE {100 + n}")
    title = factory.Faker("catch_phrase")
    credits = Decimal("3.0")
    ects = Decimal("6.0")


class OfferingFactory(factory.django.DjangoModelFactory):
    class Meta:
        model = CourseOffering
        skip_postgeneration_save = True

    course = factory.SubFactory(CourseFactory)
    term = factory.SubFactory(TermFactory)
    section = "1"

    @factory.post_generation
    def instructors(obj, create, extracted, **kwargs):
        """OfferingFactory(instructors=[teacher]) adds them to the M2M."""
        if create and extracted:
            obj.instructors.add(*extracted)


class EnrollmentFactory(factory.django.DjangoModelFactory):
    class Meta:
        model = Enrollment

    offering = factory.SubFactory(OfferingFactory)
    student = factory.SubFactory(UserFactory)
    status = Enrollment.Status.ENROLLED


class MembershipFactory(factory.django.DjangoModelFactory):
    class Meta:
        model = ProgramMembership

    user = factory.SubFactory(UserFactory)
    program = factory.SubFactory(ProgramFactory)
    role = ProgramMembership.Role.STUDENT
    cohort_year = factory.Maybe(
        factory.LazyAttribute(lambda o: o.role == ProgramMembership.Role.STUDENT),
        yes_declaration=2023,
        no_declaration=None,
    )


class LearningOutcomeFactory(factory.django.DjangoModelFactory):
    class Meta:
        model = LearningOutcome

    offering = factory.SubFactory(OfferingFactory)
    number = factory.Sequence(lambda n: n + 1)
    description = factory.Faker("sentence")


class AssessmentFactory(factory.django.DjangoModelFactory):
    class Meta:
        model = Assessment

    offering = factory.SubFactory(OfferingFactory)
    name = factory.Sequence(lambda n: f"Assessment {n}")
    kind = Assessment.Kind.MIDTERM
    max_score = Decimal("100")
    published_at = None

    class Params:
        published = factory.Trait(published_at=factory.LazyFunction(timezone.now))


class AssessmentLOWeightFactory(factory.django.DjangoModelFactory):
    class Meta:
        model = AssessmentLOWeight

    assessment = factory.SubFactory(AssessmentFactory)
    learning_outcome = factory.SubFactory(
        LearningOutcomeFactory, offering=factory.SelfAttribute("..assessment.offering")
    )
    weight = Decimal("100")


class LOPOWeightFactory(factory.django.DjangoModelFactory):
    class Meta:
        model = LOPOWeight

    learning_outcome = factory.SubFactory(LearningOutcomeFactory)
    program_outcome = factory.SubFactory(ProgramOutcomeFactory)
    weight = 3


class GradeFactory(factory.django.DjangoModelFactory):
    """GradeFactory(score=90) is a draft. GradeFactory(score=90, published=True) is what a
    student sees: published_score copied and the assessment marked published."""

    class Meta:
        model = Grade
        skip_postgeneration_save = True

    assessment = factory.SubFactory(AssessmentFactory)
    enrollment = factory.SubFactory(
        EnrollmentFactory, offering=factory.SelfAttribute("..assessment.offering")
    )
    score = Decimal("75")
    is_excused = False

    class Params:
        published = factory.Trait(
            published_score=factory.SelfAttribute("score"),
            published_is_excused=factory.SelfAttribute("is_excused"),
            published_at=factory.LazyFunction(timezone.now),
        )

    @factory.post_generation
    def _publish_assessment(obj, create, extracted, **kwargs):
        if create and obj.published_at and obj.assessment.published_at is None:
            obj.assessment.published_at = obj.published_at
            obj.assessment.save(update_fields=["published_at"])
