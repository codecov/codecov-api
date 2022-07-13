import factory

from core.tests.factories import CommitFactory
from reports.tests.factories import RepositoryFlagFactory

from ..models import CommitComparison, FlagComparison


class CommitComparisonFactory(factory.django.DjangoModelFactory):
    class Meta:
        model = CommitComparison

    base_commit = factory.SubFactory(CommitFactory)
    compare_commit = factory.SubFactory(CommitFactory)

class FlagComparisonFactory(factory.django.DjangoModelFactory):
    class Meta:
        model = FlagComparison

    commit_comparison = factory.SubFactory(CommitComparisonFactory)
    repositoryflag = factory.SubFactory(RepositoryFlagFactory)
    coverage_totals = {"diff": 0, "hits": 12, "files": 1, "lines": 14, "misses": 1, "methods": 5, "branches": 3, "coverage": "85.71429", "messages": 0, "partials": 1, "sessions": 1, "complexity": 0, "complexity_total": 0}
    patch_totals = {"diff": 0, "hits": 2, "files": 2, "lines": 7, "misses": 4, "methods": 2, "branches": 2, "coverage": "28.57143", "messages": 0, "partials": 1, "sessions": 0, "complexity": 0, "complexity_total": 0}