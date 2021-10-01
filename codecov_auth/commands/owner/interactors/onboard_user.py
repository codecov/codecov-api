from asgiref.sync import sync_to_async
import html
import yaml

from codecov_auth.models import OwnerProfile
from codecov.commands.base import BaseInteractor
from codecov.commands.exceptions import Unauthenticated, Unauthorized, ValidationError


class OnboardUserInteractor(BaseInteractor):
    def validate(self):
        if not self.current_user.is_authenticated:
            raise Unauthenticated()
        # if self.current_user.onboarding_completed:
        #     raise Unauthorized()

    def create_profile(self, params):
        self.current_user.ownerprofile.delete()
        self.current_user.onboarding_completed = True
        self.current_user.business_email = params.get("business_email")
        self.current_user.email = params.get("email")
        self.current_user.save()
        profile = OwnerProfile(
            owner=self.current_user,
            type_projects=params.get("type_projects", []),
            goals=params.get("goals", []),
            other_goal=params.get("other_goal"),
        )
        profile.save()

    @sync_to_async
    def execute(self, params):
        self.validate()
        self.create_profile(params)
        return self.current_user
