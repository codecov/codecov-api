from unittest.mock import MagicMock, Mock, patch

from django.test import override_settings
from rest_framework.test import APITestCase
from shared.django_apps.reports.models import ReportType
from shared.upload.utils import UploaderType, insert_coverage_measurement

from core.tests.factories import CommitFactory, OwnerFactory, RepositoryFactory
from plan.constants import PlanName
from reports.tests.factories import CommitReportFactory, UploadFactory
from services.redis_configuration import get_redis_connection
from upload.throttles import UploadsPerCommitThrottle, UploadsPerWindowThrottle


class ThrottlesUnitTests(APITestCase):
    def setUp(self):
        self.owner = OwnerFactory(
            plan=PlanName.BASIC_PLAN_NAME.value, max_upload_limit=150
        )

    def request_should_not_throttle(self, commit):
        self.uploads_per_window_not_throttled(commit)
        self.uploads_per_commit_not_throttled(commit)

    def set_view_obj(self, commit):
        view = MagicMock()
        view.get_repo.return_value = commit.repository
        view.get_commit.return_value = commit
        return view

    def uploads_per_commit_throttled(self, commit):
        throttle_class = UploadsPerCommitThrottle()
        view = self.set_view_obj(commit)
        assert not throttle_class.allow_request(Mock(), view)

    def uploads_per_window_throttled(self, commit):
        throttle_class = UploadsPerWindowThrottle()
        view = self.set_view_obj(commit)
        assert not throttle_class.allow_request(Mock(), view)

    def uploads_per_commit_not_throttled(self, commit):
        throttle_class = UploadsPerCommitThrottle()
        view = self.set_view_obj(commit)
        assert throttle_class.allow_request(Mock(), view)

    def uploads_per_window_not_throttled(self, commit):
        throttle_class = UploadsPerWindowThrottle()
        view = self.set_view_obj(commit)
        assert throttle_class.allow_request(Mock(), view)

    @override_settings(UPLOAD_THROTTLING_ENABLED=False)
    def test_check_commit_constraints_settings_disabled(self):
        repository = RepositoryFactory(
            author__plan=PlanName.BASIC_PLAN_NAME.value,
            private=True,
            author=self.owner,
        )
        first_commit = CommitFactory(repository=repository)
        second_commit = CommitFactory(repository=repository)
        third_commit = CommitFactory(repository__author=repository.author)
        unrelated_commit = CommitFactory()

        first_report = CommitReportFactory(
            commit=first_commit, report_type=ReportType.COVERAGE.value
        )
        sec_report = CommitReportFactory(
            commit=second_commit, report_type=ReportType.COVERAGE.value
        )

        for i in range(150):
            first_upload = UploadFactory(report=first_report)
            insert_coverage_measurement(
                owner=self.owner,
                repo=repository,
                commit=first_commit,
                upload=first_upload,
                uploader_used=UploaderType.CLI.value,
                private_repo=repository.private,
                report_type=first_report.report_type,
            )
            second_upload = UploadFactory(report=sec_report)
            insert_coverage_measurement(
                owner=self.owner,
                repo=repository,
                commit=second_commit,
                upload=second_upload,
                uploader_used=UploaderType.CLI.value,
                private_repo=repository.private,
                report_type=sec_report.report_type,
            )

        # no commit should be throttled
        self.request_should_not_throttle(first_commit)
        self.request_should_not_throttle(second_commit)
        self.request_should_not_throttle(third_commit)
        self.request_should_not_throttle(unrelated_commit)

    @override_settings(UPLOAD_THROTTLING_ENABLED=True)
    def test_check_commit_constraints_settings_enabled(self):
        author = self.owner
        first_commit = CommitFactory.create(repository__author=author)

        repository = RepositoryFactory.create(author=author, private=True)
        second_commit = CommitFactory.create(repository=repository)
        third_commit = CommitFactory.create(repository=repository)
        fourth_commit = CommitFactory.create(repository=repository)

        public_repository = RepositoryFactory.create(author=author, private=False)
        public_repository_commit = CommitFactory.create(repository=public_repository)

        unrelated_commit = CommitFactory.create()

        second_report = CommitReportFactory.create(
            commit=second_commit, report_type=ReportType.COVERAGE.value
        )
        fourth_report = CommitReportFactory.create(
            commit=fourth_commit, report_type=ReportType.COVERAGE.value
        )
        self.request_should_not_throttle(third_commit)

        for i in range(300):
            upload = UploadFactory.create(report__commit__repository=public_repository)
            insert_coverage_measurement(
                owner=author,
                repo=public_repository,
                commit=second_commit,
                upload=upload,
                uploader_used=UploaderType.CLI.value,
                private_repo=public_repository.private,
                report_type=second_report.report_type,
            )
        # ensuring public repos counts don't count towards the quota
        self.request_should_not_throttle(third_commit)

        for i in range(150):
            second_upload = UploadFactory.create(report=second_report)
            insert_coverage_measurement(
                owner=author,
                repo=repository,
                commit=second_commit,
                upload=second_upload,
                uploader_used=UploaderType.CLI.value,
                private_repo=repository.private,
                report_type=second_report.report_type,
            )
            fourth_upload = UploadFactory.create(report=fourth_report)
            insert_coverage_measurement(
                owner=author,
                repo=repository,
                commit=fourth_commit,
                upload=fourth_upload,
                uploader_used=UploaderType.CLI.value,
                private_repo=repository.private,
                report_type=fourth_report.report_type,
            )
        # second and fourth commit already has uploads made, we won't block uploads to them
        self.request_should_not_throttle(second_commit)
        self.request_should_not_throttle(fourth_commit)

        # unrelated commit belongs to a different user. Ensuring we don't block it
        self.request_should_not_throttle(unrelated_commit)
        # public repositories commit should never be throttled
        self.request_should_not_throttle(public_repository_commit)

        # third commit does not have uploads made, so we block it
        self.uploads_per_window_throttled(third_commit)
        # first commit belongs to a different repo, but same user
        self.uploads_per_window_throttled(first_commit)

    def test_validate_upload_too_many_uploads_for_commit(self):
        par = [(151, 0, False), (151, 151, True), (0, 0, False), (0, 200, True)]
        for totals_column_count, rows_count, should_raise in par:
            owner = self.owner
            repo = RepositoryFactory.create(author=owner)
            commit = CommitFactory.create(
                totals={"s": totals_column_count}, repository=repo
            )
            report = CommitReportFactory.create(commit=commit)
            for i in range(rows_count):
                UploadFactory.create(report=report)

            if should_raise:
                self.uploads_per_commit_throttled(commit)
            else:
                self.request_should_not_throttle(commit)

    # @patch("redis.Redis.get")
    # def test_validate_commit_count_uses_redis(self, mocked_get):
    #     par = [(151, 0, False), (151, 250, True), (0, 300, True), (0, 200, False)]
    #     for totals_column_count, window_count, should_raise in par:
    #         owner = self.owner
    #         repo = RepositoryFactory.create(author=owner)
    #         mocked_get.return_value = window_count
    #         commit = CommitFactory.create(
    #             totals={"s": totals_column_count}, repository=repo
    #         )
    #         if should_raise:
    #             self.uploads_per_window_throttled(commit)
    #         else:
    #             self.request_should_not_throttle(commit)

    def test_validate_redis_counter(self):
        redis = get_redis_connection()
        owner = self.owner
        cache_key = f"monthly_upload_usage_{owner.ownerid}"
        redis.set(cache_key, 1, ex=259200)
        repo = RepositoryFactory.create(author=owner)
        commit = CommitFactory.create(totals={}, repository=repo)
        self.request_should_not_throttle(commit)
        assert redis.get(cache_key) == b"1"
        redis.delete(cache_key)

    # @patch("redis.Redis.get")
    # def test_handles_redis_error(self, mocked_get):
    #     def raise_oserror(*args, **kwargs):
    #         raise OSError

    #     mocked_get.side_effect = raise_oserror
    #     owner = self.owner
    #     repo = RepositoryFactory.create(author=owner)
    #     commit = CommitFactory.create(totals={}, repository=repo)
    #     self.request_should_not_throttle(commit)
    #     repository = RepositoryFactory.create(author=owner, private=True)
    #     for i in range(300):
    #         UploadFactory.create(report__commit__repository=repository)
    #     self.uploads_per_window_throttled(commit)
