from django.conf import settings
from django.test import TestCase, override_settings

from codecov_auth.tests.factories import OwnerFactory

from ..constants import ENTERPRISE_CLOUD_USER_PLAN_REPRESENTATIONS
from ..helpers import on_enterprise_plan


class HelpersTestCase(TestCase):
    @override_settings(IS_ENTERPRISE=True)
    def test_on_enterprise_plan_on_prem(self):
        owner = OwnerFactory()
        assert on_enterprise_plan(owner) == True

    def test_on_enterprise_plan_enterpise_cloud(self):
        for plan in ENTERPRISE_CLOUD_USER_PLAN_REPRESENTATIONS.keys():
            owner = OwnerFactory(plan=plan)
            assert on_enterprise_plan(owner) == True

    def test_on_enterprise_plan_cloud(self):
        owner = OwnerFactory()
        assert on_enterprise_plan(owner) == False
