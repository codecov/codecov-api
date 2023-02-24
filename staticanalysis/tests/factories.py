from uuid import uuid4

import factory
from factory.django import DjangoModelFactory

from core.tests.factories import CommitFactory, RepositoryFactory
from staticanalysis.models import (
    StaticAnalysisSingleFileSnapshot,
    StaticAnalysisSuite,
    StaticAnalysisSuiteFilepath,
)


class StaticAnalysisSuiteFactory(DjangoModelFactory):
    class Meta:
        model = StaticAnalysisSuite

    commit = factory.SubFactory(CommitFactory)


class StaticAnalysisSingleFileSnapshotFactory(DjangoModelFactory):
    class Meta:
        model = StaticAnalysisSingleFileSnapshot

    repository = factory.SubFactory(RepositoryFactory)
    file_hash = factory.LazyFunction(lambda: uuid4().hex)
    content_location = "a/b/c.txt"


class StaticAnalysisSuiteFilepathFactory(DjangoModelFactory):
    class Meta:
        model = StaticAnalysisSuiteFilepath

    file_snapshot = factory.SubFactory(StaticAnalysisSingleFileSnapshotFactory)
    analysis_suite = factory.SubFactory(StaticAnalysisSuiteFactory)
