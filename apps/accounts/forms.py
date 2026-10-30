from django import forms
from django.contrib.auth.forms import AuthenticationForm

GENERIC_LOGIN_ERROR = "Email or password is incorrect."


class EmailAuthenticationForm(AuthenticationForm):
    """Same message for a wrong password, an unknown email and an inactive account (B1 AC 2)."""

    error_messages = {"invalid_login": GENERIC_LOGIN_ERROR, "inactive": GENERIC_LOGIN_ERROR}

    def __init__(self, request=None, *args, **kwargs):
        super().__init__(request, *args, **kwargs)
        self.fields["username"].label = "University email"
        self.fields["username"].widget = forms.EmailInput(
            attrs={"autocomplete": "email", "autofocus": True, "class": "form-control"}
        )
        self.fields["password"].widget.attrs.update({"class": "form-control"})
