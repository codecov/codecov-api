from unittest.mock import patch

from django.test import TestCase, override_settings
from rest_framework.reverse import reverse
from shared.django_apps.core.tests.factories import OwnerFactory

from codecov_auth.models import Owner
from services.self_hosted import activate_owner, is_activated_owner
from utils.test_utils import APIClient


@override_settings(IS_ENTERPRISE=True, ROOT_URLCONF="api.internal.enterprise_urls")
class UserViewsetUnauthenticatedTestCase(TestCase):
    def test_list_users(self):
        res = self.client.get(reverse("selfhosted-users-list"))
        # not authenticated
        assert res.status_code == 401


@override_settings(IS_ENTERPRISE=True, ROOT_URLCONF="api.internal.enterprise_urls")
class UserViewsetTestCase(TestCase):
    def setUp(self):
        self.owner = OwnerFactory()
        self.current_owner = OwnerFactory(organizations=[self.owner.ownerid])
        self.client = APIClient()
        self.client.force_login_owner(self.current_owner)


class UserViewsetAuthenticatedTestCase(UserViewsetTestCase):
    def test_list_users(self):
        res = self.client.get(reverse("selfhosted-users-list"))
        # not an admin
        assert res.status_code == 403

    def test_detail(self):
        other_owner = OwnerFactory()

        res = self.client.get(
            reverse("selfhosted-users-detail", kwargs={"pk": other_owner.pk})
        )
        assert res.status_code == 403

    def test_detail_self(self):
        res = self.client.get(
            reverse("selfhosted-users-detail", kwargs={"pk": self.current_owner.pk})
        )
        assert res.status_code == 403

    def test_current(self):
        res = self.client.get(reverse("selfhosted-users-current"))
        assert res.status_code == 200
        assert res.json() == {
            "ownerid": self.current_owner.pk,
            "username": self.current_owner.username,
            "email": self.current_owner.email,
            "name": self.current_owner.name,
            "is_admin": False,
            "activated": False,
        }

    @patch("services.self_hosted.license_seats")
    def test_current_update(self, license_seats):
        license_seats.return_value = 5

        org = OwnerFactory()
        self.current_owner.organizations = [org.pk]
        self.current_owner.save()

        res = self.client.patch(
            reverse("selfhosted-users-current"), data={"activated": True}, format="json"
        )
        assert res.status_code == 200
        assert res.json() == {
            "ownerid": self.current_owner.pk,
            "username": self.current_owner.username,
            "email": self.current_owner.email,
            "name": self.current_owner.name,
            "is_admin": False,
            "activated": True,
        }
        assert is_activated_owner(self.current_owner) == True


