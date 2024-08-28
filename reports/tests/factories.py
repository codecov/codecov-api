import factory
from factory.django import DjangoModelFactory

from core.tests.factories import CommitFactory, RepositoryFactory
from graphql_api.types.enums import UploadErrorEnum
from reports import models
from reports.models import ReportResults, TestInstance


class CommitReportFactory(DjangoModelFactory):
    class Meta:
        model = models.CommitReport

    commit = factory.SubFactory(CommitFactory)


class UploadFactory(DjangoModelFactory):
    class Meta:
        model = models.ReportSession

    build_code = factory.Sequence(lambda n: f"{n}")
    report = factory.SubFactory(CommitReportFactory)
    state = "processed"


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


class UploadLevelTotalsFactory(DjangoModelFactory):
    class Meta:
        model = models.UploadLevelTotals

    report_session = factory.SubFactory(UploadFactory)


class ReportDetailsFactory(DjangoModelFactory):
    class Meta:
        model = models.ReportDetails

    report = factory.SubFactory(CommitReportFactory)
    _files_array = factory.LazyAttribute(lambda _: [])
    _files_array_storage_path = None


class UploadErrorFactory(DjangoModelFactory):
    class Meta:
        model = models.UploadError

    report_session = factory.SubFactory(UploadFactory)
    error_code = factory.Iterator(
        [
            UploadErrorEnum.FILE_NOT_IN_STORAGE,
            UploadErrorEnum.REPORT_EMPTY,
            UploadErrorEnum.REPORT_EXPIRED,
        ]
    )


class ReportResultsFactory(DjangoModelFactory):
    class Meta:
        model = ReportResults

    report = factory.SubFactory(CommitReportFactory)
    state = factory.Iterator(
        [
            ReportResults.ReportResultsStates.PENDING,
            ReportResults.ReportResultsStates.COMPLETED,
        ]
    )


class TestFactory(factory.django.DjangoModelFactory):
    class Meta:
        model = models.Test

    id = factory.Faker("word")
    name = factory.Faker("word")
    repository = factory.SubFactory(RepositoryFactory)
    commits_where_fail = []


class TestInstanceFactory(factory.django.DjangoModelFactory):
    class Meta:
        model = models.TestInstance

    test = factory.SubFactory(TestFactory)
    duration_seconds = 1.0
    outcome = TestInstance.Outcome.FAILURE.value
    failure_message = "Test failed"
    branch = "master"
    repoid = factory.SelfAttribute("test.repository.repoid")
    commitid = "123456"
    upload = factory.SubFactory(UploadFactory)
