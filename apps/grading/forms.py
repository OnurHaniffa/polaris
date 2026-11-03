from django import forms


class PublishForm(forms.Form):
    expected_changes = forms.IntegerField(min_value=0, widget=forms.HiddenInput)


class UnpublishForm(forms.Form):
    reason = forms.CharField(
        min_length=5,
        max_length=500,
        widget=forms.Textarea(attrs={"rows": 3}),
        help_text="Students will no longer see these grades. This reason is kept in the history.",
    )
