from django import forms
from django.core.exceptions import ValidationError

_CHECK_WIDGETS = (forms.CheckboxInput, forms.CheckboxSelectMultiple, forms.RadioSelect)


class BootstrapFormMixin:
    """Adds Bootstrap 5 classes to every widget.
    Put it first: class F(BootstrapFormMixin, forms.Form)."""

    def __init__(self, *args, **kwargs):
        super().__init__(*args, **kwargs)
        for field in self.fields.values():
            widget = field.widget
            if isinstance(widget, forms.HiddenInput):
                continue
            if isinstance(widget, _CHECK_WIDGETS):
                css = "form-check-input"
            elif isinstance(widget, forms.Select | forms.SelectMultiple):
                css = "form-select"
            else:
                css = "form-control"
            widget.attrs["class"] = f"{widget.attrs.get('class', '')} {css}".strip()

    def full_clean(self):
        super().full_clean()
        for name in self.errors:
            if name in self.fields:
                widget = self.fields[name].widget
                widget.attrs["class"] = f"{widget.attrs.get('class', '')} is-invalid".strip()
                widget.attrs["aria-invalid"] = "true"


def add_service_errors(form, exc: ValidationError) -> None:
    """Show a service's ValidationError on the form, next to the field when the form has it."""
    if hasattr(exc, "error_dict"):
        for name, messages in exc.message_dict.items():
            target = name if name in form.fields else None
            for message in messages:
                form.add_error(target, message)
    else:
        for message in exc.messages:
            form.add_error(None, message)