class UserViewsetAdminTestCase(UserViewsetTestCase):
    @patch("services.self_hosted.admin_owners")
    def test_list_users(self, admin_owners):
        admin_owners.return_value = Owner.objects.filter(pk__in=[self.current_owner.pk])

        OwnerFactory()
        OwnerFactory(oauth_token=None, organizations=[self.owner.ownerid])
        activated_owner = OwnerFactory(
            oauth_token=None,
            organizations=None,
        )
        self.owner.plan_activated_users = [activated_owner.pk]
        self.owner.save()

        res = self.client.get(reverse("selfhosted-users-list"))
        assert res.status_code == 200
        assert res.json() == {
            "count": 2,
            "next": None,
            "previous": None,
            "results": [
                {
                    "ownerid": self.current_owner.pk,
                    "username": self.current_owner.username,
                    "email": self.current_owner.email,
                    "name": self.current_owner.name,
                    "is_admin": True,
                    "activated": False,
                },
                {
                    "ownerid": activated_owner.pk,
                    "username": activated_owner.username,
                    "email": activated_owner.email,
                    "name": activated_owner.name,
                    "is_admin": False,
                    "activated": True,
                },
            ],
            "total_pages": 1,
        }

    @patch("services.self_hosted.admin_owners")
    def test_list_users_filter_admin(self, admin_owners):
        admin_owners.return_value = Owner.objects.filter(pk__in=[self.current_owner.pk])

        OwnerFactory()

        res = self.client.get(reverse("selfhosted-users-list"), {"is_admin": True})
        assert res.status_code == 200
        assert res.json() == {
            "count": 1,
            "next": None,
            "previous": None,
            "results": [
                {
                    "ownerid": self.current_owner.pk,
                    "username": self.current_owner.username,
                    "email": self.current_owner.email,
                    "name": self.current_owner.name,
                    "is_admin": True,
                    "activated": False,
                },
            ],
            "total_pages": 1,
        }

    @patch("services.self_hosted.activated_owners")
    @patch("services.self_hosted.admin_owners")
    def test_list_users_filter_activated(self, admin_owners, activated_owners):
        admin_owners.return_value = Owner.objects.filter(pk__in=[self.current_owner.pk])

        other_owner = OwnerFactory(organizations=[self.owner.ownerid])
        activated_owners.return_value = Owner.objects.filter(pk__in=[other_owner.pk])

        res = self.client.get(reverse("selfhosted-users-list"), {"activated": True})
        assert res.status_code == 200
        assert res.json() == {
            "count": 1,
            "next": None,
            "previous": None,
            "results": [
                {
                    "ownerid": other_owner.pk,
                    "username": other_owner.username,
                    "email": other_owner.email,
                    "name": other_owner.name,
                    "is_admin": False,
                    "activated": True,
                },
            ],
            "total_pages": 1,
        }

    @patch("services.self_hosted.admin_owners")
    def test_list_users_search(self, admin_owners):
        admin_owners.return_value = Owner.objects.filter(pk__in=[self.current_owner.pk])

        other_owner = OwnerFactory(
            username="foobar", organizations=[self.owner.ownerid]
        )

        res = self.client.get(reverse("selfhosted-users-list"), {"search": "foo"})
        assert res.status_code == 200
        assert res.json() == {
            "count": 1,
            "next": None,
            "previous": None,
            "results": [
                {
                    "ownerid": other_owner.pk,
                    "username": other_owner.username,
                    "email": other_owner.email,
                    "name": other_owner.name,
                    "is_admin": False,
                    "activated": False,
                },
            ],
            "total_pages": 1,
        }

    @patch("services.self_hosted.admin_owners")
    def test_detail(self, admin_owners):
        admin_owners.return_value = Owner.objects.filter(pk__in=[self.current_owner.pk])

        other_owner = OwnerFactory(organizations=[self.owner.ownerid])

        res = self.client.get(
            reverse("selfhosted-users-detail", kwargs={"pk": other_owner.pk})
        )
        assert res.status_code == 200
        assert res.json() == {
            "ownerid": other_owner.pk,
            "username": other_owner.username,
            "email": other_owner.email,
            "name": other_owner.name,
            "is_admin": False,
            "activated": False,
        }

    @patch("services.self_hosted.license_seats")
    @patch("services.self_hosted.admin_owners")
    def test_update_activate(self, admin_owners, license_seats):
        admin_owners.return_value = Owner.objects.filter(pk__in=[self.current_owner.pk])
        license_seats.return_value = 5

        org = OwnerFactory()
        other_owner = OwnerFactory(organizations=[org.pk])

        res = self.client.patch(
            reverse("selfhosted-users-detail", kwargs={"pk": other_owner.pk}),
            data={"activated": True},
            format="json",
        )
        assert res.status_code == 200
        assert res.json() == {
            "ownerid": other_owner.pk,
            "username": other_owner.username,
            "email": other_owner.email,
            "name": other_owner.name,
            "is_admin": False,
            "activated": True,
        }
        assert is_activated_owner(other_owner) == True

    @patch("services.self_hosted.license_seats")
    @patch("services.self_hosted.admin_owners")
    def test_update_activate_no_more_seats(self, admin_owners, license_seats):
        admin_owners.return_value = Owner.objects.filter(pk__in=[self.current_owner.pk])
        license_seats.return_value = 0

        org = OwnerFactory()
        other_owner = OwnerFactory(organizations=[org.pk])

        res = self.client.patch(
            reverse("selfhosted-users-detail", kwargs={"pk": other_owner.pk}),
            data={"activated": True},
            format="json",
        )
        assert res.status_code == 403
        assert res.json() == {
            "detail": "No seats remaining. Please contact Codecov support or deactivate users."
        }
        assert is_activated_owner(other_owner) == False

    @patch("services.self_hosted.license_seats")
    @patch("services.self_hosted.admin_owners")
    def test_update_deactivate(self, admin_owners, license_seats):
        admin_owners.return_value = Owner.objects.filter(pk__in=[self.current_owner.pk])
        license_seats.return_value = 5

        org = OwnerFactory()
        other_owner = OwnerFactory(organizations=[org.pk])

        activate_owner(other_owner)

        res = self.client.patch(
            reverse("selfhosted-users-detail", kwargs={"pk": other_owner.pk}),
            data={"activated": False},
            format="json",
        )
        assert res.status_code == 200
        assert res.json() == {
            "ownerid": other_owner.pk,
            "username": other_owner.username,
            "email": other_owner.email,
            "name": other_owner.name,
            "is_admin": False,
            "activated": False,
        }
        assert is_activated_owner(other_owner) == False
