from unittest.mock import MagicMock, patch
from wsgiref import headers

from django.http import HttpRequest, QueryDict
from django.test import TestCase
from django.urls import reverse
from rest_framework.test import APIClient, APITestCase

from core.tests.factories import CommitFactory, OwnerFactory, RepositoryFactory
from services.archive import ArchiveService
from services.storage import StorageService
from upload.views.uploads import MutationTestingUploadView


def test_uploads_get_not_allowed(client):
    url = reverse("new_upload.uploads", args=["the-repo", "commit-sha", "report-id"])
    assert url == "/upload/the-repo/commits/commit-sha/reports/report-id/uploads"
    res = client.get(url)
    assert res.status_code == 401


def test_uploads_post_empty(client):
    url = reverse("new_upload.uploads", args=["the-repo", "commit-sha", "report-id"])
    assert url == "/upload/the-repo/commits/commit-sha/reports/report-id/uploads"
    res = client.post(url, content_type="application/json", data={})
    assert res.status_code == 401


def test_mutation_uploads_post_empty(client):
    url = reverse(
        "new_upload.mutation_uploads", args=["the-repo", "commit-sha", "report-id"]
    )
    assert (
        url == "/upload/the-repo/commits/commit-sha/reports/report-id/mutation_uploads"
    )
    res = client.post(url, content_type="application/json", data={})
    assert res.status_code == 401


class MutationUploadTests(APITestCase, TestCase):
    def setUp(self):
        self.repository = RepositoryFactory()
        self.client = APIClient()
        self.uploader_class = MutationTestingUploadView()

    def test_get_upload_params(self):
        request_params = {
            "version": "v4",
            "commit": "3be5c52bd748c508a7e96993c02cf3518c816e84",
            "slug": "codecov/codecov-api",
            "token": "testbtznwf3ooi3xlrsnetkddj5od731pap9",
            "service": "circleci",
            "pull_request": "undefined",
            "flags": "this-is-a-flag,this-is-another-flag",
            "name": "",
            "branch": "HEAD",
            "param_doesn't_exist_but_still_should_not_error": True,
            "s3": 123,
            "build_url": "https://thisisabuildurl.com",
            "_did_change_merge_commit": False,
            "parent": "123abc",
        }

        expected_result = {
            "version": "v4",
            "commit": "3be5c52bd748c508a7e96993c02cf3518c816e84",
            "slug": "codecov/codecov-api",
            "owner": "codecov",
            "repo": "codecov-api",
            "token": "testbtznwf3ooi3xlrsnetkddj5od731pap9",
            "service": "circleci",
            "pr": None,
            "pull_request": None,
            "flags": "this-is-a-flag,this-is-another-flag",
            "param_doesn't_exist_but_still_should_not_error": True,
            "s3": 123,
            "build_url": "https://thisisabuildurl.com",
            "job": None,
            "using_global_token": False,
            "branch": None,
            "_did_change_merge_commit": False,
            "parent": "123abc",
        }
        query_dict_request_params = QueryDict("", mutable=True)
        query_dict_request_params.update(request_params)
        request = HttpRequest()
        request.query_params = query_dict_request_params
        parsed_params = self.uploader_class._get_upload_params(request)
        assert expected_result == parsed_params

    def test_get_upload_params(self):
        request_params_incomplete = {
            "name": "",
            "branch": "HEAD",
            "param_doesn't_exist_but_still_should_not_error": True,
            "s3": 123,
            "build_url": "https://thisisabuildurl.com",
            "_did_change_merge_commit": False,
            "parent": "123abc",
        }
        query_dict_request_params = QueryDict("", mutable=True)
        query_dict_request_params.update(request_params_incomplete)
        request = HttpRequest()
        request.query_params = query_dict_request_params
        parsed_params = self.uploader_class._get_upload_params(request)
        assert parsed_params == None

    @patch("upload.views.uploads.ArchiveService")
    def test_generate_presigned_put(self, mock_archive_service):
        instance = mock_archive_service.return_value
        instance.create_raw_upload_presigned_put.return_value = "presigned url"
        generated_presigned_put = self.uploader_class._generate_presigned_put(
            self.repository, "commit_sha", "report_id"
        )
        assert generated_presigned_put == "presigned url"
