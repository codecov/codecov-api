import uuid
from unittest.mock import patch

import pytest
from django.forms import ValidationError
from django.test import TransactionTestCase
from shared.django_apps.codecov_auth.tests.factories import (
    OrganizationLevelTokenFactory,
    OwnerFactory,
    PlanFactory,
    TierFactory,
)
from shared.plan.constants import DEFAULT_FREE_PLAN, PlanName, TierName

from codecov_auth.models import OrganizationLevelToken
from codecov_auth.services.org_level_token_service import OrgLevelTokenService


@patch(
    "codecov_auth.services.org_level_token_service.OrgLevelTokenService.org_can_have_upload_token"
)
def test_token_is_deleted_when_changing_user_plan(mocked_org_can_have_upload_token, db):
    # This should happen because of the signal consumer we have defined in
    # codecov_auth/services/org_upload_token_service.py > manage_org_tokens_if_owner_plan_changed
    mocked_org_can_have_upload_token.return_value = False
    enterprise_tier = TierFactory(tier_name=TierName.ENTERPRISE.value)
    enterprise_plan = PlanFactory(
        tier=enterprise_tier, name=PlanName.ENTERPRISE_CLOUD_YEARLY.value
    )
    owner = OwnerFactory(plan=enterprise_plan.name)
    org_token = OrganizationLevelTokenFactory(owner=owner)
    owner.save()
    org_token.save()
    assert OrganizationLevelToken.objects.filter(owner=owner).count() == 1
    owner.plan = "users-basic"
    owner.save()
    assert OrganizationLevelToken.objects.filter(owner=owner).count() == 0


class TestOrgWideUploadTokenService(TransactionTestCase):
    def setUp(self):
        self.enterprise_tier = TierFactory(tier_name=TierName.ENTERPRISE.value)
        self.enterprise_plan = PlanFactory(
            tier=self.enterprise_tier,
            name=PlanName.ENTERPRISE_CLOUD_YEARLY.value,
        )
        self.basic_tier = TierFactory(tier_name=TierName.BASIC.value)
        self.basic_plan = PlanFactory(
            tier=self.basic_tier,
            name=DEFAULT_FREE_PLAN,
        )
        self.owner = OwnerFactory(plan=self.enterprise_plan.name)

    def test_get_org_token(self):
        # Check that if you try to create a token for an org that already has one you get the same token
        org_token = OrganizationLevelTokenFactory(owner=self.owner)
        self.owner.save()
        org_token.save()
        assert org_token == OrgLevelTokenService.get_or_create_org_token(self.owner)

    def test_create_org_token(self):
        user_in_enterprise_plan = OwnerFactory(plan=self.enterprise_plan.name)
        token = OrgLevelTokenService.get_or_create_org_token(user_in_enterprise_plan)
        assert isinstance(token.token, uuid.UUID)
        assert token.owner == user_in_enterprise_plan
        # Check that users not in enterprise plan can create org tokens
        user_not_in_enterprise_plan = OwnerFactory(plan=self.basic_plan.name)
        token = OrgLevelTokenService.get_or_create_org_token(
            user_not_in_enterprise_plan
        )
        assert isinstance(token.token, uuid.UUID)
        assert token.owner == user_not_in_enterprise_plan

    def test_delete_token(self):
        owner = OwnerFactory(plan=self.enterprise_plan.name)
        OrgLevelTokenService.delete_org_token_if_exists(owner)
        with pytest.raises(OrganizationLevelToken.DoesNotExist):
            OrganizationLevelToken.objects.get(owner=owner)

    def test_refresh_token(self):
        owner = OwnerFactory(plan=self.enterprise_plan.name)
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
