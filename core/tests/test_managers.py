from django.test import TestCase
from .factories import RepositoryFactory, CommitFactory
from core.models import Repository


class RepositoryQuerySetTests(TestCase):

    def setUp(self):
        self.repo = RepositoryFactory()

    def test_with_total_commit_count(self):
        CommitFactory(repository=self.repo)
        CommitFactory(repository=self.repo)

        assert Repository.objects.all().with_total_commit_count()[0].total_commit_count == 2

    def test_with_latest_coverage_change(self):
        CommitFactory(totals={"c": 99}, repository=self.repo)
        CommitFactory(totals={"c": 98}, repository=self.repo)
        assert Repository.objects.all().with_latest_coverage_change()[0].latest_coverage_change == -1
