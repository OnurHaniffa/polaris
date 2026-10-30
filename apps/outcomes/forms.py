from __future__ import annotations

from decimal import Decimal

from django import forms

from apps.core.forms import BootstrapFormMixin

from .models import Assessment


class LearningOutcomeForm(BootstrapFormMixin, forms.Form):
    description = forms.CharField(
        max_length=2000,
        widget=forms.Textarea(attrs={"rows": 3}),
        help_text="What a student should be able to do after the course. "
        "Copy the wording from your syllabus if you have one.",
    )

    def clean_description(self):
        text = " ".join(self.cleaned_data["description"].split())  # collapse pasted line breaks
        if len(text) < 5:
            raise forms.ValidationError("Write at least a few words.")
        return text


class AssessmentForm(BootstrapFormMixin, forms.Form):
    name = forms.CharField(max_length=100, help_text="As students know it, e.g. “Midterm I”.")
    kind = forms.ChoiceField(choices=Assessment.Kind.choices)
    max_score = forms.DecimalField(
        max_digits=7,
        decimal_places=2,
        min_value=Decimal("0.01"),
        initial=Decimal("100"),
        help_text="The highest possible raw mark. Grades are converted to 0–100 using it.",
    )
    course_weight = forms.DecimalField(
        max_digits=5,
        decimal_places=2,
        min_value=Decimal("0"),
        max_value=Decimal("100"),
        required=False,
        label="Course weight (%)",
        help_text="Share of the course grade, e.g. 25. Leave blank if you don't know.",
    )
    due_date = forms.DateField(required=False, widget=forms.DateInput(attrs={"type": "date"}))
    confirm_max_change = forms.BooleanField(
        required=False,
        label="Yes, change the maximum and re-check every grade",
    )

    #: Fields passed to the service. confirm_max_change is a flag, not a model field.
    MODEL_FIELDS = ("name", "kind", "max_score", "course_weight", "due_date")

    def clean_name(self):
        return " ".join(self.cleaned_data["name"].split())

    def model_data(self) -> dict:
        return {name: self.cleaned_data[name] for name in self.MODEL_FIELDS}

    @classmethod
    def initial_for(cls, assessment: Assessment) -> dict:
        return {name: getattr(assessment, name) for name in cls.MODEL_FIELDS}
