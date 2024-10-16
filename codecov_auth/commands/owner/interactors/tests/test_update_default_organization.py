from unittest.mock import patch

import pytest
from asgiref.sync import async_to_sync
from django.test import TransactionTestCase
from shared.django_apps.core.tests.factories import OwnerFactory

from codecov.commands.exceptions import Unauthenticated, ValidationError
from codecov_auth.models import OwnerProfile

from ..update_default_organization import UpdateDefaultOrganizationInteractor


class UpdateDefaultOrganizationInteractorTest(TransactionTestCase):
    def setUp(self):
        self.default_organization_username = "sample-default-org-username"
        self.default_organization = OwnerFactory(
            username=self.default_organization_username, service="github"
        )
        self.owner = OwnerFactory(
            username="sample-owner",
            service="github",
            organizations=[self.default_organization.ownerid],
        )

        self.org_not_in_users_organizations = OwnerFactory(
            username="imposter", service="github"
        )

    @async_to_sync
    def execute(self, owner, username=None):
        return UpdateDefaultOrganizationInteractor(owner, "github").execute(
            default_org_username=username,
        )

    def test_when_unauthenticated_raise(self):
        with pytest.raises(Unauthenticated):
            self.execute(owner=None, username="random-name")

    def test_update_org_not_belonging_to_users_organizations(self):
        with pytest.raises(ValidationError):
            self.execute(owner=self.owner, username="imposter")

    def test_update_org_when_default_org_username_is_none(self):
        self.execute(owner=self.owner, username=None)

        owner_profile: OwnerProfile = OwnerProfile.objects.filter(
            owner_id=self.owner.ownerid
        ).first()
        assert owner_profile.default_org is None

    def test_update_owners_default_org(self):
        username = self.execute(
            owner=self.owner, username=self.default_organization_username
        )

        owner_profile: OwnerProfile = OwnerProfile.objects.filter(
            owner_id=self.owner.ownerid
        ).first()
        assert owner_profile.default_org == self.default_organization
        assert username == self.default_organization.username

    @patch(
        "codecov_auth.commands.owner.interactors.update_default_organization.try_auto_activate"
    )
    def test_attempts_to_auto_activate_user_for_default_org(self, try_auto_activate):
        self.execute(owner=self.owner, username=self.default_organization_username)

        try_auto_activate.assert_called_once_with(
            self.default_organization,
            self.owner,
        )

    def test_update_owners_default_org_when_current_user_is_selected(self):
        username = self.execute(owner=self.owner, username=self.owner.username)

        owner_profile: OwnerProfile = OwnerProfile.objects.filter(
            owner_id=self.owner.ownerid
        ).first()
        assert owner_profile.default_org == self.owner
        assert username == self.owner.username
