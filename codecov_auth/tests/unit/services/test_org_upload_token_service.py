import uuid

import pytest
from django.forms import ValidationError
from django.test import TransactionTestCase

from codecov_auth.models import OrganizationLevelToken, TokenTypeChoices
from codecov_auth.services.org_level_token_service import OrgLevelTokenService
from codecov_auth.tests.factories import OwnerFactory


class TestOrgLevelTokenService(TransactionTestCase):
    def test_get_org_token(self):
        # Check that if you try to create a token for an org that already has one you get the same token
        owner = OwnerFactory(
            username="codecov_name", email="name@codecov.io", plan="users-enterprisey"
        )
        org_token = OrganizationLevelToken.objects.get(owner=owner)
        assert org_token == OrgLevelTokenService.get_or_create_org_token(owner)

    def test_create_org_token(self):
        user_in_enterprise_plan = OwnerFactory(plan="users-enterprisey")
        token = OrgLevelTokenService.get_or_create_org_token(user_in_enterprise_plan)
        assert isinstance(token.token, uuid.UUID)
        assert token.owner == user_in_enterprise_plan
        assert token.token_type == TokenTypeChoices.UPLOAD.value
        # Check that users not in enterprise plan can't create org tokens
        user_not_in_enterprise_plan = OwnerFactory(plan="users-basic")
        with pytest.raises(ValidationError):
            OrgLevelTokenService.get_or_create_org_token(user_not_in_enterprise_plan)

    def test_delete_token(self):
        owner = OwnerFactory(
            username="codecov_name", email="name@codecov.io", plan="users-enterprisey"
        )
        OrgLevelTokenService.delete_org_token_if_exists(owner)
        with pytest.raises(OrganizationLevelToken.DoesNotExist):
            OrganizationLevelToken.objects.get(owner=owner)
