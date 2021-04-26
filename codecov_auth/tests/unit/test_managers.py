from django.test import TestCase

from codecov_auth.models import Owner
from codecov_auth.tests.factories import OwnerFactory, SessionFactory
from core.tests.factories import RepositoryFactory, PullFactory


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
                [
                    self.owner.ownerid,
                    owner_in_org_and_plan_activated_users.ownerid,
                ],
            )

        with self.subTest("no users"):
            self.owner.delete()
            owner_in_org_and_plan_activated_users.delete()
            users_of = Owner.objects.users_of(owner=org)
            self.assertEqual(list(users_of), [])

    def test_annotate_with_latest_pr_date_in(self):
        org = OwnerFactory()
        self.owner.organizations = [org.ownerid]
        self.owner.save()

        with self.subTest("with multiple pulls"):
            repo = RepositoryFactory(author=org, private=True)
            pull1 = PullFactory(repository=repo, author=self.owner)
            pull2 = PullFactory(repository=repo, author=self.owner)

            owner = (
                Owner.objects.filter(ownerid=self.owner.ownerid)
                .annotate_with_latest_private_pr_date_in(org)
                .get()
            )

            assert owner.latest_private_pr_date == pull2.updatestamp

        with self.subTest("with pulls in separate orgs"):
            repository_in_org = RepositoryFactory(author=org, private=True)
            repository_not_in_org = RepositoryFactory(private=True)
            most_recent_pull_in_org = PullFactory(
                repository=repository_in_org, author=self.owner
            )
            more_recent_pull_not_in_org = PullFactory(
                repository=repository_not_in_org, author=self.owner
            )

            owner = (
                Owner.objects.filter(ownerid=self.owner.ownerid)
                .annotate_with_latest_private_pr_date_in(org)
                .get()
            )

            assert owner.latest_private_pr_date == most_recent_pull_in_org.updatestamp

    def test_annotate_with_lastseen(self):
        session = SessionFactory(owner=self.owner)
        SessionFactory()
        SessionFactory()

        owner = Owner.objects.annotate_with_lastseen().get(ownerid=self.owner.ownerid)

        assert owner.lastseen == session.lastseen
