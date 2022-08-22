from unittest.mock import patch

from django.test import TestCase, override_settings
from shared.license import LicenseInformation

from codecov_auth.tests.factories import OwnerFactory
from services.self_hosted import (
    LicenseException,
    activate_owner,
    activated_owners,
    admin_owners,
    deactivate_owner,
    num_seats,
)


@override_settings(IS_ENTERPRISE=True)
class SelfHostedTestCase(TestCase):
    @patch("services.self_hosted.get_config")
    def test_admin_owners(self, get_config):
        owner1 = OwnerFactory(service="github", username="foo")
        owner2 = OwnerFactory(service="github", username="bar")
        owner3 = OwnerFactory(service="gitlab", username="foo")

        get_config.return_value = [
            {"service": "github", "username": "foo"},
            {"service": "gitlab", "username": "foo"},
        ]

        owners = admin_owners()
        assert list(owners) == [owner1, owner3]

        get_config.assert_called_once_with("setup", "admins", default=[])

    def test_activated_owners(self):
        user1 = OwnerFactory()
        user2 = OwnerFactory()
        user3 = OwnerFactory()
        user4 = OwnerFactory()
        org1 = OwnerFactory(plan_activated_users=[user1.pk])
        org2 = OwnerFactory(plan_activated_users=[user2.pk, user3.pk])

        owners = activated_owners()
        assert list(owners) == [user1, user2, user3]

    @patch("services.self_hosted.get_current_license")
    def test_num_seats(self, get_current_license):
        get_current_license.return_value = LicenseInformation(number_allowed_users=123)
        assert num_seats() == 123

    @patch("services.self_hosted.get_current_license")
    def test_num_seats_not_specified(self, get_current_license):
        get_current_license.return_value = LicenseInformation()
        assert num_seats() == 0

    @patch("services.self_hosted.num_seats")
    def test_activate_owner(self, num_seats):
        num_seats.return_value = 100

        other_owner = OwnerFactory()
        org1 = OwnerFactory(plan_activated_users=[other_owner.pk])
        org2 = OwnerFactory(plan_activated_users=[])
        org3 = OwnerFactory(plan_activated_users=[other_owner.pk])
        owner = OwnerFactory(organizations=[org1.pk, org2.pk])

        activate_owner(owner)

        org1.refresh_from_db()
        assert org1.plan_activated_users == [other_owner.pk, owner.pk]
        org2.refresh_from_db()
        assert org2.plan_activated_users == [owner.pk]
        org3.refresh_from_db()
        assert org3.plan_activated_users == [other_owner.pk]

        activate_owner(owner)

        # does not add duplicate entry
        org1.refresh_from_db()
        assert org1.plan_activated_users == [other_owner.pk, owner.pk]
        org2.refresh_from_db()
        assert org2.plan_activated_users == [owner.pk]
        org3.refresh_from_db()
        assert org3.plan_activated_users == [other_owner.pk]

    @patch("services.self_hosted.num_seats")
    def test_activate_owner_no_more_seats(self, num_seats):
        num_seats.return_value = 1

        other_owner = OwnerFactory()
        org1 = OwnerFactory(plan_activated_users=[other_owner.pk])
        org2 = OwnerFactory(plan_activated_users=[])
        owner = OwnerFactory(organizations=[org2.pk])

        with self.assertRaises(LicenseException) as e:
            activate_owner(owner)
            assert e.message == "no more seats available"

        org1.refresh_from_db()
        assert org1.plan_activated_users == [other_owner.pk]
        org2.refresh_from_db()
        assert org2.plan_activated_users == []

    def test_deactivate_owner(self):
        owner1 = OwnerFactory()
        owner2 = OwnerFactory()
        org1 = OwnerFactory(plan_activated_users=[owner1.pk, owner2.pk])
        org2 = OwnerFactory(plan_activated_users=[owner1.pk])
        org3 = OwnerFactory(plan_activated_users=[owner2.pk])

        deactivate_owner(owner1)

        org1.refresh_from_db()
        assert org1.plan_activated_users == [owner2.pk]
        org2.refresh_from_db()
        assert org2.plan_activated_users == []
        org3.refresh_from_db()
        assert org3.plan_activated_users == [owner2.pk]


@override_settings(IS_ENTERPRISE=False)
class SelfHostedNonEnterpriseTestCase(TestCase):
    def test_activate_owner(self):
        org = OwnerFactory(plan_activated_users=[])
        owner = OwnerFactory(organizations=[org.pk])

        with self.assertRaises(Exception):
            activate_owner(owner)

        org.refresh_from_db()
        assert org.plan_activated_users == []

    def test_deactivate_owner(self):
        owner1 = OwnerFactory()
        owner2 = OwnerFactory()
        org1 = OwnerFactory(plan_activated_users=[owner1.pk, owner2.pk])
        org2 = OwnerFactory(plan_activated_users=[owner1.pk])
        org3 = OwnerFactory(plan_activated_users=[owner2.pk])

        with self.assertRaises(Exception):
            deactivate_owner(owner1)

        org1.refresh_from_db()
        assert org1.plan_activated_users == [owner1.pk, owner2.pk]
        org2.refresh_from_db()
        assert org2.plan_activated_users == [owner1.pk]
        org3.refresh_from_db()
        assert org3.plan_activated_users == [owner2.pk]
