from unittest.mock import MagicMock, Mock

from django.test import override_settings
from django.urls import reverse
from rest_framework.test import APIClient, APITestCase

from billing.constants import BASIC_PLAN_NAME
from core.tests.factories import CommitFactory, OwnerFactory, RepositoryFactory
from reports.tests.factories import CommitReportFactory, UploadFactory
from upload.throttles import UploadsPerCommitThrottle, UploadsPerWindowThrottle


class ThrottlesUnitTests(APITestCase):
    def setUp(self):
        self.owner = OwnerFactory(plan=BASIC_PLAN_NAME)

    def request_should_not_throttle(self, commit):
        self.uploads_per_window_not_throttled(commit)
        self.uploads_per_commit_not_throttled(commit)

    def set_view_obj(self, commit):
        view = MagicMock()
        d = {"commitid": commit.commitid}
        view.kwargs.get.side_effect = d.get
        view.get_repo.return_value = commit.repository
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
    def test_check_commit_contraints_settings_disabled(self):
        repository = RepositoryFactory(
            author__plan=BASIC_PLAN_NAME, private=True, author=self.owner
        )
        first_commit = CommitFactory(repository=repository)
        second_commit = CommitFactory(repository=repository)
        third_commit = CommitFactory(repository__author=repository.author)
        unrelated_commit = CommitFactory()

        first_report = CommitReportFactory(commit=first_commit)
        sec_report = CommitReportFactory(commit=second_commit)

        for i in range(150):
            UploadFactory(report=first_report)
            UploadFactory(report=sec_report)

        # no commit should be throttled
        self.request_should_not_throttle(first_commit)
        self.request_should_not_throttle(second_commit)
        self.request_should_not_throttle(third_commit)
        self.request_should_not_throttle(unrelated_commit)

    @override_settings(UPLOAD_THROTTLING_ENABLED=True)
    def test_check_commit_contraints_settings_enabled(self):
        author = self.owner
        first_commit = CommitFactory.create(repository__author=author)

        repository = RepositoryFactory.create(author=author, private=True)
        second_commit = CommitFactory.create(repository=repository)
        third_commit = CommitFactory.create(repository=repository)
        fourth_commit = CommitFactory.create(repository=repository)

        public_repository = RepositoryFactory.create(author=author, private=False)
        public_repository_commit = CommitFactory.create(repository=public_repository)

        unrelated_commit = CommitFactory.create()

        second_report = CommitReportFactory.create(commit=second_commit)
        fourth_report = CommitReportFactory.create(commit=fourth_commit)
        self.request_should_not_throttle(third_commit)

        for i in range(300):
            UploadFactory.create(report__commit__repository=public_repository)
        # ensuring public repos counts don't count torwards the quota
        self.request_should_not_throttle(third_commit)

        for i in range(150):
            UploadFactory.create(report=second_report)
            UploadFactory.create(report=fourth_report)
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
