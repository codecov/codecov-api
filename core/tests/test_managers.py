from datetime import datetime

from django.contrib.auth.models import AnonymousUser
from django.test import TestCase
from django.utils import timezone

from codecov_auth.tests.factories import OwnerFactory
from core.models import Repository

from .factories import CommitFactory, RepositoryFactory


class RepositoryQuerySetTests(TestCase):
    def setUp(self):
        self.repo1 = RepositoryFactory()
        self.repo2 = RepositoryFactory()

    def test_with_latest_commit_totals_before(self):
        totals = {
            "n": 10,
            "h": 5,
            "m": 3,
            "p": 2,
            "c": 100.0,
            "C": 80.0,
        }
        CommitFactory(totals=totals, repository=self.repo1)

        repo = Repository.objects.filter(
            repoid=self.repo1.repoid
        ).with_latest_commit_totals_before(datetime.now().isoformat(), None)[0]
        assert repo.latest_commit_totals == totals

    def test_get_aggregated_coverage(self):
        CommitFactory(
            totals={"n": 10, "h": 5, "m": 5, "p": 0, "c": 50.0, "C": 0.0,},
            repository=self.repo1,
        )
        CommitFactory(
            totals={"n": 10, "h": 10, "m": 0, "p": 0, "c": 100.0, "C": 0.0,},
            repository=self.repo1,
        )
        CommitFactory(
            totals={"n": 90, "h": 40, "m": 50, "p": 0, "c": 60.0, "C": 0.0,},
            repository=self.repo2,
        )
        CommitFactory(
            totals={"n": 100, "h": 50, "m": 50, "p": 0, "c": 50.0, "C": 0.0,},
            repository=self.repo2,
        )

        stats = (
            Repository.objects.all()
            .with_latest_commit_totals_before(
                timezone.now().isoformat(), None, include_previous_totals=True
            )
            .get_aggregated_coverage()
        )

        assert stats["repo_count"] == 2
        assert stats["sum_lines"] == 110
        assert stats["sum_partials"] == 0
        # We would expect the weighted coverage to be (54 / 110) * 100
        assert stats["weighted_coverage"] == 54.5454545454545
        # We would expect the weighted coverage to be (54 / 110) * 100 - (45 / 100) * 100
        assert stats["weighted_coverage_change"] == 9.54545454545454

    def test_with_latest_coverage_change(self):
        CommitFactory(totals={"c": 99}, repository=self.repo1)
        CommitFactory(totals={"c": 98}, repository=self.repo1)
        assert (
            Repository.objects.filter(repoid=self.repo1.repoid)
            .with_latest_commit_totals_before(timezone.now().isoformat(), None, True)
            .with_latest_coverage_change()[0]
            .latest_coverage_change
            == -1
        )

    def test_get_or_create_from_github_repo_data(self):
        owner = OwnerFactory()

        with self.subTest("doesnt crash when fork but no parent"):
            repo_data = {
                "id": 45,
                "default_branch": "master",
                "private": True,
                "name": "test",
                "fork": True,
            }

            repo, created = Repository.objects.get_or_create_from_git_repo(
                repo_data, owner
            )
            assert created
            assert repo.service_id == 45
            assert repo.branch == "master"
            assert repo.private
            assert repo.name == "test"

    def test_viewable_repos(self):
        private_repo = RepositoryFactory(private=True)
        public_repo = RepositoryFactory(private=False)

        with self.subTest("when owner permission is none doesnt crash"):
            owner = OwnerFactory(permission=None)
            owned_repo = RepositoryFactory(author=owner)

            repos = Repository.objects.viewable_repos(owner)
            assert repos.count() == 2

            repoids = repos.values_list("repoid", flat=True)
            assert public_repo.repoid in repoids
            assert owned_repo.repoid in repoids

        with self.subTest("when repository do not have a name doesnt return it"):
            owner = OwnerFactory(permission=None)
            RepositoryFactory(author=owner, name=None)
            RepositoryFactory(author=owner, name=None)
            RepositoryFactory(author=owner, name=None)

            repos = Repository.objects.viewable_repos(owner)
            assert repos.count() == 1
            # only public repo created above
            repoids = repos.values_list("repoid", flat=True)
            assert public_repo.repoid in repoids

        with self.subTest("when owner permission is not none, returns repos"):
            owner = OwnerFactory(permission=[private_repo.repoid])
            owned_repo = RepositoryFactory(author=owner)

            repos = Repository.objects.viewable_repos(owner)
            assert repos.count() == 3

            repoids = repos.values_list("repoid", flat=True)
            assert public_repo.repoid in repoids
            assert owned_repo.repoid in repoids
            assert private_repo.repoid in repoids

        with self.subTest("when user not authed, returns only public"):
            user = AnonymousUser()

            repos = Repository.objects.viewable_repos(user)
            assert repos.count() == 1

            repoids = repos.values_list("repoid", flat=True)
            assert public_repo.repoid in repoids
