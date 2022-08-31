import uuid

import pytest
from django.forms import ValidationError
from django.test import TransactionTestCase

from codecov_auth.models import OrganizationLevelToken
from codecov_auth.services.org_level_token_service import OrgLevelTokenService
from codecov_auth.tests.factories import OrganizationLevelTokenFactory, OwnerFactory


def test_token_is_deleted_when_changing_user_plan(db):
    # This should happen because of the signal consumer we have defined in
    # codecov_auth/services/org_upload_token_service.py > manage_org_tokens_if_owner_plan_changed
    owner = OwnerFactory(plan="users-enterprisey")
    org_token = OrganizationLevelTokenFactory(owner=owner)
    owner.save()
    org_token.save()
    assert OrganizationLevelToken.objects.filter(owner=owner).count() == 1
    owner.plan = "users-basic"
    owner.save()
    assert OrganizationLevelToken.objects.filter(owner=owner).count() == 0


class TestOrgWideUploadTokenService(TransactionTestCase):
    def test_get_org_token(self):
        # Check that if you try to create a token for an org that already has one you get the same token
        owner = OwnerFactory(plan="users-enterprisey")
        org_token = OrganizationLevelTokenFactory(owner=owner)
        owner.save()
        org_token.save()
        assert org_token == OrgLevelTokenService.get_or_create_org_token(owner)

    def test_create_org_token(self):
        user_in_enterprise_plan = OwnerFactory(plan="users-enterprisey")
        token = OrgLevelTokenService.get_or_create_org_token(user_in_enterprise_plan)
        assert isinstance(token.token, uuid.UUID)
        assert token.owner == user_in_enterprise_plan
        # Check that users not in enterprise plan can't create org tokens
        user_not_in_enterprise_plan = OwnerFactory(plan="users-basic")
        with pytest.raises(ValidationError):
            OrgLevelTokenService.get_or_create_org_token(user_not_in_enterprise_plan)

    def test_delete_token(self):
        owner = OwnerFactory(plan="users-enterprisey")
        OrgLevelTokenService.delete_org_token_if_exists(owner)
        with pytest.raises(OrganizationLevelToken.DoesNotExist):
            OrganizationLevelToken.objects.get(owner=owner)

    def test_refresh_token(self):
        owner = OwnerFactory(plan="users-enterprisey")
        org_token = OrganizationLevelTokenFactory(owner=owner)
        owner.save()
        org_token.save()
        previous_token_obj = OrganizationLevelToken.objects.get(owner=owner)
        previous_token = previous_token_obj.token
        OrgLevelTokenService.refresh_token(previous_token_obj.id)
        refreshed_token_obj = OrganizationLevelToken.objects.get(owner=owner)
        assert previous_token_obj.id == refreshed_token_obj.id
        assert previous_token != refreshed_token_obj.token

    def test_refresh_token_error(self):
        with pytest.raises(ValidationError):
            # Token that doesn't exist
            OrgLevelTokenService.refresh_token(1000)
