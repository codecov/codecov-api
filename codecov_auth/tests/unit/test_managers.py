from django.test import TestCase

from codecov_auth.models import Owner
from codecov_auth.tests.factories import OwnerFactory, SessionFactory
from core.tests.factories import PullFactory, RepositoryFactory


class OwnerManagerTests(TestCase):
    def setUp(self):
        self.owner = OwnerFactory()

    def test_users_of(self):
        org = OwnerFactory()
        self.owner.organizations = [org.ownerid]
        self.owner.save()

        owner_in_org_and_plan_activated_users = OwnerFactory(
            organizations=[org.ownerid]
        )
        owner_only_in_plan_activated_users = OwnerFactory()

        org.plan_activated_users = [
            owner_in_org_and_plan_activated_users.ownerid,
            owner_only_in_plan_activated_users.ownerid,
        ]
        org.save()

        with self.subTest("returns all users"):
            users_of = Owner.objects.users_of(owner=org)
            self.assertCountEqual(
                [user.ownerid for user in users_of],
                [
                    self.owner.ownerid,
                    owner_only_in_plan_activated_users.ownerid,
                    owner_in_org_and_plan_activated_users.ownerid,
                ],
            )

        with self.subTest("no plan_activated_users"):
            org.plan_activated_users = []
            org.save()
            users_of = Owner.objects.users_of(owner=org)
            self.assertCountEqual(
                [user.ownerid for user in users_of],
                [self.owner.ownerid, owner_in_org_and_plan_activated_users.ownerid,],
            )

        with self.subTest("no users"):
            self.owner.delete()
            owner_in_org_and_plan_activated_users.delete()
            users_of = Owner.objects.users_of(owner=org)
            self.assertEqual(list(users_of), [])
