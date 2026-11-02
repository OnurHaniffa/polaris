from django import forms

from apps.catalog.models import Term


class DepartmentFilterForm(forms.Form):
    term = forms.ModelChoiceField(
        queryset=Term.objects.exclude(status=Term.Status.PLANNED).order_by("-starts_on"),
        required=False,
        empty_label=None,
        label="Up to term",
    )
    include_open = forms.BooleanField(required=False, label="Include open terms")
