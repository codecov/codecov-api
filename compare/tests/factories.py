import factory

from core.tests.factories import CommitFactory

from ..models import CommitComparison


class CommitComparisonFactory(factory.django.DjangoModelFactory):
    class Meta:
        model = CommitComparison

    base_commit = factory.SubFactory(CommitFactory)
    compare_commit = factory.SubFactory(CommitFactory)
