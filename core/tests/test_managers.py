from datetime import datetime

from django.test import TestCase

from core.models import Repository

from .factories import RepositoryFactory, CommitFactory


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

        repo = Repository.objects.all().with_latest_commit_totals_before(datetime.now().isoformat(), None)[0]
        assert repo.latest_commit_totals == totals

    def test_get_aggregated_coverage(self):
        CommitFactory(
            totals={
                "n": 10,
                "h": 5,
                "m": 5,
                "p": 0,
                "c": 50.0,
                "C": 0.0,
            },
            repository=self.repo1
        )
        CommitFactory(
            totals={
                "n": 10,
                "h": 10,
                "m": 0,
                "p": 0,
                "c": 100.0,
                "C": 0.0,
            },
            repository=self.repo1
        )
        CommitFactory(
            totals={
                "n": 90,
                "h": 40,
                "m": 50,
                "p": 0,
                "c": 60.0,
                "C": 0.0,
            },
            repository=self.repo2
        )
        CommitFactory(
            totals={
                "n": 100,
                "h": 50,
                "m": 50,
                "p": 0,
                "c": 50.0,
                "C": 0.0,
            },
            repository=self.repo2
        )

        stats = Repository.objects.all(
        ).with_latest_commit_totals_before(
            datetime.now().isoformat(),
            None,
            include_previous_totals=True
        ).get_aggregated_coverage()

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
        assert Repository.objects.all(
        ).with_latest_commit_totals_before(
            datetime.now().isoformat(),
            None,
            True
        ).with_latest_coverage_change()[0].latest_coverage_change == -1
