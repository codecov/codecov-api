import pytest
from asgiref.sync import async_to_sync
from django.contrib.auth.models import AnonymousUser
from django.test import TransactionTestCase

from codecov.commands.exceptions import Unauthenticated, ValidationError
from codecov_auth.models import Owner, OwnerProfile
from codecov_auth.tests.factories import OwnerFactory

from ..update_default_organization import UpdateDefaultOrganizationInteractor


class UpdateDefaultOrganizationInteractorTest(TransactionTestCase):
    def setUp(self):
        self.default_organization_username = "sample-default-org-username"
        self.default_organization = OwnerFactory(
            username=self.default_organization_username, service="github"
        )
        self.user = OwnerFactory(
            username="sample-owner",
            service="github",
            organizations=[self.default_organization.ownerid],
        )

        self.org_not_in_users_organizations = OwnerFactory(
            username="imposter", service="github"
        )

    @async_to_sync
    def execute(self, user, username=None):
        current_user = user or AnonymousUser()
        return UpdateDefaultOrganizationInteractor(current_user, "github").execute(
            default_org_username=username or self.default_organization_username,
        )

    def test_when_unauthenticated_raise(self):
        with pytest.raises(Unauthenticated):
            self.execute(user=None, username="random-name")

    def test_update_org_when_default_org_is_none(self):
        with pytest.raises(ValidationError):
            self.execute(user=self.user, username="org-doesnt-exist")

    def test_update_org_not_belonging_to_users_organizations(self):
        assert not OwnerProfile.objects.filter(
            owner_id=self.org_not_in_users_organizations.ownerid
        ).exists()

        with pytest.raises(ValidationError):
            self.execute(user=self.user, username="imposter")

    def test_update_owners_default_org(self):
        assert not OwnerProfile.objects.filter(owner_id=self.user.ownerid).exists()

        self.execute(user=self.user)

        owner_profile: OwnerProfile = OwnerProfile.objects.filter(
            owner_id=self.user.ownerid
        ).first()
        assert owner_profile.default_org == self.default_organization

    def test_update_owners_default_org_when_current_user_is_selected(self):
        assert not OwnerProfile.objects.filter(owner_id=self.user.ownerid).exists()

        self.execute(user=self.user, username=self.user.username)

        owner_profile: OwnerProfile = OwnerProfile.objects.filter(
            owner_id=self.user.ownerid
        ).first()
        assert owner_profile.default_org == self.user
