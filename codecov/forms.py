from dal import autocomplete
from django import forms
from shared.django_apps.rollouts.models import FeatureFlagVariant

from codecov_auth.models import Owner
from core.models import Repository


class AutocompleteSearchForm(forms.ModelForm):
    repository = forms.ModelChoiceField(
        queryset=Repository.objects.all(),
        widget=autocomplete.ModelSelect2(url="admin-repository-autocomplete"),
        required=False,
        label="Add repo override",
        help_text="Search for a repo and hit `Save and continue editing` to add it",
    )

    owner = forms.ModelChoiceField(
        queryset=Owner.objects.all(),
        widget=autocomplete.ModelSelect2(url="admin-owner-autocomplete"),
        required=False,
        label="Add owner override",
        help_text="Search for an owner and hit `Save and continue editing` to add it",
    )

    class Meta:
        model = FeatureFlagVariant
        fields = "__all__"

    def save(self, commit=True):
        instance = super(AutocompleteSearchForm, self).save(commit=False)

        if self.cleaned_data["repository"]:
            if instance.override_repo_ids is None:
                instance.override_repo_ids = []
            instance.override_repo_ids.append(self.cleaned_data["repository"].repoid)

        if self.cleaned_data["owner"]:
            if instance.override_owner_ids is None:
                instance.override_repo_ids = []
            instance.override_owner_ids.append(self.cleaned_data["owner"].ownerid)

        if commit:
            instance.save()

        return instance
