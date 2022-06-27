from unittest.mock import patch

from django.http import HttpRequest, QueryDict
from django.test import TestCase
from django.urls import reverse
from pytest import param
from billing.constants import BASIC_PLAN_NAME
from codecov_auth.tests.factories import OwnerFactory
from rest_framework.test import APIClient, APITestCase

from core.tests.factories import RepositoryFactory
from upload.views.uploads import MutationTestingUploadView


def test_uploads_get_not_allowed(client, db):
    url = reverse("new_upload.uploads", args=["the-repo", "commit-sha", "report-id"])
    assert url == "/upload/the-repo/commits/commit-sha/reports/report-id/uploads"
    client.force_login(OwnerFactory(plan=BASIC_PLAN_NAME))
    res = client.get(url)
    assert res.status_code == 405

def test_uploads_post_empty(client, db):
    url = reverse("new_upload.uploads", args=["the-repo", "commit-sha", "report-id"])
    assert url == "/upload/the-repo/commits/commit-sha/reports/report-id/uploads"
    client.force_login(OwnerFactory(plan=BASIC_PLAN_NAME))
    res = client.post(url, content_type="application/json", data={})
    assert res.status_code == 404


class MutationUploadTests(APITestCase, TestCase):
    def setUp(self):
        self.owner = OwnerFactory(plan=BASIC_PLAN_NAME)
        self.repository = RepositoryFactory(name='the_repo', author__username='codecov')
        self.client = APIClient()
        self.uploader_class = MutationTestingUploadView()
        self.client.force_authenticate(user=self.owner)

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

    @patch("upload.views.uploads.parse_params") # Mocking cause I'm not sure we're gonna actually use it later
    @patch("upload.views.uploads.determine_repo_for_upload")
    @patch("upload.views.uploads.ArchiveService")
    def test_mutation_test_uplaod(self, mock_archive_service, mock_repo_for_upload, mock_parse_params):
        instance = mock_archive_service.return_value
        instance.create_raw_upload_presigned_put.return_value = "presigned url"
        mock_repo_for_upload.return_value = self.repository
        mock_parse_params.return_value = {} 
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
        url = reverse("new_upload.mutation_uploads", args=[self.repository.name, "commit-sha", "report-id"])
        response = self.client.post(url, data=request_params)
        assert response.status_code == 200
        assert response.content.decode() == "presigned url"

    @patch("upload.views.uploads.parse_params") # Mocking cause I'm not sure we're gonna actually use it later
    @patch("upload.views.uploads.determine_repo_for_upload")
    @patch("upload.views.uploads.ArchiveService")
    def test_mutation_test_upload_not_codecov(self, mock_archive_service, mock_repo_for_upload, mock_parse_params):
        instance = mock_archive_service.return_value
        instance.create_raw_upload_presigned_put.return_value = "presigned url"
        mock_repo_for_upload.return_value = RepositoryFactory(name='other_repo', author__name='batata')
        mock_parse_params.return_value = {} 
        request_params = {
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
        url = reverse("new_upload.mutation_uploads", args=[self.repository.name, "commit-sha", "report-id"])
        response = self.client.post(url, data=request_params)
        assert response.status_code == 403
        assert response.content.decode() == "Feature currently unnavailable outside codecov"


