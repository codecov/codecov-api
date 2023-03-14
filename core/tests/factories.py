import random
from hashlib import sha1

import factory
from factory.django import DjangoModelFactory

from codecov_auth.models import RepositoryToken
from codecov_auth.tests.factories import OwnerFactory
from core import models


class RepositoryFactory(DjangoModelFactory):
    class Meta:
        model = models.Repository

    private = True
    name = factory.Faker("word")
    service_id = factory.Sequence(lambda n: f"{n}")
    author = factory.SubFactory(OwnerFactory)
    language = factory.Iterator(
        [language.value for language in models.Repository.Languages]
    )
    fork = None
    branch = "master"
    upload_token = factory.Faker("uuid4")
    using_integration = False


class CommitFactory(DjangoModelFactory):
    class Meta:
        model = models.Commit

    commitid = factory.LazyAttribute(
        lambda o: sha1(o.message.encode("utf-8")).hexdigest()
    )
    message = factory.Faker("sentence", nb_words=7)
    ci_passed = True
    pullid = 1
    author = factory.SubFactory(OwnerFactory)
    repository = factory.SubFactory(RepositoryFactory)
    branch = "master"
    totals = {
        "C": 0,
        "M": 0,
        "N": 0,
        "b": 0,
        "c": "85.00000",
        "d": 0,
        "diff": [1, 2, 1, 1, 0, "50.00000", 0, 0, 0, 0, 0, 0, 0],
        "f": 3,
        "h": 17,
        "m": 3,
        "n": 20,
        "p": 0,
        "s": 1,
    }
    parent_commit_id = factory.LazyAttribute(
        lambda o: sha1((o.message + "parent").encode("utf-8")).hexdigest()
    )
    state = "complete"


class CommitWithReportFactory(CommitFactory):
    @classmethod
    def _create(cls, model_class, *args, **kwargs):
        commit = super()._create(model_class, *args, **kwargs)

        # The following replaces the old `commits.report` JSON column
        # TODO: we may want to find another way to create this since the imports below
        # create a cyclic dependency

        from reports.tests.factories import (
            CommitReportFactory,
            ReportDetailsFactory,
            ReportLevelTotalsFactory,
            UploadFactory,
            UploadFlagMembershipFactory,
            UploadLevelTotalsFactory,
        )

        commit_report = CommitReportFactory(commit=commit)
        ReportDetailsFactory(
            report=commit_report,
            files_array=[
                {
                    "filename": "tests/__init__.py",
                    "file_index": 0,
                    "file_totals": [0, 3, 2, 1, 0, "66.66667", 0, 0, 0, 0, 0, 0, 0],
                    "session_totals": [
                        [0, 3, 2, 1, 0, "66.66667", 0, 0, 0, 0, 0, 0, 0]
                    ],
                    "diff_totals": None,
                },
                {
                    "filename": "tests/test_sample.py",
                    "file_index": 1,
                    "file_totals": [0, 7, 7, 0, 0, "100", 0, 0, 0, 0, 0, 0, 0],
                    "session_totals": [[0, 7, 7, 0, 0, "100", 0, 0, 0, 0, 0, 0, 0]],
                    "diff_totals": None,
                },
                {
                    "filename": "awesome/__init__.py",
                    "file_index": 2,
                    "file_totals": [0, 10, 8, 2, 0, "80.00000", 0, 0, 0, 0, 0, 0, 0],
                    "session_totals": [
                        [0, 10, 8, 2, 0, "80.00000", 0, 0, 0, 0, 0, 0, 0]
                    ],
                    "diff_totals": [0, 2, 1, 1, 0, "50.00000", 0, 0, 0, 0, 0, 0, 0],
                },
            ],
        )
        ReportLevelTotalsFactory(
            report=commit_report,
            files=3,
            lines=20,
            hits=17,
            misses=3,
            partials=0,
            coverage=85.0,
            branches=0,
            methods=0,
        )

        flag_unittests, created = commit.repository.flags.get_or_create(
            flag_name="unittests"
        )
        flag_integrations, created = commit.repository.flags.get_or_create(
            flag_name="integrations"
        )

        upload1 = UploadFactory(
            report=commit_report,
            order_number=0,
            storage_path="v4/raw/2019-01-10/4434BC2A2EC4FCA57F77B473D83F928C/abf6d4df662c47e32460020ab14abf9303581429/9ccc55a1-8b41-4bb1-a946-ee7a33a7fb56.txt",
        )
        UploadLevelTotalsFactory(
            report_session=upload1,
            files=3,
            lines=20,
            hits=17,
            misses=3,
            partials=0,
            coverage=85.0,
            branches=0,
            methods=0,
        )
        UploadFlagMembershipFactory(
            report_session=upload1,
            flag=flag_unittests,
        )

        upload2 = UploadFactory(
            report=commit_report,
            order_number=1,
            storage_path="v4/raw/2019-01-10/4434BC2A2EC4FCA57F77B473D83F928C/abf6d4df662c47e32460020ab14abf9303581429/9ccc55a1-8b41-4bb1-a946-ee7a33a7fb56.txt",
        )
        UploadLevelTotalsFactory(
            report_session=upload2,
            files=3,
            lines=20,
            hits=17,
            misses=3,
            partials=0,
            coverage=85.0,
            branches=0,
            methods=0,
        )
        UploadFlagMembershipFactory(
            report_session=upload2,
            flag=flag_integrations,
        )

        return commit


class PullFactory(DjangoModelFactory):
    class Meta:
        model = models.Pull

    pullid = factory.Sequence(lambda n: n)
    issueid = random.randint(1, 1000)
    commentid = factory.LazyAttribute(
        lambda o: sha1(o.title.encode("utf-8")).hexdigest()
    )
    flare = {
        "name": "",
        "color": "#e05d44",
        "lines": 14,
        "_class": None,
        "children": [
            {
                "name": "tests.py",
                "color": "#baaf1b",
                "lines": 7,
                "_class": None,
                "coverage": "85.71429",
            }
        ],
    }
    diff = [2, 3, 0, 3, 0, "0", 0, 0, 0, 0, 0, 0, 0]
    title = factory.Faker("sentence", nb_words=7)
    head = factory.LazyAttribute(lambda o: sha1(o.title.encode("utf-8")).hexdigest())
    base = factory.LazyAttribute(lambda o: sha1(o.title.encode("utf-8")).hexdigest())
    compared_to = factory.LazyAttribute(
        lambda o: sha1(o.title.encode("utf-8")).hexdigest()
    )


class BranchFactory(DjangoModelFactory):
    class Meta:
        model = models.Branch

    repository = factory.SubFactory(RepositoryFactory)
    name = factory.Faker("sentence", nb_words=1)
    head = factory.LazyAttribute(lambda o: sha1(o.name.encode("utf-8")).hexdigest())


class VersionFactory(DjangoModelFactory):
    class Meta:
        model = models.Version


class RepositoryTokenFactory(DjangoModelFactory):
    repository = factory.SubFactory(RepositoryFactory)
    key = factory.LazyFunction(RepositoryToken.generate_key)
    token_type = "profiling"

    class Meta:
        model = RepositoryToken


class CommitErrorFactory(DjangoModelFactory):
    class Meta:
        model = models.CommitError

    commit = factory.SubFactory(CommitFactory)
    error_code = factory.Faker("")
