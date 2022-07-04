from unittest.mock import patch

from django.test import override_settings
from django.urls import reverse
from rest_framework.test import APIClient, APITestCase

from billing.constants import BASIC_PLAN_NAME
from core.tests.factories import CommitFactory, OwnerFactory, RepositoryFactory
from reports.tests.factories import CommitReportFactory, UploadFactory


class ThrottlesTests(APITestCase):
    def setUp(self):
        self.owner = OwnerFactory(plan=BASIC_PLAN_NAME)
        self.client = APIClient()
        self.client.force_authenticate(user=self.owner)

    def get_response(self, repo, commitid, reportid):
        _url = reverse("new_upload.uploads", args=[repo, commitid, reportid])
        res = self.client.post(_url, data={"state": "uploaded"}, format="json")
        return res

    def request_should_throttle(self, commit, reportid):
        response = self.get_response(commit.repository.name, commit.commitid, reportid)
        assert response.status_code == 429

    def request_should_not_throttle(self, commit, reportid):
        response = self.get_response(commit.repository.name, commit.commitid, reportid)
        assert response.status_code != 429

    @patch("services.archive.StorageService")
    @override_settings(UPLOAD_THROTTLING_ENABLED=False)
    def test_check_commit_contraints_settings_disabled(self, mock_storage):
        instance = mock_storage.return_value
        instance.create_presigned_put.return_value = "presigned put"

        repository = RepositoryFactory.create(
            author__plan=BASIC_PLAN_NAME, private=True, author=self.owner
        )
        first_commit = CommitFactory.create(repository=repository)
        second_commit = CommitFactory.create(repository=repository)
        third_commit = CommitFactory.create(repository__author=repository.author)
        unrelated_commit = CommitFactory.create()

        first_report = CommitReportFactory.create(commit=first_commit)
        sec_report = CommitReportFactory.create(commit=second_commit)
        thrid_report = CommitReportFactory.create(commit=third_commit)
        unrelated_report = CommitReportFactory.create(commit=unrelated_commit)

        for i in range(150):
            UploadFactory.create(report=first_report)
            UploadFactory.create(report=sec_report)

        # no commit should be throttled
        self.request_should_not_throttle(first_commit, first_report.id)
        self.request_should_not_throttle(second_commit, sec_report.id)
        self.request_should_not_throttle(third_commit, thrid_report.id)
        self.request_should_not_throttle(unrelated_commit, unrelated_report.id)

    @patch("services.archive.StorageService")
    @override_settings(UPLOAD_THROTTLING_ENABLED=True)
    def test_check_commit_contraints_settings_enabled(self, mock_storage):
        instance = mock_storage.return_value
        instance.create_presigned_put.return_value = "presigned put"

        author = self.owner
        first_commit = CommitFactory.create(repository__author=author)

        repository = RepositoryFactory.create(author=author, private=True)
        second_commit = CommitFactory.create(repository=repository)
        third_commit = CommitFactory.create(repository=repository)
        fourth_commit = CommitFactory.create(repository=repository)

        public_repository = RepositoryFactory.create(author=author, private=False)
        public_repository_commit = CommitFactory.create(repository=public_repository)

        unrelated_commit = CommitFactory.create()

        first_report = CommitReportFactory.create(commit=first_commit)
        second_report = CommitReportFactory.create(commit=second_commit)
        third_report = CommitReportFactory.create(commit=third_commit)
        fourth_report = CommitReportFactory.create(commit=fourth_commit)
        unrelated_report = CommitReportFactory.create(commit=unrelated_commit)

        self.request_should_not_throttle(third_commit, third_report.id)

        for i in range(300):
            UploadFactory.create(report__commit__repository=public_repository)
        # ensuring public repos counts don't count torwards the quota
        self.request_should_not_throttle(third_commit, third_report.id)

        for i in range(150):
            UploadFactory.create(report=second_report)
            UploadFactory.create(report=fourth_report)
        # second and fourth commit already has uploads made, we won't block uploads to them
        self.request_should_not_throttle(second_commit, second_report.id)
        self.request_should_not_throttle(fourth_commit, fourth_report.id)

        # unrelated commit belongs to a different user. Ensuring we don't block it
        self.request_should_not_throttle(unrelated_commit, unrelated_report.id)
        # public repositories commit should never be throttled
        self.request_should_not_throttle(public_repository_commit, unrelated_report.id)

        # third commit does not have uploads made, so we block it
        self.request_should_throttle(third_commit, third_report.id)
        # first commit belongs to a different repo, but same user
        self.request_should_throttle(first_commit, first_report.id)

    @patch("services.archive.StorageService")
    def test_validate_upload_too_many_uploads_for_commit(self, mock_storage):
        instance = mock_storage.return_value
        instance.create_presigned_put.return_value = "presigned put"

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
                self.request_should_throttle(commit, report.id)
            else:
                self.request_should_not_throttle(commit, report.id)
