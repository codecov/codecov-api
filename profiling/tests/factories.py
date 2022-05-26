import factory
from factory.django import DjangoModelFactory

from core.tests.factories import RepositoryFactory
from profiling import models


class ProfilingCommitFactory(DjangoModelFactory):
    class Meta:
        model = models.ProfilingCommit

    repository = factory.SubFactory(RepositoryFactory)
    environment = "development"
    version_identifier = "0.1.0"
    code = factory.LazyAttribute(lambda o: f"{o.version_identifier}:{o.environment}")
