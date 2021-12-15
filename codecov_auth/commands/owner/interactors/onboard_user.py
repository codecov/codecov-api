import html

import yaml
from asgiref.sync import sync_to_async
from django import forms

from codecov.commands.base import BaseInteractor
from codecov.commands.exceptions import Unauthenticated, Unauthorized, ValidationError
from codecov_auth.models import OwnerProfile


class OnboardForm(forms.Form):
    email = forms.EmailField(required=False)
    business_email = forms.EmailField(required=False)
    other_goal = forms.CharField(required=False)
    type_projects = forms.MultipleChoiceField(choices=OwnerProfile.ProjectType.choices)
    goals = forms.MultipleChoiceField(choices=OwnerProfile.Goal.choices)


class OnboardUserInteractor(BaseInteractor):
    def validate(self, params):
        if not self.current_user.is_authenticated:
            raise Unauthenticated()
        if self.current_user.onboarding_completed:
            raise Unauthorized()
        form = OnboardForm(params)
        if not form.is_valid():
            raise ValidationError(form.errors.as_json())

    def create_profile(self, params):
        self.current_user.onboarding_completed = True
        self.current_user.business_email = params.get("business_email")
        self.current_user.email = params.get("email")
        self.current_user.save()

        OwnerProfile.objects.update_or_create(
            owner=self.current_user,
            defaults={
                "type_projects": params.get("type_projects", []),
                "goals": params.get("goals", []),
                "other_goal": params.get("other_goal"),
            },
        )

    @sync_to_async
    def execute(self, params):
        self.validate(params)
        self.create_profile(params)
        return self.current_user
