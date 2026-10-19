from django import forms

from .models import Brief


class BriefReviewForm(forms.ModelForm):
    """The parts of a brief an editor may change: the AI explanation only.
    Facts (stage, status, what's next) come from code and are not in this form."""

    # Stored as a list in the database; edited as one group per line.
    who_is_affected = forms.CharField(
        widget=forms.Textarea(attrs={"rows": 4}),
        help_text="One group per line, 2 to 4 groups.",
    )

    class Meta:
        model = Brief
        fields = ["summary", "why_it_matters", "who_is_affected", "policy_area"]
        widgets = {
            "summary": forms.Textarea(attrs={"rows": 3}),
            "why_it_matters": forms.Textarea(attrs={"rows": 3}),
        }
        labels = {
            "summary": "What it does",
            "why_it_matters": "Why it matters",
            "who_is_affected": "Who's affected",
        }

    def __init__(self, *args, **kwargs):
        super().__init__(*args, **kwargs)
        if self.instance.pk and not self.is_bound:
            self.initial["who_is_affected"] = "\n".join(self.instance.who_is_affected or [])

    def clean_who_is_affected(self):
        lines = self.cleaned_data["who_is_affected"].splitlines()
        groups = [line.strip() for line in lines if line.strip()]
        if not groups:
            raise forms.ValidationError("Add at least one group.")
        return groups