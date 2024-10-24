import pytest
from asgiref.sync import async_to_sync
from django.contrib.auth.models import AnonymousUser
from django.test import TransactionTestCase, override_settings
from shared.django_apps.core.tests.factories import OwnerFactory

from codecov.commands.exceptions import Unauthenticated, ValidationError
from codecov_auth.commands.owner.interactors.update_self_hosted_settings import (
    UpdateSelfHostedSettingsInteractor,
)


class UpdateSelfHostedSettingsInteractorTest(TransactionTestCase):
    @async_to_sync
    def execute(
        self,
        current_user,
        input={
            "should_auto_activate": None,
        },
    ):
        return UpdateSelfHostedSettingsInteractor(None, "github", current_user).execute(
            input=input,
        )

    @override_settings(IS_ENTERPRISE=True)
    def test_update_self_hosted_settings_when_auto_activate_is_true(self):
        owner = OwnerFactory(plan_auto_activate=False)
        self.execute(current_user=owner, input={"should_auto_activate": True})
        owner.refresh_from_db()
        assert owner.plan_auto_activate == True

    @override_settings(IS_ENTERPRISE=True)
    def test_update_self_hosted_settings_when_auto_activate_is_false(self):
        owner = OwnerFactory(plan_auto_activate=True)
        self.execute(current_user=owner, input={"should_auto_activate": False})
        owner.refresh_from_db()
        assert owner.plan_auto_activate == False

    @override_settings(IS_ENTERPRISE=False)
    def test_validation_error_when_not_self_hosted_instance(self):
        owner = OwnerFactory(plan_auto_activate=True)
        with pytest.raises(ValidationError):
            self.execute(
                current_user=owner,
                input={
                    "should_auto_activate": False,
                },
            )

    @override_settings(IS_ENTERPRISE=True)
    def test_user_is_not_authenticated(self):
        with pytest.raises(Unauthenticated):
            self.execute(
                current_user=AnonymousUser(),
                input={
                    "should_auto_activate": False,
                },
            )
