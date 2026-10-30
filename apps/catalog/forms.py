from __future__ import annotations

from django import forms

from apps.accounts.models import ProgramMembership, User
from apps.catalog.models import Course, CourseOffering, ProgramOutcome, ProgramOutcomeSet, Term
from apps.core.forms import BootstrapFormMixin


class DateInput(forms.DateInput):
    input_type = "date"


class TermForm(BootstrapFormMixin, forms.ModelForm):
    class Meta:
        model = Term
        fields = ["code", "name", "starts_on", "ends_on"]
        widgets = {"starts_on": DateInput(), "ends_on": DateInput()}
        help_texts = {"code": "Short and sortable, e.g. 2026F, 2027S."}

    def clean(self):
        data = super().clean()
        starts, ends = data.get("starts_on"), data.get("ends_on")
        if starts and ends and ends <= starts:
            self.add_error("ends_on", "The term must end after it starts.")
        return data


class TermReopenForm(BootstrapFormMixin, forms.Form):
    reason = forms.CharField(
        min_length=10,
        widget=forms.Textarea(attrs={"rows": 2}),
        help_text=(
            "Stored in the audit trail. Example: "
            "'Grade appeal for CSE 311 Midterm I, approved by the board.'"
        ),
    )


class CourseForm(BootstrapFormMixin, forms.ModelForm):
    class Meta:
        model = Course
        fields = ["code", "title", "credits", "ects"]
        labels = {"ects": "ECTS"}

    def __init__(self, *args, program, **kwargs):
        super().__init__(*args, **kwargs)
        self.program = program

    def clean_code(self):
        code = " ".join(self.cleaned_data["code"].upper().split())
        clash = Course.objects.filter(program=self.program, code=code).exclude(pk=self.instance.pk)
        if clash.exists():
            raise forms.ValidationError(f"{code} already exists in {self.program.code}.")
        return code


def instructor_choices(program):
    return (
        User.objects.filter(
            memberships__program=program, memberships__role=ProgramMembership.Role.INSTRUCTOR
        )
        .distinct()
        .order_by("last_name", "first_name")
    )


class InstructorField(forms.ModelMultipleChoiceField):
    def label_from_instance(self, obj):
        return f"{obj.get_full_name()} <{obj.email}>"


class OfferingForm(BootstrapFormMixin, forms.Form):
    """Create form with course + term; edit form (offering=…) has section + instructors only."""

    course = forms.ModelChoiceField(queryset=Course.objects.none())
    term = forms.ModelChoiceField(queryset=Term.objects.none())
    section = forms.CharField(max_length=8, initial="1")
    instructors = InstructorField(
        queryset=User.objects.none(),
        required=False,
        widget=forms.CheckboxSelectMultiple,
        help_text="Only people with an instructor membership in this program are listed.",
    )

    def __init__(self, *args, program, offering: CourseOffering | None = None, **kwargs):
        super().__init__(*args, **kwargs)
        self.fields["instructors"].queryset = instructor_choices(program)
        if offering is None:
            self.fields["course"].queryset = program.courses.order_by("code")
            self.fields["term"].queryset = Term.objects.exclude(status=Term.Status.CLOSED)
        else:
            del self.fields["course"]
            del self.fields["term"]
            self.initial.setdefault("section", offering.section)
            self.initial.setdefault("instructors", list(offering.instructors.all()))


class EnrollmentAddForm(BootstrapFormMixin, forms.Form):
    """Add one student by student number. For a student who has no account yet,
    also fill in email, names and cohort year."""

    student_number = forms.CharField(max_length=20)
    email = forms.EmailField(required=False)
    first_name = forms.CharField(max_length=150, required=False)
    last_name = forms.CharField(max_length=150, required=False)
    cohort_year = forms.IntegerField(
        required=False,
        min_value=1990,
        max_value=2100,
        help_text="Year the student started, e.g. 2023.",
    )


class POForm(BootstrapFormMixin, forms.ModelForm):
    class Meta:
        model = ProgramOutcome
        fields = ["short_name", "description"]
        widgets = {"description": forms.Textarea(attrs={"rows": 4})}
        help_texts = {
            "description": "The official wording. Instructors map their LOs against this text."
        }


class POSetCopyForm(BootstrapFormMixin, forms.Form):
    label = forms.CharField(max_length=100, help_text="e.g. 2027 curriculum")
    effective_from_year = forms.IntegerField(
        min_value=1990,
        max_value=2100,
        help_text="First cohort (entry year) that uses this set.",
    )

    def __init__(self, *args, program, **kwargs):
        super().__init__(*args, **kwargs)
        self.program = program

    def clean_label(self):
        label = self.cleaned_data["label"].strip()
        if ProgramOutcomeSet.objects.filter(program=self.program, label=label).exists():
            raise forms.ValidationError(f"A PO set called “{label}” already exists.")
        return label
