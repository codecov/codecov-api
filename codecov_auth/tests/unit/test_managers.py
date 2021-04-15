from django.test import TestCase
from codecov_auth.models import Owner, Session
from core.models import Repository, Pull
from ddf import G


class OwnerManagerTests(TestCase):
    def setUp(self):
        self.owner = G(Owner)

    def test_annotate_with_latest_pr_date_in(self):
        org = G(Owner)
        self.owner.organizations = [org.ownerid]
        self.owner.save()

        with self.subTest("with multiple pulls"):
            repo = G(Repository, author=org, private=True)
            pull1 = G(Pull, repository=repo, author=self.owner)
            pull2 = G(Pull, repository=repo, author=self.owner)

            owner = (
                Owner.objects.filter(ownerid=self.owner.ownerid)
                .annotate_with_latest_private_pr_date_in(org)
                .get()
            )

            assert owner.latest_private_pr_date == pull2.updatestamp

        with self.subTest("with pulls in separate orgs"):
            repository_in_org = G(Repository, author=org, private=True)
            repository_not_in_org = G(Repository, private=True)
            most_recent_pull_in_org = G(
                Pull, repository=repository_in_org, author=self.owner
            )
            more_recent_pull_not_in_org = G(
                Pull, repository=repository_not_in_org, author=self.owner
            )

            owner = (
                Owner.objects.filter(ownerid=self.owner.ownerid)
                .annotate_with_latest_private_pr_date_in(org)
                .get()
            )

            assert owner.latest_private_pr_date == most_recent_pull_in_org.updatestamp

    def test_annotate_with_lastseen(self):
        session = G(Session, owner=self.owner)
        G(Session)
        G(Session)

        owner = Owner.objects.annotate_with_lastseen().get(ownerid=self.owner.ownerid)

        assert owner.lastseen == session.lastseen
