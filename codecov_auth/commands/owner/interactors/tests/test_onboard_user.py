import pytest
from django.contrib.auth.models import AnonymousUser
from django.test import TransactionTestCase

from codecov.commands.exceptions import Unauthenticated, Unauthorized, ValidationError
from codecov_auth.commands.owner.interactors.onboard_user import OnboardUserInteractor
from codecov_auth.models import OwnerProfile
from codecov_auth.tests.factories import OwnerFactory


class OnboardUserInteractorTest(TransactionTestCase):
    def setUp(self):
        self.user = OwnerFactory(username="codecov-user")
        self.already_onboarded_user = OwnerFactory(
            username="codecov-user", onboarding_completed=True
        )
        self.good_params = {
            "email": "dev@dev.com",
            "business_email": "dev@codecov.io",
            "type_projects": [OwnerProfile.ProjectType.PERSONAL],
            "goals": [OwnerProfile.Goal.STARTING_WITH_TESTS, OwnerProfile.Goal.OTHER],
            "other_goal": "feel confident in my code",
        }

    async def test_when_unauthenticated_raise(self):
        with pytest.raises(Unauthenticated):
            await OnboardUserInteractor(AnonymousUser(), "github").execute(
                self.good_params
            )

    async def test_when_user_already_completed_onboarding(self):
        with pytest.raises(Unauthorized):
            await OnboardUserInteractor(self.already_onboarded_user, "github").execute(
                self.good_params
            )

    async def test_when_params_arent_good(self):
        with pytest.raises(ValidationError):
            await OnboardUserInteractor(self.user, "github").execute(
                {**self.good_params, "email": "notgood"}
            )

    async def test_when_everything_is_good(self):
        user = await OnboardUserInteractor(self.user, "github").execute(
            self.good_params
        )
        assert user.email == self.good_params["email"]
        assert user.business_email == self.good_params["business_email"]
        assert user.profile.type_projects == self.good_params["type_projects"]
        assert user.profile.goals == self.good_params["goals"]
        assert user.profile.other_goal == self.good_params["other_goal"]
