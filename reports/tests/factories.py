import random
import uuid

import factory

from reports import models
from hashlib import sha1
from factory.django import DjangoModelFactory
from codecov_auth.tests.factories import OwnerFactory
from core.tests.factories import CommitFactory, RepositoryFactory


class CommitReportFactory(DjangoModelFactory):
    class Meta:
        model = models.CommitReport

    commit = factory.SubFactory(CommitFactory)


class UploadFactory(DjangoModelFactory):
    class Meta:
        model = models.ReportSession

    build_code = factory.Sequence(lambda n: f"{n}")
    report = factory.SubFactory(CommitReportFactory)


class RepositoryFlagFactory(DjangoModelFactory):
    class Meta:
        model = models.RepositoryFlag

    repository = factory.SubFactory(RepositoryFactory)
    flag_name = factory.Faker("word")


class UploadFlagMembershipFactory(DjangoModelFactory):
    class Meta:
        model = models.UploadFlagMembership

    flag = factory.SubFactory(RepositoryFlagFactory)
    report_session = factory.SubFactory(UploadFactory)


class ReportLevelTotalsFactory(DjangoModelFactory):
    class Meta:
        model = models.ReportLevelTotals

    report = factory.SubFactory(CommitReportFactory)
    branches = factory.Faker("pyint")
    coverage = factory.Faker("pydecimal", min_value=10, max_value=90, right_digits=2)
    hits = factory.Faker("pyint")
    lines = factory.Faker("pyint")
    methods = factory.Faker("pyint")
    misses = factory.Faker("pyint")
    partials = factory.Faker("pyint")
    files = factory.Faker("pyint")


class UploadErrorFactory(DjangoModelFactory):
    class Meta:
        model = models.UploadError

    report_session = factory.SubFactory(UploadFactory)
    error_code = factory.Iterator(
        ["file_not_in_storage", "report_expired", "report_empty"]
    )
