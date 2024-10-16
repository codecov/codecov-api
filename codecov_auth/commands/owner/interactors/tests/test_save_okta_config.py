import pytest
from asgiref.sync import async_to_sync
from django.contrib.auth.models import AnonymousUser
from django.test import TransactionTestCase
from shared.django_apps.codecov_auth.tests.factories import (
    AccountFactory,
    OktaSettingsFactory,
    OwnerFactory,
)

from codecov.commands.exceptions import Unauthenticated, Unauthorized, ValidationError
from codecov_auth.models import OktaSettings

from ..save_okta_config import SaveOktaConfigInteractor


class SaveOktaConfigInteractorTest(TransactionTestCase):
    def setUp(self):
        self.current_user = OwnerFactory(username="codecov-user")
        self.service = "github"
        user1 = OwnerFactory()
        user2 = OwnerFactory()
        self.owner = OwnerFactory(
            username=self.current_user.username,
            service=self.service,
            account=AccountFactory(),
        )

        self.owner_with_admins = OwnerFactory(
            username=self.current_user.username,
            service=self.service,
            admins=[self.current_user.ownerid],
            plan_activated_users=[user1.ownerid, user2.ownerid],
            account=None,
        )

        self.interactor = SaveOktaConfigInteractor(
            current_owner=self.owner,
            service=self.service,
            current_user=self.current_user,
        )

    @async_to_sync
    def execute(
        self,
        interactor: SaveOktaConfigInteractor | None = None,
        input: dict | None = None,
    ):
        if not interactor and self.interactor:
            interactor = self.interactor

        if not interactor:
            return
        return interactor.execute(input)

    def test_user_is_not_authenticated(self):
        with pytest.raises(Unauthenticated):
            self.execute(
                interactor=SaveOktaConfigInteractor(
                    current_owner=None,
                    service=self.service,
                    current_user=AnonymousUser(),
                ),
                input={
                    "client_id": "some-client-id",
                    "client_secret": "some-client-secret",
                    "url": "https://okta.example.com",
                    "enabled": True,
                    "enforced": True,
                    "org_username": self.owner.username,
                },
            )

    def test_validation_error_when_owner_not_found(self):
        with pytest.raises(ValidationError):
            self.execute(
                input={
                    "client_id": "some-client-id",
                    "client_secret": "some-client-secret",
                    "url": "https://okta.example.com",
                    "enabled": True,
                    "enforced": True,
                    "org_username": "non-existent-user",
                },
            )

    def test_unauthorized_error_when_user_is_not_admin(self):
        with pytest.raises(Unauthorized):
            self.execute(
                input={
                    "client_id": "some-client-id",
                    "client_secret": "some-client-secret",
                    "url": "https://okta.example.com",
                    "enabled": True,
                    "enforced": True,
                    "org_username": self.owner.username,
                },
            )

    def test_create_okta_settings_when_account_does_not_exist(self):
        plan_activated_users = []
        for _ in range(100):
            user_owner = OwnerFactory(user=None)
            plan_activated_users.append(user_owner.ownerid)

        org_with_lots_of_users = OwnerFactory(
            service=self.service,
            admins=[self.current_user.ownerid],
            plan_activated_users=plan_activated_users,
        )

        input_data = {
            "client_id": "some-client-id",
            "client_secret": "some-client-secret",
            "url": "https://okta.example.com",
            "enabled": True,
            "enforced": True,
            "org_username": org_with_lots_of_users.username,
        }

        interactor = SaveOktaConfigInteractor(
            current_owner=self.current_user, service=self.service
        )
        self.execute(interactor=interactor, input=input_data)

        org_with_lots_of_users.refresh_from_db()
        account = org_with_lots_of_users.account

        assert account.name == org_with_lots_of_users.username
        assert account.plan == org_with_lots_of_users.plan
        assert account.plan_seat_count == org_with_lots_of_users.plan_user_count
        assert account.free_seat_count == org_with_lots_of_users.free

        assert account.users.count() == 100
        assert account.users.count() == len(org_with_lots_of_users.plan_activated_users)

        okta_config = OktaSettings.objects.get(account=org_with_lots_of_users.account)

        assert okta_config.client_id == input_data["client_id"]
        assert okta_config.client_secret == input_data["client_secret"]
        assert okta_config.url == input_data["url"]
        assert okta_config.enabled == input_data["enabled"]
        assert okta_config.enforced == input_data["enforced"]

    def test_update_okta_settings_when_account_exists(self):
        input_data = {
            "client_id": "some-client-id",
            "client_secret": "some-client-secret",
            "url": "https://okta.example.com",
            "enabled": True,
            "enforced": True,
            "org_username": self.owner_with_admins.username,
        }

        account = AccountFactory()
        self.owner_with_admins.account = account
        self.owner_with_admins.save()

        interactor = SaveOktaConfigInteractor(
            current_owner=self.current_user, service=self.service
        )
        self.execute(interactor=interactor, input=input_data)

        okta_config = OktaSettings.objects.get(account=self.owner_with_admins.account)

        assert okta_config.client_id == input_data["client_id"]
        assert okta_config.client_secret == input_data["client_secret"]
        assert okta_config.url == input_data["url"]
        assert okta_config.enabled == input_data["enabled"]
        assert okta_config.enforced == input_data["enforced"]

    def test_update_okta_settings_url_remove_trailing_slashes(self):
        input_data = {
            "client_id": "some-client-id",
            "client_secret": "some-client-secret",
            "url": "https://okta.example.com/",
            "enabled": True,
            "enforced": True,
            "org_username": self.owner_with_admins.username,
        }

        account = AccountFactory()
        self.owner_with_admins.account = account
        self.owner_with_admins.save()

        interactor = SaveOktaConfigInteractor(
            current_owner=self.current_user, service=self.service
        )
        self.execute(interactor=interactor, input=input_data)

        okta_config = OktaSettings.objects.get(account=self.owner_with_admins.account)

        assert okta_config.url == "https://okta.example.com"

    def test_update_okta_settings_when_okta_settings_exists(self):
        input_data = {
            "client_id": "some-client-id",
            "client_secret": "some-client-secret",
            "url": "https://okta.example.com",
            "enabled": True,
            "enforced": True,
            "org_username": self.owner_with_admins.username,
        }

        account = AccountFactory()
        OktaSettingsFactory(account=account)
        self.owner_with_admins.account = account
        self.owner_with_admins.save()

        interactor = SaveOktaConfigInteractor(
            current_owner=self.current_user, service=self.service
        )
        self.execute(interactor=interactor, input=input_data)

        okta_config = OktaSettings.objects.get(account=self.owner_with_admins.account)

        assert okta_config.client_id == input_data["client_id"]
        assert okta_config.client_secret == input_data["client_secret"]
        assert okta_config.url == input_data["url"]
        assert okta_config.enabled == input_data["enabled"]
        assert okta_config.enforced == input_data["enforced"]

    def test_update_okta_settings_when_some_fields_are_none(self):
        input_data = {
            "client_id": "some-client-id",
            "client_secret": None,
            "url": None,
            "enabled": True,
            "enforced": True,
            "org_username": self.owner_with_admins.username,
        }

        account = AccountFactory()
        OktaSettingsFactory(account=account)
        self.owner_with_admins.account = account
        self.owner_with_admins.save()

        interactor = SaveOktaConfigInteractor(
            current_owner=self.current_user, service=self.service
        )
        self.execute(interactor=interactor, input=input_data)

        okta_config = OktaSettings.objects.get(account=self.owner_with_admins.account)

        assert okta_config.client_id == input_data["client_id"]
        assert okta_config.client_secret is not None
        assert okta_config.url is not None
        assert okta_config.enabled == input_data["enabled"]
        assert okta_config.enforced == input_data["enforced"]
