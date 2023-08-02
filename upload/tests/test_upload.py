import time
from datetime import datetime, timedelta
from json import dumps, loads
from unittest.mock import ANY, PropertyMock, call, patch
from urllib.parse import urlencode

import pytest
import requests
from ddf import G
from django.core.exceptions import MultipleObjectsReturned
from django.test import TestCase, override_settings
from django.utils import timezone
from rest_framework import status
from rest_framework.exceptions import NotFound, ValidationError
from rest_framework.reverse import reverse
from rest_framework.test import APIRequestFactory, APITestCase
from shared.torngit.exceptions import (
    TorngitClientGeneralError,
    TorngitObjectNotFoundError,
)
from simplejson import JSONDecodeError

from codecov_auth.models import Owner
from codecov_auth.tests.factories import OwnerFactory
from core.models import Commit, Repository
from reports.tests.factories import CommitReportFactory, UploadFactory
from upload.helpers import (
    determine_repo_for_upload,
    determine_upload_branch_to_use,
    determine_upload_commit_to_use,
    determine_upload_pr_to_use,
    dispatch_upload_task,
    get_global_tokens,
    insert_commit,
    parse_headers,
    parse_params,
    store_report_in_redis,
    validate_upload,
)
from upload.tokenless.tokenless import TokenlessUploadHandler
from utils.encryption import encryptor


def mock_get_config_global_upload_tokens(*args):
    if args == ("github", "global_upload_token"):
        return "githubuploadtoken"
    if args == ("gitlab", "global_upload_token"):
        return "gitlabuploadtoken"
    if args == ("bitbucket_server", "global_upload_token"):
        return "bitbucketserveruploadtoken"


class MockRedis:
    def __init__(self, blacklisted=False, *args, **kwargs):
        self.blacklisted = blacklisted
        self.expected_task_key = kwargs.get("expected_task_key")
        self.expected_task_arguments = kwargs.get("expected_task_arguments")
        self.expected_expire_time = kwargs.get("expected_expire_time")

    def rpush(self, key, value):
        assert key == self.expected_task_key
        assert value == dumps(self.expected_task_arguments)

    def expire(self, key, expire_time):
        assert key == self.expected_task_key
        assert expire_time == self.expected_expire_time

    def sismember(self, key, repoid):
        return self.blacklisted

    def get(self, key):
        return 10

    def setex(self, redis_key, expire_time, report):
        return


class UploadHandlerHelpersTest(TestCase):
    def test_parse_params_validates_valid_input(self):
        request_params = {
            "version": "v4",
            "commit": "3be5c52bd748c508a7e96993c02cf3518c816e84",
            "slug": "codecov/codecov-api",
            "token": "4a24929b-9276-4784-8e85-a7a008a32037",
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
            "token": "4a24929b-9276-4784-8e85-a7a008a32037",
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

        parsed_params = parse_params(request_params)
        assert expected_result == parsed_params

    def test_parse_params_errors_for_invalid_input(self):
        request_params = {
            "version": "v5",
            "slug": "not-a-valid-slug",
            "token": "4a24929b-9276-4784-8e85-a7a008a32037",
            "service": "circleci",
            "pr": 123,
            "flags": "not_a_valid_flag!!?!",
            "s3": "this should be an integer",
            "build_url": "not a valid url!",
            "_did_change_merge_commit": "yup",
            "parent": 123,
        }

        with self.assertRaises(ValidationError) as err:
            parse_params(request_params)

        assert len(err.exception.detail) == 9

    def test_parse_params_transforms_input(self):
        request_params = {
            "version": "v4",
            "commit": "3BE5C52BD748C508a7e96993c02cf3518c816e84",
            "slug": "codecov/subgroup/codecov-api",
            "service": "travis-org",
            "pull_request": "439",
            "pr": "",
            "branch": "origin/test-branch",
            "travis_job_id": "travis-jobID",
            "build": "nil",
        }

        expected_result = {
            "version": "v4",
            "commit": "3be5c52bd748c508a7e96993c02cf3518c816e84",  # converted to lower case
            "slug": "codecov/subgroup/codecov-api",
            "owner": "codecov:subgroup",  # extracted from slug
            "repo": "codecov-api",  # extracted from slug
            "service": "travis",  # "travis-org" converted to "travis"
            "pr": "439",  # populated from "pull_request" field since none was provided
            "pull_request": "439",
            "branch": "test-branch",  # "origin/" removed from name
            "job": "travis-jobID",  # populated from "travis_job_id" since none was provided
            "travis_job_id": "travis-jobID",
            "build": None,  # "nil" coerced to None
            "using_global_token": False,
        }

        parsed_params = parse_params(request_params)
        assert expected_result == parsed_params

        request_params = {
            "version": "v4",
            "commit": "3be5c52bd748c508a7e96993c02cf3518c816e84",
            "pr": "967",
            "pull_request": "null",
            "branch": "refs/heads/another-test-branch",
            "job": "jobID",
            "travis_job_id": "travis-jobID",
        }

        expected_result = {
            "version": "v4",
            "commit": "3be5c52bd748c508a7e96993c02cf3518c816e84",
            "owner": None,  # set to "None" since slug wasn't provided
            "repo": None,  # set to "None" since slug wasn't provided
            "pr": "967",  # not populated from "pull_request"
            "pull_request": None,  # "null" coerced to None
            "branch": "another-test-branch",  # "refs/heads" removed
            "job": "jobID",  # not populated from "travis_job_id"
            "travis_job_id": "travis-jobID",
            "using_global_token": False,
            "service": None,  # defaulted to None if not provided and not using global upload token
        }

        parsed_params = parse_params(request_params)
        assert expected_result == parsed_params

        request_params = {
            "version": "v4",
            "commit": "3be5c52bd748c508a7e96993c02cf3518c816e84",
            "slug": "",
            "pr": "",
            "pull_request": "156",
            "job": None,
            "travis_job_id": "travis-jobID",
        }

        expected_result = {
            "version": "v4",
            "commit": "3be5c52bd748c508a7e96993c02cf3518c816e84",
            "owner": None,  # set to "None" since slug wasn't provided
            "repo": None,  # set to "None" since slug wasn't provided
            "pr": "156",  # populated from "pull_request"
            "pull_request": "156",
            "job": "travis-jobID",  # populated from "travis_job_id"
            "travis_job_id": "travis-jobID",
            "service": None,  # defaulted to None if not provided and not using global upload token
            "using_global_token": False,
        }

        parsed_params = parse_params(request_params)
        assert expected_result == parsed_params

    @patch("upload.helpers.get_config")
    def test_parse_params_recognizes_global_token(self, mock_get_config):
        mock_get_config.side_effect = mock_get_config_global_upload_tokens

        request_params = {
            "version": "v4",
            "commit": "3be5c52bd748c508a7e96993c02cf3518c816e84",
            "token": "bitbucketserveruploadtoken",
        }

        expected_result = {
            "version": "v4",
            "commit": "3be5c52bd748c508a7e96993c02cf3518c816e84",
            "token": "bitbucketserveruploadtoken",
            "using_global_token": True,
            "service": "bitbucket_server",
            "job": None,
            "owner": None,
            "pr": None,
            "repo": None,
        }

        parsed_params = parse_params(request_params)
        assert expected_result == parsed_params

    @patch("upload.helpers.get_config")
    def test_parse_params_recognizes_global_token_overrides_service(
        self, mock_get_config
    ):
        mock_get_config.side_effect = mock_get_config_global_upload_tokens

        request_params = {
            "version": "v4",
            "commit": "3be5c52bd748c508a7e96993c02cf3518c816e84",
            "token": "bitbucketserveruploadtoken",
            "service": "jenkins",
        }

        expected_result = {
            "version": "v4",
            "commit": "3be5c52bd748c508a7e96993c02cf3518c816e84",
            "token": "bitbucketserveruploadtoken",
            "using_global_token": True,
            "service": "bitbucket_server",
            "job": None,
            "owner": None,
            "pr": None,
            "repo": None,
        }

        parsed_params = parse_params(request_params)
        assert expected_result == parsed_params

    @patch("upload.helpers.get_config")
    def test_get_global_tokens(self, mock_get_config):
        mock_get_config.side_effect = mock_get_config_global_upload_tokens

        expected_result = {
            "githubuploadtoken": "github",
            "gitlabuploadtoken": "gitlab",
            "bitbucketserveruploadtoken": "bitbucket_server",
        }

        global_tokens = get_global_tokens()
        assert expected_result == global_tokens

    def test_determine_repo_upload(self):
        with self.subTest("token found"):
            org = G(Owner)
            repo = G(Repository, author=org)

            params = {
                "version": "v4",
                "using_global_token": False,
                "token": repo.upload_token,
            }

            assert repo == determine_repo_for_upload(params)

        with self.subTest("token not found"):
            org = G(Owner)
            repo = G(Repository, author=org)

            params = {
                "version": "v4",
                "using_global_token": False,
                "token": "4a24929b-9276-4784-8e85-a7a008a32037",
            }

            with self.assertRaises(NotFound):
                determine_repo_for_upload(params)

        with self.subTest("missing token or service"):
            params = {"version": "v4", "using_global_token": False, "service": None}

            with self.assertRaises(ValidationError):
                determine_repo_for_upload(params)

    @patch.object(requests, "get")
    def test_determine_repo_upload_tokenless(self, mock_get):
        org = G(Owner, username="codecov", service="github")
        repo = G(Repository, author=org)
        expected_response = {
            "id": 732059764,
            "finishTime": f"{datetime.utcnow()}",
            "status": "inProgress",
            "sourceVersion": "3be5c52bd748c508a7e96993c02cf3518c816e84",
            "buildNumber": "732059764",
            "allow_failure": None,
            "number": "498.1",
            "state": "passed",
            "started_at": "2020-10-01T20:02:55Z",
            "finished_at": f"{datetime.utcnow()}".split(".")[0],
            "project": {"visibility": "public", "repositoryType": "github"},
            "triggerInfo": {"pr.sourceSha": "3be5c52bd748c508a7e96993c02cf3518c816e84"},
            "build": {
                "@type": "build",
                "@href": "/build/732059763",
                "@representation": "minimal",
                "id": 732059763,
                "number": "498",
                "state": "passed",
                "duration": 84,
                "event_type": "push",
                "previous_state": "passed",
                "pull_request_title": None,
                "pull_request_number": None,
                "started_at": "2020-10-01T20:01:31Z",
                "finished_at": "2020-10-01T20:02:55Z",
                "private": False,
                "priority": False,
                "jobs": [{"jobId": "732059764"}],
            },
            "queue": "builds.gce",
            "repository": {
                "@type": "repository",
                "@href": "/repo/25205338",
                "@representation": "minimal",
                "id": 25205338,
                "type": "GitHub",
                "name": "python-standard",
                "slug": f"{org.username}/{repo.name}",
            },
            "commit": {
                "@type": "commit",
                "@representation": "minimal",
                "id": 226208830,
                "sha": "3be5c52bd748c508a7e96993c02cf3518c816e84",
                "ref": "refs/heads/master",
                "message": "New Build: 10/01/20 20:00:54",
                "compare_url": "https://github.com/codecov/python-standard/compare/28392734979c...2485b28f9862",
                "committed_at": "2020-10-01T20:00:55Z",
            },
        }

        mock_get.return_value.status_code.return_value = 200
        mock_get.return_value.json.return_value = expected_response

        params = {
            "version": "v4",
            "commit": "3be5c52bd748c508a7e96993c02cf3518c816e84",
            "slug": f"{org.username}/{repo.name}",
            "owner": org.username,
            "repo": repo.name,
            "service": "travis",
            "pr": None,
            "pull_request": None,
            "flags": "this-is-a-flag,this-is-another-flag",
            "param_doesn't_exist_but_still_should_not_error": True,
            "s3": 123,
            "build_url": "https://thisisabuildurl.com",
            "job": "732059764",
            "build": "732059764",
            "using_global_token": False,
            "branch": None,
            "project": "p12",
            "server_uri": "https://",
            "_did_change_merge_commit": False,
            "parent": "123abc",
        }

        assert repo == determine_repo_for_upload(params)

        params["service"] = "appveyor"

        assert repo == determine_repo_for_upload(params)

        params["service"] = "azure_pipelines"

        assert repo == determine_repo_for_upload(params)

    def test_determine_upload_branch_to_use(self):
        with self.subTest("no branch and no pr provided"):
            upload_params = {"branch": None, "pr": None}
            repo_default_branch = "defaultbranch"

            expected_value = "defaultbranch"
            assert expected_value == determine_upload_branch_to_use(
                upload_params, repo_default_branch
            )

        with self.subTest("pullid in branch name"):
            upload_params = {"branch": "pr/123", "pr": None}
            repo_default_branch = "defaultbranch"

            expected_value = None
            assert expected_value == determine_upload_branch_to_use(
                upload_params, repo_default_branch
            )

        with self.subTest("branch and no pr provided"):
            upload_params = {"branch": "uploadbranch", "pr": None}
            repo_default_branch = "defaultbranch"

            expected_value = "uploadbranch"
            assert expected_value == determine_upload_branch_to_use(
                upload_params, repo_default_branch
            )

        with self.subTest("branch and pr provided"):
            upload_params = {"branch": "uploadbranch", "pr": "123"}
            repo_default_branch = "defaultbranch"

            expected_value = "uploadbranch"
            assert expected_value == determine_upload_branch_to_use(
                upload_params, repo_default_branch
            )

    def test_determine_upload_pr_to_use(self):
        with self.subTest("pullid in branch"):
            upload_params = {"branch": "pr/123", "pr": "456"}

            expected_value = "123"
            assert expected_value == determine_upload_pr_to_use(upload_params)

        with self.subTest("pullid in arguments, no pullid in branch"):
            upload_params = {"branch": "uploadbranch", "pr": "456"}

            expected_value = "456"
            assert expected_value == determine_upload_pr_to_use(upload_params)

        with self.subTest("pullid not provided"):
            upload_params = {"branch": "uploadbranch", "pr": None}

            expected_value = None
            assert expected_value == determine_upload_pr_to_use(upload_params)

        with self.subTest("pullid not provided, branch not provided"):
            upload_params = {"branch": None, "pr": None}

            expected_value = None
            assert expected_value == determine_upload_pr_to_use(upload_params)

        with self.subTest("pullid set to true"):
            upload_params = {"branch": None, "pr": "true"}

            expected_value = None
            assert expected_value == determine_upload_pr_to_use(upload_params)

    @patch("upload.helpers.RepoProviderService")
    @patch("upload.helpers._get_git_commit_data")
    def test_determine_upload_commit_to_use(
        self, mock_repo_provider_service, mock_async
    ):
        mock_repo_provider_service.return_value = {
            "message": "Merge 1c78206f1a46dc6db8412a491fc770eb7d0f8a47 into 261aa931e8e3801ad95a31bbc3529de2bba436c8"
        }

        with self.subTest("not a github commit"):
            org = G(
                Owner,
                service="bitbucket",
                oauth_token=encryptor.encode("hahahahaha").decode(),
            )
            repo = G(Repository, author=org)
            upload_params = {
                "service": "bitbucket",
                "commit": "3be5c52bd748c508a7e96993c02cf3518c816e84",
            }
            assert (
                "3be5c52bd748c508a7e96993c02cf3518c816e84"
                == determine_upload_commit_to_use(upload_params, repo)
            )

        with self.subTest("merge commit"):
            org = G(
                Owner,
                service="github",
                oauth_token=encryptor.encode("hahahahaha").decode(),
            )
            repo = G(Repository, author=org)
            upload_params = {
                "service": "github",
                "commit": "3084886b7ff869dcf327ad1d28a8b7d34adc7584",
            }
            # Should use id from merge commit message, not from params
            assert (
                "1c78206f1a46dc6db8412a491fc770eb7d0f8a47"
                == determine_upload_commit_to_use(upload_params, repo)
            )

        with self.subTest("just no bot available"):
            org = G(Owner, service="github", oauth_token=None)
            repo = G(Repository, author=org, private=True)
            upload_params = {
                "service": "github",
                "commit": "3084886b7ff869dcf327ad1d28a8b7d34adc7584",
            }
            # Should use id from merge commit message, not from params
            assert (
                "3084886b7ff869dcf327ad1d28a8b7d34adc7584"
                == determine_upload_commit_to_use(upload_params, repo)
            )

        with self.subTest("merge commit with did_change_merge_commit argument"):
            org = G(
                Owner,
                service="github",
                oauth_token=encryptor.encode("hahahahaha").decode(),
            )
            repo = G(Repository, author=org)
            upload_params = {
                "service": "github",
                "commit": "3084886b7ff869dcf327ad1d28a8b7d34adc7584",
                "_did_change_merge_commit": True,
            }
            # Should use the commit id provided in params, not the one from the commit message
            assert (
                "3084886b7ff869dcf327ad1d28a8b7d34adc7584"
                == determine_upload_commit_to_use(upload_params, repo)
            )

        with self.subTest("use repo bot token when available"):
            bot = OwnerFactory()
            org = G(Owner, service="github")
            repo = G(Repository, author=org, bot=bot)

            upload_params = {
                "service": "github",
                "commit": "3084886b7ff869dcf327ad1d28a8b7d34adc7584",
            }

            determine_upload_commit_to_use(upload_params, repo)

            assert (
                "1c78206f1a46dc6db8412a491fc770eb7d0f8a47"
                == determine_upload_commit_to_use(upload_params, repo)
            )

        mock_async.side_effect = [TorngitClientGeneralError(500, None, None)]

        with self.subTest("HTTP error"):
            org = G(Owner, service="github")
            repo = G(Repository, author=org)
            upload_params = {
                "service": "github",
                "commit": "3084886b7ff869dcf327ad1d28a8b7d34adc7584",
                "_did_change_merge_commit": False,
            }
            assert (
                "3084886b7ff869dcf327ad1d28a8b7d34adc7584"
                == determine_upload_commit_to_use(upload_params, repo)
            )

        mock_async.side_effect = [TorngitObjectNotFoundError(500, None)]

        with self.subTest("HTTP error"):
            org = G(Owner, service="github")
            repo = G(Repository, author=org)
            upload_params = {
                "service": "github",
                "commit": "3084886b7ff869dcf327ad1d28a8b7d34adc7584",
                "_did_change_merge_commit": False,
            }
            assert (
                "3084886b7ff869dcf327ad1d28a8b7d34adc7584"
                == determine_upload_commit_to_use(upload_params, repo)
            )

    def test_insert_commit(self):
        org = G(Owner)
        repo = G(Repository, author=org)

        with self.subTest("newly created"):
            insert_commit(
                "3084886b7ff869dcf327ad1d28a8b7d34adc7584", "test", "123", repo, org
            )

            commit = Commit.objects.get(
                commitid="3084886b7ff869dcf327ad1d28a8b7d34adc7584"
            )
            assert commit.repository == repo
            assert commit.state == "pending"
            assert commit.branch == "test"
            assert commit.pullid == 123
            assert commit.merged == False
            assert commit.parent_commit_id == None

        with self.subTest("commit already in database"):
            G(
                Commit,
                commitid="1c78206f1a46dc6db8412a491fc770eb7d0f8a47",
                branch="apples",
                pullid="456",
                repository=repo,
                parent_commit_id=None,
            )
            insert_commit(
                "1c78206f1a46dc6db8412a491fc770eb7d0f8a47",
                "oranges",
                "123",
                repo,
                org,
                parent_commit_id="different_parent_commit",
            )

            commit = Commit.objects.get(
                commitid="1c78206f1a46dc6db8412a491fc770eb7d0f8a47"
            )
            assert commit.repository == repo
            assert commit.state == "pending"
            assert commit.branch == "apples"
            assert commit.pullid == 456
            assert commit.merged == None
            assert commit.parent_commit_id == "different_parent_commit"

        with self.subTest("parent provided"):
            parent = G(Commit)
            insert_commit(
                "8458a8c72aafb5fb4c5cd58f467a2f71298f1b61",
                "test",
                None,
                repo,
                org,
                parent_commit_id=parent.commitid,
            )

            commit = Commit.objects.get(
                commitid="8458a8c72aafb5fb4c5cd58f467a2f71298f1b61"
            )
            assert commit.repository == repo
            assert commit.state == "pending"
            assert commit.branch == "test"
            assert commit.pullid == None
            assert commit.merged == None
            assert commit.parent_commit_id == parent.commitid

    def test_parse_request_headers(self):
        with self.subTest("Invalid content disposition"):
            with self.assertRaises(ValidationError):
                parse_headers({"Content_Disposition": "not inline"}, {"version": "v2"})

        with self.subTest("v2"):
            assert parse_headers(
                {"Content-Disposition": "inline"}, {"version": "v2"}
            ) == {"content_type": "application/x-gzip", "reduced_redundancy": False}

        with self.subTest("v4"):
            assert parse_headers(
                {"X_Content_Type": "text/html", "X_Reduced_Redundancy": "false"},
                {"version": "v4"},
            ) == {"content_type": "text/plain", "reduced_redundancy": False}

            assert parse_headers(
                {"X_Content_Type": "plain/text", "X_Reduced_Redundancy": "true"},
                {"version": "v4"},
            ) == {"content_type": "plain/text", "reduced_redundancy": True}

            assert parse_headers(
                {
                    "X_Content_Type": "application/x-gzip",
                    "X_Reduced_Redundancy": "true",
                },
                {"version": "v4", "package": "node"},
            ) == {"content_type": "application/x-gzip", "reduced_redundancy": False}

        with self.subTest("Unsafe content type"):
            assert parse_headers(
                {
                    "Content_Disposition": None,
                    "X_Content_Type": "multipart/form-data",
                },
                {"version": "v4"},
            ) == {"content_type": "text/plain", "reduced_redundancy": True}

    def test_store_report_in_redis(self):
        redis = MockRedis()

        with self.subTest("gzip encoding"):
            assert (
                store_report_in_redis(
                    APIRequestFactory().get("", HTTP_X_CONTENT_ENCODING="gzip"),
                    "1c78206f1a46dc6db8412a491fc770eb7d0f8a47",
                    "report",
                    redis,
                )
                == "upload/1c78206/report/gzip"
            )

        with self.subTest("plain encoding"):
            assert (
                store_report_in_redis(
                    APIRequestFactory().get(""),
                    "1c78206f1a46dc6db8412a491fc770eb7d0f8a47",
                    "report",
                    redis,
                )
                == "upload/1c78206/report/plain"
            )

    def test_validate_upload_repository_moved(self):
        redis = MockRedis()
        owner = G(Owner, plan="users-free")
        repo = G(Repository, author=owner, name="")
        commit = G(Commit)

        with self.assertRaises(ValidationError) as err:
            validate_upload({"commit": commit.commitid}, repo, redis)

        assert (
            err.exception.detail[0]
            == "This repository has moved or was deleted. Please login to Codecov to retrieve a new upload token."
        )

    def test_validate_upload_empty_totals(self):
        redis = MockRedis()
        owner = G(Owner, plan="5m")
        repo = G(Repository, author=owner)
        commit = G(Commit, totals=None, repository=repo)

        validate_upload({"commit": commit.commitid}, repo, redis)
        repo.refresh_from_db()
        assert repo.activated == True
        assert repo.active == True
        assert repo.deleted == False

    def test_validate_upload_too_many_uploads_for_commit(self):
        redis = MockRedis()
        owner = G(Owner, plan="users-free")
        repo = G(Repository, author=owner)
        commit = G(Commit, totals={"s": 151}, repository=repo)
        report = CommitReportFactory.create(commit=commit)
        for i in range(151):
            UploadFactory.create(report=report)

        with self.assertRaises(ValidationError) as err:
            validate_upload({"commit": commit.commitid}, repo, redis)
        assert err.exception.detail[0] == "Too many uploads to this commit."

    def test_validate_upload_repository_blacklisted(self):
        redis = MockRedis(blacklisted=True)
        owner = G(Owner, plan="users-free")
        repo = G(Repository, author=owner)
        commit = G(Commit)

        with self.assertRaises(ValidationError) as err:
            validate_upload({"commit": commit.commitid}, repo, redis)
        assert (
            err.exception.detail[0]
            == "Uploads rejected for this project. Please contact Codecov staff for more details. Sorry for the inconvenience."
        )

    def test_validate_upload_per_repo_billing_invalid(self):
        redis = MockRedis()
        owner = G(Owner, plan="1m")
        repo_already_activated = G(
            Repository, author=owner, private=True, activated=True, active=True
        )
        repo = G(Repository, author=owner, private=True, activated=False, active=False)
        commit = G(Commit)

        with self.assertRaises(ValidationError) as err:
            validate_upload({"commit": commit.commitid}, repo, redis)
        assert (
            err.exception.detail[0]
            == "Sorry, but this team has no private repository credits left."
        )

    def test_validate_upload_gitlab_subgroups(self):
        redis = MockRedis()
        parent_group = G(Owner, plan="1m", parent_service_id=None, service="gitlab")
        top_subgroup = G(
            Owner,
            plan="1m",
            parent_service_id=parent_group.service_id,
            service="gitlab",
        )
        bottom_subgroup = G(
            Owner,
            plan="1m",
            parent_service_id=top_subgroup.service_id,
            service="gitlab",
        )
        repo_already_activated = G(
            Repository, author=parent_group, private=True, activated=True, active=True
        )
        repo = G(Repository, author=bottom_subgroup, private=True, activated=False)
        commit = G(Commit)

        with self.assertRaises(ValidationError) as err:
            validate_upload({"commit": commit.commitid}, repo, redis)
        assert (
            err.exception.detail[0]
            == "Sorry, but this team has no private repository credits left."
        )

    def test_validate_upload_valid_upload_repo_not_activated(self):
        redis = MockRedis()
        owner = G(Owner, plan="users-free")
        repo = G(
            Repository,
            author=owner,
            private=True,
            activated=False,
            deleted=False,
            active=False,
        )
        commit = G(Commit)

        with patch(
            "services.segment.SegmentService.account_activated_repository_on_upload"
        ) as mock_segment_event:
            validate_upload({"commit": commit.commitid}, repo, redis)
            assert mock_segment_event.called

        repo.refresh_from_db()
        assert repo.activated == True
        assert repo.active == True
        assert repo.deleted == False

    def test_validate_upload_valid_upload_repo_activated(self):
        redis = MockRedis()
        owner = G(Owner, plan="5m")
        repo = G(Repository, author=owner, private=True, activated=True)
        commit = G(Commit)

        with patch(
            "services.segment.SegmentService.account_activated_repository_on_upload"
        ) as mock_segment_event:
            validate_upload({"commit": commit.commitid}, repo, redis)
            assert not mock_segment_event.called

        repo.refresh_from_db()
        assert repo.activated == True
        assert repo.active == True
        assert repo.deleted == False

    @patch("services.task.TaskService.upload")
    def test_dispatch_upload_task(self, mock_task_service_upload):
        repo = G(Repository)
        task_arguments = {
            "commit": "commit123",
            "version": "v4",
            "report_code": "local_report",
        }

        expected_key = f"uploads/{repo.repoid}/commit123"

        redis = MockRedis(
            expected_task_key=expected_key,
            expected_task_arguments=task_arguments,
            expected_expire_time=86400,
        )

        dispatch_upload_task(task_arguments, repo, redis)
        assert mock_task_service_upload.called
        mock_task_service_upload.assert_called_with(
            repoid=repo.repoid,
            commitid=task_arguments.get("commit"),
            report_code="local_report",
            countdown=4,
        )


class UploadHandlerRouteTest(APITestCase):
    # Wrap client calls
    def _get(self, kwargs=None):
        return self.client.get(reverse("upload-handler", kwargs=kwargs))

    def _options(self, kwargs=None, data=None):
        return self.client.options(reverse("upload-handler", kwargs=kwargs))

    def _post(
        self,
        kwargs=None,
        data=None,
        query=None,
        content_type="application/json",
        headers=None,
    ):
        headers = headers or {}
        query_string = f"?{urlencode(query)}" if query else ""
        url = reverse("upload-handler", kwargs=kwargs) + query_string
        return self.client.post(url, data=data, content_type=content_type, **headers)

    def _post_slash(
        self,
        kwargs=None,
        data=None,
        query=None,
        content_type="application/json",
        headers=None,
    ):
        headers = headers or {}
        query_string = f"?{urlencode(query)}" if query else ""
        url = "/upload/v2/" + query_string
        return self.client.post(url, data=data, content_type=content_type, **headers)

    def setUp(self):
        self.org = G(Owner, username="codecovtest", service="github")
        self.repo = G(
            Repository,
            author=self.org,
            name="upload-test-repo",
            upload_token="a03e5d02-9495-4413-b0d8-05651bb2e842",
        )

    def test_get_request_returns_405(self):
        response = self._get(kwargs={"version": "v4"})

        assert response.status_code == status.HTTP_405_METHOD_NOT_ALLOWED

    # Test headers
    def test_options_headers(self):
        response = self._options(kwargs={"version": "v2"})

        headers = response.headers

        assert headers["accept"] == "text/*"
        assert headers["access-control-allow-origin"] == "*"
        assert headers["access-control-allow-method"] == "POST"
        assert (
            headers["access-control-allow-headers"]
            == "Origin, Content-Type, Accept, X-User-Agent"
        )

    @patch("shared.metrics.metrics.incr")
    def test_invalid_request_params(self, mock_metrics):
        query_params = {"pr": 9838, "flags": "flags!!!", "package": "codecov-cli/0.0.0"}

        response = self._post(kwargs={"version": "v5"}, query=query_params)

        assert response.status_code == status.HTTP_400_BAD_REQUEST
        mock_metrics.assert_has_calls(
            [call("upload.cli.0.0.0"), call("uploads.rejected", 1)]
        )

    @patch("shared.metrics.metrics.incr")
    def test_invalid_request_params_uploader_package(self, mock_metrics):
        query_params = {"pr": 9838, "flags": "flags!!!", "package": "uploader-0.0.0"}

        response = self._post(kwargs={"version": "v5"}, query=query_params)

        assert response.status_code == status.HTTP_400_BAD_REQUEST
        mock_metrics.assert_has_calls(
            [call("upload.uploader.0.0.0"), call("uploads.rejected", 1)]
        )

    @patch("shared.metrics.metrics.incr")
    def test_invalid_request_params_invalid_package(self, mock_metrics):
        query_params = {"pr": 9838, "flags": "flags!!!", "package": ""}

        response = self._post(kwargs={"version": "v5"}, query=query_params)

        assert response.status_code == status.HTTP_400_BAD_REQUEST
        mock_metrics.assert_has_calls([call("uploads.rejected", 1)])

    @patch("shared.metrics.metrics.incr")
    @patch("upload.views.legacy.get_redis_connection")
    @patch("upload.views.legacy.uuid4")
    @patch("upload.views.legacy.dispatch_upload_task")
    @patch("services.repo_providers.RepoProviderService.get_adapter")
    @override_settings(CODECOV_DASHBOARD_URL="https://app.codecov.io")
    def test_successful_upload_v2(
        self,
        mock_repo_provider_service,
        mock_dispatch_upload,
        mock_uuid4,
        mock_get_redis,
        mock_metrics,
    ):
        class MockRepoProviderAdapter:
            async def get_commit(self, commit, token):
                return {"message": "This is not a merge commit"}

        mock_get_redis.return_value = MockRedis()
        mock_repo_provider_service.return_value = MockRepoProviderAdapter()
        mock_uuid4.return_value = (
            "dec1f00b-1883-40d0-afd6-6dcb876510be"  # this will be the reportid
        )

        query_params = {
            "commit": "b521e55aef79b101f48e2544837ca99a7fa3bf6b",
            "token": "a03e5d02-9495-4413-b0d8-05651bb2e842",
            "pr": "456",
            "branch": "",
            "flags": "",
            "build_url": "",
            "package": "",
        }

        response = self._post(
            kwargs={"version": "v2"}, query=query_params, data="coverage report"
        )

        assert response.status_code == 200
        mock_metrics.assert_called_once_with("uploads.accepted", 1)

        headers = response.headers

        assert headers["access-control-allow-origin"] == "*"
        assert (
            headers["access-control-allow-headers"]
            == "Origin, Content-Type, Accept, X-User-Agent"
        )
        assert headers["content-type"] != "text/plain"

        assert mock_dispatch_upload.call_args[0][0] == {
            "commit": "b521e55aef79b101f48e2544837ca99a7fa3bf6b",
            "token": "a03e5d02-9495-4413-b0d8-05651bb2e842",
            "pr": "456",
            "version": "v2",
            "service": None,
            "owner": None,
            "repo": None,
            "using_global_token": False,
            "build_url": None,
            "branch": None,
            "reportid": "dec1f00b-1883-40d0-afd6-6dcb876510be",
            "redis_key": "upload/b521e55/dec1f00b-1883-40d0-afd6-6dcb876510be/plain",
            "url": None,
            "branch": None,
            "job": None,
        }

        result = loads(response.content)
        assert result["message"] == "Coverage reports upload successfully"
        assert result["uploaded"] == True
        assert result["queued"] == True
        assert result["id"] == "dec1f00b-1883-40d0-afd6-6dcb876510be"
        assert (
            result["url"]
            == "https://app.codecov.io/github/codecovtest/upload-test-repo/commit/b521e55aef79b101f48e2544837ca99a7fa3bf6b"
        )

    @patch("shared.metrics.metrics.incr")
    @patch("upload.views.legacy.get_redis_connection")
    @patch("upload.views.legacy.uuid4")
    @patch("upload.views.legacy.dispatch_upload_task")
    @patch("services.repo_providers.RepoProviderService.get_adapter")
    @override_settings(CODECOV_DASHBOARD_URL="https://app.codecov.io")
    def test_successful_upload_v2_slash(
        self,
        mock_repo_provider_service,
        mock_dispatch_upload,
        mock_uuid4,
        mock_get_redis,
        mock_metrics,
    ):
        class MockRepoProviderAdapter:
            async def get_commit(self, commit, token):
                return {"message": "This is not a merge commit"}

        mock_get_redis.return_value = MockRedis()
        mock_repo_provider_service.return_value = MockRepoProviderAdapter()
        mock_uuid4.return_value = (
            "dec1f00b-1883-40d0-afd6-6dcb876510be"  # this will be the reportid
        )

        query_params = {
            "commit": "b521e55aef79b101f48e2544837ca99a7fa3bf6b",
            "token": "a03e5d02-9495-4413-b0d8-05651bb2e842",
            "pr": "456",
            "branch": "",
            "flags": "",
            "build_url": "",
            "package": "",
        }

        response = self._post_slash(
            kwargs={"version": "v2"}, query=query_params, data="coverage report"
        )

        assert response.status_code == 200
        mock_metrics.assert_called_once_with("uploads.accepted", 1)

        headers = response.headers

        assert headers["access-control-allow-origin"] == "*"
        assert (
            headers["access-control-allow-headers"]
            == "Origin, Content-Type, Accept, X-User-Agent"
        )
        assert headers["content-type"] != "text/plain"

        assert mock_dispatch_upload.call_args[0][0] == {
            "commit": "b521e55aef79b101f48e2544837ca99a7fa3bf6b",
            "token": "a03e5d02-9495-4413-b0d8-05651bb2e842",
            "pr": "456",
            "version": "v2",
            "service": None,
            "owner": None,
            "repo": None,
            "using_global_token": False,
            "build_url": None,
            "branch": None,
            "reportid": "dec1f00b-1883-40d0-afd6-6dcb876510be",
            "redis_key": "upload/b521e55/dec1f00b-1883-40d0-afd6-6dcb876510be/plain",
            "url": None,
            "branch": None,
            "job": None,
        }

        result = loads(response.content)
        assert result["message"] == "Coverage reports upload successfully"
        assert result["uploaded"] == True
        assert result["queued"] == True
        assert result["id"] == "dec1f00b-1883-40d0-afd6-6dcb876510be"
        assert (
            result["url"]
            == "https://app.codecov.io/github/codecovtest/upload-test-repo/commit/b521e55aef79b101f48e2544837ca99a7fa3bf6b"
        )

    @patch("shared.metrics.metrics.incr")
    @patch("upload.views.legacy.get_redis_connection")
    @patch("upload.views.legacy.uuid4")
    @patch("upload.views.legacy.determine_repo_for_upload")
    @patch("services.repo_providers.RepoProviderService.get_adapter")
    @override_settings(CODECOV_DASHBOARD_URL="https://app.codecov.io")
    def test_repo_validation_error_v2(
        self,
        mock_repo_provider_service,
        mock_determine_repo_for_upload,
        mock_uuid4,
        mock_get_redis,
        mock_metrics,
    ):
        class MockRepoProviderAdapter:
            async def get_commit(self, commit, token):
                return {"message": "This is not a merge commit"}

        mock_get_redis.return_value = MockRedis()
        mock_repo_provider_service.return_value = MockRepoProviderAdapter()
        mock_uuid4.return_value = (
            "dec1f00b-1883-40d0-afd6-6dcb876510be"  # this will be the reportid
        )
        mock_determine_repo_for_upload.side_effect = ValidationError(
            "Unable to determine repo and owner"
        )

        query_params = {
            "commit": "b521e55aef79b101f48e2544837ca99a7fa3bf6b",
            "token": "a03e5d02-9495-4413-b0d8-05651bb2e842",
            "pr": "456",
            "branch": "",
            "flags": "",
            "build_url": "",
            "package": "",
        }

        response = self._post_slash(
            kwargs={"version": "v2"}, query=query_params, data="coverage report"
        )

        assert response.status_code == 400
        mock_metrics.assert_called_once_with("uploads.rejected", 1)

        headers = response.headers

        assert headers["access-control-allow-origin"] == "*"
        assert (
            headers["access-control-allow-headers"]
            == "Origin, Content-Type, Accept, X-User-Agent"
        )
        assert headers["content-type"] != "text/plain"

        assert response.content == b"Could not determine repo and owner"

    @patch("shared.metrics.metrics.incr")
    @patch("upload.views.legacy.get_redis_connection")
    @patch("upload.views.legacy.uuid4")
    @patch("upload.views.legacy.determine_repo_for_upload")
    @patch("services.repo_providers.RepoProviderService.get_adapter")
    @override_settings(CODECOV_DASHBOARD_URL="https://app.codecov.io")
    def test_too_many_repos_found_v2(
        self,
        mock_repo_provider_service,
        mock_determine_repo_for_upload,
        mock_uuid4,
        mock_get_redis,
        mock_metrics,
    ):
        class MockRepoProviderAdapter:
            async def get_commit(self, commit, token):
                return {"message": "This is not a merge commit"}

        mock_get_redis.return_value = MockRedis()
        mock_repo_provider_service.return_value = MockRepoProviderAdapter()
        mock_uuid4.return_value = (
            "dec1f00b-1883-40d0-afd6-6dcb876510be"  # this will be the reportid
        )
        mock_determine_repo_for_upload.side_effect = MultipleObjectsReturned(
            "Found too many repos"
        )

        query_params = {
            "commit": "b521e55aef79b101f48e2544837ca99a7fa3bf6b",
            "token": "a03e5d02-9495-4413-b0d8-05651bb2e842",
            "pr": "456",
            "branch": "",
            "flags": "",
            "build_url": "",
            "package": "",
        }

        response = self._post_slash(
            kwargs={"version": "v2"}, query=query_params, data="coverage report"
        )

        assert response.status_code == 400
        mock_metrics.assert_called_once_with("uploads.rejected", 1)

        headers = response.headers

        assert headers["access-control-allow-origin"] == "*"
        assert (
            headers["access-control-allow-headers"]
            == "Origin, Content-Type, Accept, X-User-Agent"
        )
        assert headers["content-type"] != "text/plain"

        assert response.content == b"Found too many repos"

    @patch("services.storage.MINIO_CLIENT.presigned_put_object")
    @patch("services.archive.ArchiveService.get_archive_hash")
    @patch("upload.views.legacy.get_redis_connection")
    @patch("upload.views.legacy.uuid4")
    @patch("upload.views.legacy.dispatch_upload_task")
    @patch("services.repo_providers.RepoProviderService.get_adapter")
    def test_upload_v4(
        self,
        mock_repo_provider_service,
        mock_dispatch_upload,
        mock_uuid4,
        mock_get_redis,
        mock_hash,
        mock_storage_put,
    ):
        class MockRepoProviderAdapter:
            async def get_commit(self, commit, token):
                return {"message": "This is not a merge commit"}

        path = "/".join(
            (
                "v4/raw",
                timezone.now().strftime("%Y-%m-%d"),
                "awawaw",
                "b521e55aef79b101f48e2544837ca99a7fa3bf6b",
            )
        )

        mock_storage_put.return_value = path + "?AWS=PARAMS"
        mock_get_redis.return_value = MockRedis()
        mock_repo_provider_service.return_value = MockRepoProviderAdapter()
        mock_uuid4.return_value = (
            "dec1f00b-1883-40d0-afd6-6dcb876510be"  # this will be the reportid
        )
        mock_hash.return_value = "awawaw"
        query_params = {
            "commit": "b521e55aef79b101f48e2544837ca99a7fa3bf6b",
            "token": "a03e5d02-9495-4413-b0d8-05651bb2e842",
            "pr": "456",
            "branch": "",
            "flags": "",
            "build_url": "",
            "package": "",
        }

        response = self._post(
            kwargs={"version": "v4"}, query=query_params, data="coverage report"
        )

        assert response.status_code == 200

    @patch("services.storage.MINIO_CLIENT.presigned_put_object")
    @patch("services.archive.ArchiveService.get_archive_hash")
    @patch("upload.views.legacy.get_redis_connection")
    @patch("upload.views.legacy.uuid4")
    @patch("upload.views.legacy.dispatch_upload_task")
    @patch("services.repo_providers.RepoProviderService.get_adapter")
    def test_upload_v4_with_upload_token_header(
        self,
        mock_repo_provider_service,
        mock_dispatch_upload,
        mock_uuid4,
        mock_get_redis,
        mock_hash,
        mock_storage_put,
    ):
        class MockRepoProviderAdapter:
            async def get_commit(self, commit, token):
                return {"message": "This is not a merge commit"}

        path = "/".join(
            (
                "v4/raw",
                timezone.now().strftime("%Y-%m-%d"),
                "awawaw",
                "b521e55aef79b101f48e2544837ca99a7fa3bf6b",
            )
        )

        mock_storage_put.return_value = path + "?AWS=PARAMS"
        mock_get_redis.return_value = MockRedis()
        mock_repo_provider_service.return_value = MockRepoProviderAdapter()
        mock_uuid4.return_value = (
            "dec1f00b-1883-40d0-afd6-6dcb876510be"  # this will be the reportid
        )
        mock_hash.return_value = "awawaw"
        query_params = {
            "commit": "b521e55aef79b101f48e2544837ca99a7fa3bf6b",
            "pr": "456",
            "branch": "",
            "flags": "",
            "build_url": "",
            "package": "",
        }

        response = self._post(
            kwargs={"version": "v4"},
            query=query_params,
            data="coverage report",
            headers={"HTTP_X_UPLOAD_TOKEN": "a03e5d02-9495-4413-b0d8-05651bb2e842"},
        )

        assert response.status_code == 200

    @patch("services.storage.MINIO_CLIENT.presigned_put_object")
    @patch("services.archive.ArchiveService.get_archive_hash")
    @patch("upload.views.legacy.get_redis_connection")
    @patch("upload.views.legacy.uuid4")
    @patch("upload.views.legacy.dispatch_upload_task")
    @patch("services.repo_providers.RepoProviderService.get_adapter")
    @patch("upload.views.legacy.determine_repo_for_upload")
    def test_repo_validation_error_v4(
        self,
        mock_determine_repo_for_upload,
        mock_repo_provider_service,
        mock_dispatch_upload,
        mock_uuid4,
        mock_get_redis,
        mock_hash,
        mock_storage_put,
    ):
        mock_determine_repo_for_upload.side_effect = ValidationError(
            "Unable to determine repo and owner"
        )

        class MockRepoProviderAdapter:
            async def get_commit(self, commit, token):
                return {"message": "This is not a merge commit"}

        path = "/".join(
            (
                "v4/raw",
                timezone.now().strftime("%Y-%m-%d"),
                "awawaw",
                "b521e55aef79b101f48e2544837ca99a7fa3bf6b",
            )
        )

        mock_storage_put.return_value = path + "?AWS=PARAMS"
        mock_get_redis.return_value = MockRedis()
        mock_repo_provider_service.return_value = MockRepoProviderAdapter()
        mock_uuid4.return_value = (
            "dec1f00b-1883-40d0-afd6-6dcb876510be"  # this will be the reportid
        )
        mock_hash.return_value = "awawaw"
        query_params = {
            "commit": "b521e55aef79b101f48e2544837ca99a7fa3bf6b",
            "token": "a03e5d02-9495-4413-b0d8-05651bb2e842",
            "pr": "456",
            "branch": "",
            "flags": "",
            "build_url": "",
            "package": "",
        }

        response = self._post(
            kwargs={"version": "v4"}, query=query_params, data="coverage report"
        )

        assert response.status_code == 400

        headers = response.headers

        assert headers["access-control-allow-origin"] == "*"
        assert (
            headers["access-control-allow-headers"]
            == "Origin, Content-Type, Accept, X-User-Agent"
        )
        assert headers["content-type"] != "text/plain"

        assert response.content == b"Could not determine repo and owner"

    @patch("services.storage.MINIO_CLIENT.presigned_put_object")
    @patch("services.archive.ArchiveService.get_archive_hash")
    @patch("upload.views.legacy.get_redis_connection")
    @patch("upload.views.legacy.uuid4")
    @patch("upload.views.legacy.dispatch_upload_task")
    @patch("services.repo_providers.RepoProviderService.get_adapter")
    @patch("upload.views.legacy.determine_repo_for_upload")
    def test_too_many_repos_found_v4(
        self,
        mock_determine_repo_for_upload,
        mock_repo_provider_service,
        mock_dispatch_upload,
        mock_uuid4,
        mock_get_redis,
        mock_hash,
        mock_storage_put,
    ):
        mock_determine_repo_for_upload.side_effect = MultipleObjectsReturned(
            "Found too many repos"
        )

        class MockRepoProviderAdapter:
            async def get_commit(self, commit, token):
                return {"message": "This is not a merge commit"}

        path = "/".join(
            (
                "v4/raw",
                timezone.now().strftime("%Y-%m-%d"),
                "awawaw",
                "b521e55aef79b101f48e2544837ca99a7fa3bf6b",
            )
        )

        mock_storage_put.return_value = path + "?AWS=PARAMS"
        mock_get_redis.return_value = MockRedis()
        mock_repo_provider_service.return_value = MockRepoProviderAdapter()
        mock_uuid4.return_value = (
            "dec1f00b-1883-40d0-afd6-6dcb876510be"  # this will be the reportid
        )
        mock_hash.return_value = "awawaw"
        query_params = {
            "commit": "b521e55aef79b101f48e2544837ca99a7fa3bf6b",
            "token": "a03e5d02-9495-4413-b0d8-05651bb2e842",
            "pr": "456",
            "branch": "",
            "flags": "",
            "build_url": "",
            "package": "",
        }

        response = self._post(
            kwargs={"version": "v4"}, query=query_params, data="coverage report"
        )

        assert response.status_code == 400

        headers = response.headers

        assert headers["access-control-allow-origin"] == "*"
        assert (
            headers["access-control-allow-headers"]
            == "Origin, Content-Type, Accept, X-User-Agent"
        )
        assert headers["content-type"] != "text/plain"

        assert response.content == b"Found too many repos"


class UploadHandlerTravisTokenlessTest(TestCase):
    @patch.object(requests, "get")
    def test_travis_no_slug_match(self, mock_get):
        expected_response = {
            "id": 732059764,
            "allow_failure": None,
            "number": "498.1",
            "state": "passed",
            "started_at": "2020-10-01T20:01:31Z",
            "finished_at": "2020-10-01T20:02:55Z",
            "build": {
                "@type": "build",
                "@href": "/build/732059763",
                "@representation": "minimal",
                "id": 732059763,
                "number": "498",
                "state": "passed",
                "duration": 84,
                "event_type": "push",
                "previous_state": "passed",
                "pull_request_title": None,
                "pull_request_number": None,
                "started_at": "2020-10-01T20:01:31Z",
                "finished_at": "2020-10-01T20:02:55Z",
                "private": False,
                "priority": False,
            },
            "queue": "builds.gce",
            "repository": {
                "@type": "repository",
                "@href": "/repo/25205338",
                "@representation": "minimal",
                "id": 25205338,
                "name": "python-standard",
                "slug": "codecov/python-standard",
            },
            "commit": {
                "@type": "commit",
                "@representation": "minimal",
                "id": 226208830,
                "sha": "2485b28f9862e98bcee576f02d8b37e6433f8c30",
                "ref": "refs/heads/master",
                "message": "New Build: 10/01/20 20:00:54",
                "compare_url": "https://github.com/codecov/python-standard/compare/28392734979c...2485b28f9862",
                "committed_at": "2020-10-01T20:00:55Z",
            },
        }
        mock_get.return_value.status_code.return_value = 200
        mock_get.return_value.json.return_value = expected_response

        params = {
            "version": "v4",
            "commit": "3be5c52bd748c508a7e96993c02cf3518c816e84",
            "slug": "codecov/codecov-api",
            "owner": "codecov",
            "repo": "codecov-api",
            "token": "4a24929b-9276-4784-8e85-a7a008a32037",
            "service": "circleci",
            "pr": None,
            "pull_request": None,
            "flags": "this-is-a-flag,this-is-another-flag",
            "param_doesn't_exist_but_still_should_not_error": True,
            "s3": 123,
            "build_url": "https://thisisabuildurl.com",
            "job": 732059764,
            "using_global_token": False,
            "branch": None,
            "_did_change_merge_commit": False,
            "parent": "123abc",
        }

        expected_error = """
        ERROR: Tokenless uploads are only supported for public repositories on Travis that can be verified through the Travis API. Please use an upload token if your repository is private and specify it via the -t flag. You can find the token for this repository at the url below on codecov.io (login required):

        Repo token: https://codecov.io/gh/codecov/codecov-api/settings
        Documentation: https://docs.codecov.io/docs/about-the-codecov-bash-uploader#section-upload-token"""

        with pytest.raises(NotFound) as e:
            TokenlessUploadHandler("travis", params).verify_upload()
        assert [line.strip() for line in e.value.args[0].split("\n")] == [
            line.strip() for line in expected_error.split("\n")
        ]

        with pytest.raises(NotFound) as e:
            TokenlessUploadHandler("something", params).verify_upload()

    @patch.object(requests, "get")
    def test_travis_no_sha_match(self, mock_get):
        expected_response = {
            "id": 732059764,
            "allow_failure": None,
            "number": "498.1",
            "state": "passed",
            "started_at": "2020-10-01T20:01:31Z",
            "finished_at": "2020-10-01T20:02:55Z",
            "build": {
                "@type": "build",
                "@href": "/build/732059763",
                "@representation": "minimal",
                "id": 732059763,
                "number": "498",
                "state": "passed",
                "duration": 84,
                "event_type": "push",
                "previous_state": "passed",
                "pull_request_title": None,
                "pull_request_number": None,
                "started_at": "2020-10-01T20:01:31Z",
                "finished_at": "2020-10-01T20:02:55Z",
                "private": False,
                "priority": False,
            },
            "queue": "builds.gce",
            "repository": {
                "@type": "repository",
                "@href": "/repo/25205338",
                "@representation": "minimal",
                "id": 25205338,
                "name": "python-standard",
                "slug": "codecov/codecov-api",
            },
            "commit": {
                "@type": "commit",
                "@representation": "minimal",
                "id": 226208830,
                "sha": "2485b28f9862e98bcee576f02d8b37e6433f8c30",
                "ref": "refs/heads/master",
                "message": "New Build: 10/01/20 20:00:54",
                "compare_url": "https://github.com/codecov/python-standard/compare/28392734979c...2485b28f9862",
                "committed_at": "2020-10-01T20:00:55Z",
            },
        }
        mock_get.return_value.status_code.return_value = 200
        mock_get.return_value.json.return_value = expected_response

        params = {
            "version": "v4",
            "commit": "3be5c52bd748c508a7e96993c02cf3518c816e84",
            "slug": "codecov/codecov-api",
            "owner": "codecov",
            "repo": "codecov-api",
            "token": "4a24929b-9276-4784-8e85-a7a008a32037",
            "service": "circleci",
            "pr": None,
            "pull_request": None,
            "flags": "this-is-a-flag,this-is-another-flag",
            "param_doesn't_exist_but_still_should_not_error": True,
            "s3": 123,
            "build_url": "https://thisisabuildurl.com",
            "job": 732059764,
            "using_global_token": False,
            "branch": None,
            "_did_change_merge_commit": False,
            "parent": "123abc",
        }

        expected_error = """
        ERROR: Tokenless uploads are only supported for public repositories on Travis that can be verified through the Travis API. Please use an upload token if your repository is private and specify it via the -t flag. You can find the token for this repository at the url below on codecov.io (login required):

        Repo token: https://codecov.io/gh/codecov/codecov-api/settings
        Documentation: https://docs.codecov.io/docs/about-the-codecov-bash-uploader#section-upload-token"""

        with pytest.raises(NotFound) as e:
            TokenlessUploadHandler("travis", params).verify_upload()
        assert [line.strip() for line in e.value.args[0].split("\n")] == [
            line.strip() for line in expected_error.split("\n")
        ]

    @patch.object(requests, "get")
    def test_travis_no_event_match(self, mock_get):
        expected_response = {
            "id": 732059764,
            "allow_failure": None,
            "number": "498.1",
            "state": "passed",
            "started_at": "2020-10-01T20:01:31Z",
            "finished_at": "2020-10-01T20:02:55Z",
            "build": {
                "@type": "build",
                "@href": "/build/732059763",
                "@representation": "minimal",
                "id": 732059763,
                "number": "498",
                "state": "passed",
                "duration": 84,
                "event_type": "push",
                "previous_state": "passed",
                "pull_request_title": None,
                "pull_request_number": None,
                "started_at": "2020-10-01T20:01:31Z",
                "finished_at": "2020-10-01T20:02:55Z",
                "private": False,
                "priority": False,
            },
            "queue": "builds.gce",
            "repository": {
                "@type": "repository",
                "@href": "/repo/25205338",
                "@representation": "minimal",
                "id": 25205338,
                "name": "python-standard",
                "slug": "codecov/codecov-api",
            },
            "commit": {
                "@type": "commit",
                "@representation": "minimal",
                "id": 226208830,
                "sha": "2485b28f9862e98bcee576f02d8b37e6433f8c30",
                "ref": "refs/heads/master",
                "message": "New Build: 10/01/20 20:00:54",
                "compare_url": "https://github.com/codecov/python-standard/compare/28392734979c...2485b28f9862",
                "committed_at": "2020-10-01T20:00:55Z",
            },
        }
        mock_get.return_value.status_code.return_value = 200
        mock_get.return_value.json.return_value = expected_response

        params = {
            "version": "v4",
            "commit": "3be5c52bd748c508a7e96993c02cf3518c816e84",
            "slug": "codecov/codecov-api",
            "owner": "codecov",
            "repo": "codecov-api",
            "token": "4a24929b-9276-4784-8e85-a7a008a32037",
            "service": "circleci",
            "pr": None,
            "pull_request": None,
            "flags": "this-is-a-flag,this-is-another-flag",
            "param_doesn't_exist_but_still_should_not_error": True,
            "s3": 123,
            "build_url": "https://thisisabuildurl.com",
            "job": 732059764,
            "using_global_token": False,
            "branch": None,
            "_did_change_merge_commit": False,
            "parent": "123abc",
        }

        expected_error = """
        ERROR: Tokenless uploads are only supported for public repositories on Travis that can be verified through the Travis API. Please use an upload token if your repository is private and specify it via the -t flag. You can find the token for this repository at the url below on codecov.io (login required):

        Repo token: https://codecov.io/gh/codecov/codecov-api/settings
        Documentation: https://docs.codecov.io/docs/about-the-codecov-bash-uploader#section-upload-token"""

        with pytest.raises(NotFound) as e:
            TokenlessUploadHandler("travis", params).verify_upload()
        assert [line.strip() for line in e.value.args[0].split("\n")] == [
            line.strip() for line in expected_error.split("\n")
        ]

    @patch.object(requests, "get")
    def test_travis_failed_requests(self, mock_get):
        mock_get.side_effect = [
            requests.exceptions.ConnectionError("Not found"),
            requests.exceptions.ConnectionError("Not found"),
        ]
        params = {
            "version": "v4",
            "commit": "3be5c52bd748c508a7e96993c02cf3518c816e84",
            "slug": "codecov/codecov-api",
            "owner": "codecov",
            "repo": "codecov-api",
            "token": "4a24929b-9276-4784-8e85-a7a008a32037",
            "service": "circleci",
            "pr": None,
            "pull_request": None,
            "flags": "this-is-a-flag,this-is-another-flag",
            "param_doesn't_exist_but_still_should_not_error": True,
            "s3": 123,
            "build_url": "https://thisisabuildurl.com",
            "job": 732059764,
            "using_global_token": False,
            "branch": None,
            "_did_change_merge_commit": False,
            "parent": "123abc",
        }

        expected_error = """
        ERROR: Tokenless uploads are only supported for public repositories on Travis that can be verified through the Travis API. Please use an upload token if your repository is private and specify it via the -t flag. You can find the token for this repository at the url below on codecov.io (login required):

        Repo token: https://codecov.io/gh/codecov/codecov-api/settings
        Documentation: https://docs.codecov.io/docs/about-the-codecov-bash-uploader#section-upload-token"""

        with pytest.raises(NotFound) as e:
            TokenlessUploadHandler("travis", params).verify_upload()
        assert [line.strip() for line in e.value.args[0].split("\n")] == [
            line.strip() for line in expected_error.split("\n")
        ]

    @patch.object(requests, "get")
    def test_travis_failed_requests_connection_error(self, mock_get):
        mock_get.side_effect = [
            requests.exceptions.HTTPError("Not found"),
            requests.exceptions.HTTPError("Not found"),
        ]
        params = {
            "version": "v4",
            "commit": "3be5c52bd748c508a7e96993c02cf3518c816e84",
            "slug": "codecov/codecov-api",
            "owner": "codecov",
            "repo": "codecov-api",
            "token": "4a24929b-9276-4784-8e85-a7a008a32037",
            "service": "circleci",
            "pr": None,
            "pull_request": None,
            "flags": "this-is-a-flag,this-is-another-flag",
            "param_doesn't_exist_but_still_should_not_error": True,
            "s3": 123,
            "build_url": "https://thisisabuildurl.com",
            "job": 732059764,
            "using_global_token": False,
            "branch": None,
            "_did_change_merge_commit": False,
            "parent": "123abc",
        }

        expected_error = """
        ERROR: Tokenless uploads are only supported for public repositories on Travis that can be verified through the Travis API. Please use an upload token if your repository is private and specify it via the -t flag. You can find the token for this repository at the url below on codecov.io (login required):

        Repo token: https://codecov.io/gh/codecov/codecov-api/settings
        Documentation: https://docs.codecov.io/docs/about-the-codecov-bash-uploader#section-upload-token"""

        with pytest.raises(NotFound) as e:
            TokenlessUploadHandler("travis", params).verify_upload()
        assert [line.strip() for line in e.value.args[0].split("\n")] == [
            line.strip() for line in expected_error.split("\n")
        ]

    @patch.object(requests, "get")
    def test_travis_failed_requests_connection_error(self, mock_get):
        mock_get.side_effect = [
            Exception("Not found"),
            requests.exceptions.HTTPError("Not found"),
        ]
        params = {
            "version": "v4",
            "commit": "3be5c52bd748c508a7e96993c02cf3518c816e84",
            "slug": "codecov/codecov-api",
            "owner": "codecov",
            "repo": "codecov-api",
            "token": "4a24929b-9276-4784-8e85-a7a008a32037",
            "service": "circleci",
            "pr": None,
            "pull_request": None,
            "flags": "this-is-a-flag,this-is-another-flag",
            "param_doesn't_exist_but_still_should_not_error": True,
            "s3": 123,
            "build_url": "https://thisisabuildurl.com",
            "job": 732059764,
            "using_global_token": False,
            "branch": None,
            "_did_change_merge_commit": False,
            "parent": "123abc",
        }

        expected_error = """
        ERROR: Tokenless uploads are only supported for public repositories on Travis that can be verified through the Travis API. Please use an upload token if your repository is private and specify it via the -t flag. You can find the token for this repository at the url below on codecov.io (login required):

        Repo token: https://codecov.io/gh/codecov/codecov-api/settings
        Documentation: https://docs.codecov.io/docs/about-the-codecov-bash-uploader#section-upload-token"""

        with pytest.raises(NotFound) as e:
            TokenlessUploadHandler("travis", params).verify_upload()
        assert [line.strip() for line in e.value.args[0].split("\n")] == [
            line.strip() for line in expected_error.split("\n")
        ]

    @patch.object(requests, "get")
    def test_build_not_in_progress(self, mock_get):
        expected_response = {
            "id": 732059764,
            "allow_failure": None,
            "number": "498.1",
            "state": "passed",
            "started_at": "2020-10-01T20:01:31Z",
            "finished_at": None,
            "build": {
                "@type": "build",
                "@href": "/build/732059763",
                "@representation": "minimal",
                "id": 732059763,
                "number": "498",
                "state": "passed",
                "duration": 84,
                "event_type": "push",
                "previous_state": "passed",
                "pull_request_title": None,
                "pull_request_number": None,
                "started_at": "2020-10-01T20:01:31Z",
                "finished_at": "2020-10-01T20:02:55Z",
                "private": False,
                "priority": False,
            },
            "queue": "builds.gce",
            "repository": {
                "@type": "repository",
                "@href": "/repo/25205338",
                "@representation": "minimal",
                "id": 25205338,
                "name": "python-standard",
                "slug": "codecov/codecov-api",
            },
            "commit": {
                "@type": "commit",
                "@representation": "minimal",
                "id": 226208830,
                "sha": "3be5c52bd748c508a7e96993c02cf3518c816e84",
                "ref": "refs/heads/master",
                "message": "New Build: 10/01/20 20:00:54",
                "compare_url": "https://github.com/codecov/python-standard/compare/28392734979c...2485b28f9862",
                "committed_at": "2020-10-01T20:00:55Z",
            },
        }
        mock_get.return_value.status_code.return_value = 200
        mock_get.return_value.json.return_value = expected_response

        params = {
            "version": "v4",
            "commit": "3be5c52bd748c508a7e96993c02cf3518c816e84",
            "slug": "codecov/codecov-api",
            "owner": "codecov",
            "repo": "codecov-api",
            "token": "4a24929b-9276-4784-8e85-a7a008a32037",
            "service": "circleci",
            "pr": None,
            "pull_request": None,
            "flags": "this-is-a-flag,this-is-another-flag",
            "param_doesn't_exist_but_still_should_not_error": True,
            "s3": 123,
            "build_url": "https://thisisabuildurl.com",
            "job": 732059764,
            "using_global_token": False,
            "branch": None,
            "_did_change_merge_commit": False,
            "parent": "123abc",
        }

        expected_error = """
            ERROR: The build status does not indicate that the current build is in progress. Please make sure the build is in progress or was finished within the past 4 minutes to ensure reports upload properly."""

        with pytest.raises(NotFound) as e:
            TokenlessUploadHandler("travis", params).verify_upload()
        assert [line.strip() for line in e.value.args[0].split("\n")] == [
            line.strip() for line in expected_error.split("\n")
        ]

    @patch.object(requests, "get")
    def test_travis_no_job(self, mock_get):
        mock_get.side_effect = [requests.exceptions.HTTPError("Not found"), None]
        params = {
            "version": "v4",
            "commit": "3be5c52bd748c508a7e96993c02cf3518c816e84",
            "slug": "codecov/codecov-api",
            "owner": "codecov",
            "repo": "codecov-api",
            "token": "4a24929b-9276-4784-8e85-a7a008a32037",
            "service": "circleci",
            "pr": None,
            "pull_request": None,
            "flags": "this-is-a-flag,this-is-another-flag",
            "param_doesn't_exist_but_still_should_not_error": True,
            "s3": 123,
            "build_url": "https://thisisabuildurl.com",
            "job": 732059764,
            "using_global_token": False,
            "branch": None,
            "_did_change_merge_commit": False,
            "parent": "123abc",
        }

        expected_error = """
        ERROR: Tokenless uploads are only supported for public repositories on Travis that can be verified through the Travis API. Please use an upload token if your repository is private and specify it via the -t flag. You can find the token for this repository at the url below on codecov.io (login required):

        Repo token: https://codecov.io/gh/codecov/codecov-api/settings
        Documentation: https://docs.codecov.io/docs/about-the-codecov-bash-uploader#section-upload-token"""

        with pytest.raises(NotFound) as e:
            TokenlessUploadHandler("travis", params).verify_upload()
        assert [line.strip() for line in e.value.args[0].split("\n")] == [
            line.strip() for line in expected_error.split("\n")
        ]

    @patch.object(requests, "get")
    def test_success(self, mock_get):
        expected_response = {
            "id": 732059764,
            "allow_failure": None,
            "number": "498.1",
            "state": "passed",
            "started_at": "2020-10-01T20:02:55Z",
            "finished_at": f"{datetime.utcnow()}".split(".")[0],
            "build": {
                "@type": "build",
                "@href": "/build/732059763",
                "@representation": "minimal",
                "id": 732059763,
                "number": "498",
                "state": "passed",
                "duration": 84,
                "event_type": "push",
                "previous_state": "passed",
                "pull_request_title": None,
                "pull_request_number": None,
                "started_at": "2020-10-01T20:01:31Z",
                "finished_at": "2020-10-01T20:02:55Z",
                "private": False,
                "priority": False,
            },
            "queue": "builds.gce",
            "repository": {
                "@type": "repository",
                "@href": "/repo/25205338",
                "@representation": "minimal",
                "id": 25205338,
                "name": "python-standard",
                "slug": "codecov/codecov-api",
            },
            "commit": {
                "@type": "commit",
                "@representation": "minimal",
                "id": 226208830,
                "sha": "3be5c52bd748c508a7e96993c02cf3518c816e84",
                "ref": "refs/heads/master",
                "message": "New Build: 10/01/20 20:00:54",
                "compare_url": "https://github.com/codecov/python-standard/compare/28392734979c...2485b28f9862",
                "committed_at": "2020-10-01T20:00:55Z",
            },
        }
        mock_get.return_value.status_code.return_value = 200
        mock_get.return_value.json.return_value = expected_response

        params = {
            "version": "v4",
            "commit": "3be5c52bd748c508a7e96993c02cf3518c816e84",
            "slug": "codecov/codecov-api",
            "owner": "codecov",
            "repo": "codecov-api",
            "token": "4a24929b-9276-4784-8e85-a7a008a32037",
            "service": "circleci",
            "pr": None,
            "pull_request": None,
            "flags": "this-is-a-flag,this-is-another-flag",
            "param_doesn't_exist_but_still_should_not_error": True,
            "s3": 123,
            "build_url": "https://thisisabuildurl.com",
            "job": 732059764,
            "using_global_token": False,
            "branch": None,
            "_did_change_merge_commit": False,
            "parent": "123abc",
        }

        res = TokenlessUploadHandler("travis", params).verify_upload()

        assert res == "github"

    @patch.object(requests, "get")
    def test_expired_build(self, mock_get):
        expected_response = {
            "id": 732059764,
            "allow_failure": None,
            "number": "498.1",
            "state": "passed",
            "started_at": "2020-10-01T20:02:55Z",
            "finished_at": "2020-10-01T20:02:55Z",
            "build": {
                "@type": "build",
                "@href": "/build/732059763",
                "@representation": "minimal",
                "id": 732059763,
                "number": "498",
                "state": "passed",
                "duration": 84,
                "event_type": "push",
                "previous_state": "passed",
                "pull_request_title": None,
                "pull_request_number": None,
                "started_at": "2020-10-01T20:01:31Z",
                "finished_at": "2020-10-01T20:02:55Z",
                "private": False,
                "priority": False,
            },
            "queue": "builds.gce",
            "repository": {
                "@type": "repository",
                "@href": "/repo/25205338",
                "@representation": "minimal",
                "id": 25205338,
                "name": "python-standard",
                "slug": "codecov/codecov-api",
            },
            "commit": {
                "@type": "commit",
                "@representation": "minimal",
                "id": 226208830,
                "sha": "3be5c52bd748c508a7e96993c02cf3518c816e84",
                "ref": "refs/heads/master",
                "message": "New Build: 10/01/20 20:00:54",
                "compare_url": "https://github.com/codecov/python-standard/compare/28392734979c...2485b28f9862",
                "committed_at": "2020-10-01T20:00:55Z",
            },
        }
        mock_get.return_value.status_code.return_value = 200
        mock_get.return_value.json.return_value = expected_response

        params = {
            "version": "v4",
            "commit": "3be5c52bd748c508a7e96993c02cf3518c816e84",
            "slug": "codecov/codecov-api",
            "owner": "codecov",
            "repo": "codecov-api",
            "token": "4a24929b-9276-4784-8e85-a7a008a32037",
            "service": "circleci",
            "pr": None,
            "pull_request": None,
            "flags": "this-is-a-flag,this-is-another-flag",
            "param_doesn't_exist_but_still_should_not_error": True,
            "s3": 123,
            "build_url": "https://thisisabuildurl.com",
            "job": 732059764,
            "using_global_token": False,
            "branch": None,
            "_did_change_merge_commit": False,
            "parent": "123abc",
        }

        expected_error = """
            ERROR: The coverage upload was rejected because the build is out of date. Please make sure the build is not stale for uploads to process correctly."""

        with pytest.raises(NotFound) as e:
            TokenlessUploadHandler("travis", params).verify_upload()
        assert [line.strip() for line in e.value.args[0].split("\n")] == [
            line.strip() for line in expected_error.split("\n")
        ]


class UploadHandlerAzureTokenlessTest(TestCase):
    def test_azure_no_job(self):
        params = {}

        expected_error = """Missing "job" argument. Please upload with the Codecov repository upload token to resolve issue."""

        with pytest.raises(NotFound) as e:
            TokenlessUploadHandler("azure_pipelines", params).verify_upload()
        assert [line.strip() for line in e.value.args[0].split("\n")] == [
            line.strip() for line in expected_error.split("\n")
        ]

    def test_azure_no_project(self):
        params = {"job": 732059764}

        expected_error = """Missing "project" argument. Please upload with the Codecov repository upload token to resolve issue."""

        with pytest.raises(NotFound) as e:
            TokenlessUploadHandler("azure_pipelines", params).verify_upload()
        assert [line.strip() for line in e.value.args[0].split("\n")] == [
            line.strip() for line in expected_error.split("\n")
        ]

    def test_azure_no_server_uri(self):
        params = {"project": "project123", "job": 732059764}

        expected_error = """Missing "server_uri" argument. Please upload with the Codecov repository upload token to resolve issue."""

        with pytest.raises(NotFound) as e:
            TokenlessUploadHandler("azure_pipelines", params).verify_upload()
        assert [line.strip() for line in e.value.args[0].split("\n")] == [
            line.strip() for line in expected_error.split("\n")
        ]

    @patch.object(requests, "get")
    def test_azure_http_error(self, mock_get):
        mock_get.side_effect = [requests.exceptions.HTTPError("Not found")]

        params = {"project": "project123", "job": 732059764, "server_uri": "https://"}

        expected_error = """Unable to locate build via Azure API. Please upload with the Codecov repository upload token to resolve issue."""

        with pytest.raises(NotFound) as e:
            TokenlessUploadHandler("azure_pipelines", params).verify_upload()
        assert [line.strip() for line in e.value.args[0].split("\n")] == [
            line.strip() for line in expected_error.split("\n")
        ]

    @patch.object(requests, "get")
    def test_azure_connection_error(self, mock_get):
        mock_get.side_effect = [requests.exceptions.ConnectionError("Not found")]

        params = {"project": "project123", "job": 732059764, "server_uri": "https://"}

        expected_error = """Unable to locate build via Azure API. Please upload with the Codecov repository upload token to resolve issue."""

        with pytest.raises(NotFound) as e:
            TokenlessUploadHandler("azure_pipelines", params).verify_upload()
        assert [line.strip() for line in e.value.args[0].split("\n")] == [
            line.strip() for line in expected_error.split("\n")
        ]

    @patch.object(requests, "get")
    def test_azure_no_errors(self, mock_get):
        expected_response = {
            "finishTime": "NOW",
            "buildNumber": "20190725.8",
            "status": "inProgress",
            "sourceVersion": "c739768fcac68144a3a6d82305b9c4106934d31a",
            "project": {"visibility": "public"},
            "repository": {"type": "GitHub"},
            "triggerInfo": {"pr.sourceSha": "c739768fcac68144a3a6d82305b9c4106934d31a"},
        }
        mock_get.return_value.status_code.return_value = 200
        mock_get.return_value.json.return_value = expected_response

        params = {
            "project": "project123",
            "job": 732059764,
            "server_uri": "https://",
            "commit": "c739768fcac68144a3a6d82305b9c4106934d31a",
            "build": "20190725.8",
        }

        res = TokenlessUploadHandler("azure_pipelines", params).verify_upload()

        assert res == "github"

    @patch.object(requests, "get")
    def test_azure_wrong_build_number(self, mock_get):
        expected_response = {
            "finishTime": f"{datetime.utcnow()}",
            "buildNumber": "BADBUILDNUM",
            "status": "completed",
            "sourceVersion": "c739768fcac68144a3a6d82305b9c4106934d31a",
            "project": {"visibility": "public"},
            "repository": {"type": "GitHub"},
        }
        mock_get.return_value.status_code.return_value = 200
        mock_get.return_value.json.return_value = expected_response

        params = {
            "project": "project123",
            "job": 732059764,
            "server_uri": "https://",
            "commit": "c739768fcac68144a3a6d82305b9c4106934d31a",
            "build": "20190725.8",
        }

        expected_error = """Build numbers do not match. Please upload with the Codecov repository upload token to resolve issue."""

        with pytest.raises(NotFound) as e:
            TokenlessUploadHandler("azure_pipelines", params).verify_upload()
        assert [line.strip() for line in e.value.args[0].split("\n")] == [
            line.strip() for line in expected_error.split("\n")
        ]

    @patch.object(requests, "get")
    def test_azure_expired_build(self, mock_get):
        expected_response = {
            "finishTime": f"{datetime.utcnow() - timedelta(minutes=4)}",
            "buildNumber": "20190725.8",
            "status": "completed",
            "sourceVersion": "c739768fcac68144a3a6d82305b9c4106934d31a",
            "project": {"visibility": "public"},
            "repository": {"type": "GitHub"},
        }

        mock_get.return_value.status_code.return_value = 200
        mock_get.return_value.json.return_value = expected_response

        params = {
            "project": "project123",
            "job": 732059764,
            "server_uri": "https://",
            "commit": "c739768fcac68144a3a6d82305b9c4106934d31a",
            "build": "20190725.8",
        }

        expected_error = """Azure build has already finished. Please upload with the Codecov repository upload token to resolve issue."""

        with pytest.raises(NotFound) as e:
            TokenlessUploadHandler("azure_pipelines", params).verify_upload()
        assert [line.strip() for line in e.value.args[0].split("\n")] == [
            line.strip() for line in expected_error.split("\n")
        ]

    @patch.object(requests, "get")
    def test_azure_invalid_status(self, mock_get):
        expected_response = {
            "finishTime": f"{datetime.utcnow()}",
            "buildNumber": "20190725.8",
            "status": "BADSTATUS",
            "sourceVersion": "c739768fcac68144a3a6d82305b9c4106934d31a",
            "project": {"visibility": "public"},
            "repository": {"type": "GitHub"},
        }

        mock_get.return_value.status_code.return_value = 200
        mock_get.return_value.json.return_value = expected_response

        params = {
            "project": "project123",
            "job": 732059764,
            "server_uri": "https://",
            "commit": "c739768fcac68144a3a6d82305b9c4106934d31a",
            "build": "20190725.8",
        }

        expected_error = """Azure build has already finished. Please upload with the Codecov repository upload token to resolve issue."""

        with pytest.raises(NotFound) as e:
            TokenlessUploadHandler("azure_pipelines", params).verify_upload()
        assert [line.strip() for line in e.value.args[0].split("\n")] == [
            line.strip() for line in expected_error.split("\n")
        ]

    @patch.object(requests, "get")
    def test_azure_wrong_commit(self, mock_get):
        expected_response = {
            "finishTime": "NOW",
            "buildNumber": "20190725.8",
            "status": "inProgress",
            "sourceVersion": "BADSHA",
            "project": {"visibility": "public"},
            "repository": {"type": "GitHub"},
        }

        mock_get.return_value.status_code.return_value = 200
        mock_get.return_value.json.return_value = expected_response

        params = {
            "project": "project123",
            "job": 732059764,
            "server_uri": "https://",
            "commit": "c739768fcac68144a3a6d82305b9c4106934d31a",
            "build": "20190725.8",
        }

        expected_error = """Commit sha does not match Azure build. Please upload with the Codecov repository upload token to resolve issue."""

        with pytest.raises(NotFound) as e:
            TokenlessUploadHandler("azure_pipelines", params).verify_upload()
        assert [line.strip() for line in e.value.args[0].split("\n")] == [
            line.strip() for line in expected_error.split("\n")
        ]

    @patch.object(requests, "get")
    def test_azure_not_public(self, mock_get):
        expected_response = """<!DOCTYPE html PUBLIC "-//W3C//DTD XHTML 1.0 Strict//EN" "http://www.w3.org/TR/xhtml1/DTD/xhtml1-strict.dtd">
                            <html lang="en-US">
                            <head><title>
                            Azure DevOps Services | Sign In
                            </title>
                            </html>"""

        mock_get.return_value.status_code.return_value = 203
        mock_get.return_value.json.side_effect = JSONDecodeError(
            "Expecting value: line 1 column 1", expected_response, 0
        )

        params = {
            "project": "project123",
            "job": 732059764,
            "server_uri": "https://",
            "commit": "c739768fcac68144a3a6d82305b9c4106934d31a",
            "build": "20190725.8",
        }

        expected_error = """Unable to locate build via Azure API. Project is likely private, please upload with the Codecov repository upload token to resolve issue."""

        with pytest.raises(NotFound) as e:
            TokenlessUploadHandler("azure_pipelines", params).verify_upload()
        assert [line.strip() for line in e.value.args[0].split("\n")] == [
            line.strip() for line in expected_error.split("\n")
        ]

    @patch.object(requests, "get")
    def test_azure_wrong_service_type(self, mock_get):
        expected_response = {
            "finishTime": "NOW",
            "buildNumber": "20190725.8",
            "status": "inProgress",
            "sourceVersion": "c739768fcac68144a3a6d82305b9c4106934d31a",
            "project": {"visibility": "public"},
            "repository": {"type": "BADREPOTYPE"},
        }

        mock_get.return_value.status_code.return_value = 200
        mock_get.return_value.json.return_value = expected_response

        params = {
            "project": "project123",
            "job": 732059764,
            "server_uri": "https://",
            "commit": "c739768fcac68144a3a6d82305b9c4106934d31a",
            "build": "20190725.8",
        }

        expected_error = """Sorry this service is not supported. Codecov currently only works with GitHub, GitLab, and BitBucket repositories"""

        with pytest.raises(NotFound) as e:
            TokenlessUploadHandler("azure_pipelines", params).verify_upload()
        assert [line.strip() for line in e.value.args[0].split("\n")] == [
            line.strip() for line in expected_error.split("\n")
        ]


class UploadHandlerAppveyorTokenlessTest(TestCase):
    def test_appveyor_no_job(self):
        params = {}

        expected_error = """Missing "job" argument. Please upload with the Codecov repository upload token to resolve issue."""

        with pytest.raises(NotFound) as e:
            TokenlessUploadHandler("appveyor", params).verify_upload()
        assert [line.strip() for line in e.value.args[0].split("\n")] == [
            line.strip() for line in expected_error.split("\n")
        ]

    @patch.object(requests, "get")
    def test_appveyor_http_error(self, mock_get):
        mock_get.side_effect = [requests.exceptions.HTTPError("Not found")]

        params = {"project": "project123", "job": "732059764", "server_uri": "https://"}

        expected_error = """Unable to locate build via Appveyor API. Please upload with the Codecov repository upload token to resolve issue."""

        with pytest.raises(NotFound) as e:
            TokenlessUploadHandler("appveyor", params).verify_upload()
        assert [line.strip() for line in e.value.args[0].split("\n")] == [
            line.strip() for line in expected_error.split("\n")
        ]

    @patch.object(requests, "get")
    def test_appveyor_connection_error(self, mock_get):
        mock_get.side_effect = [requests.exceptions.ConnectionError("Not found")]

        params = {
            "project": "project123",
            "job": "something/else/732059764",
            "server_uri": "https://",
        }

        expected_error = """Unable to locate build via Appveyor API. Please upload with the Codecov repository upload token to resolve issue."""

        with pytest.raises(NotFound) as e:
            TokenlessUploadHandler("appveyor", params).verify_upload()
        assert [line.strip() for line in e.value.args[0].split("\n")] == [
            line.strip() for line in expected_error.split("\n")
        ]

    @patch.object(requests, "get")
    def test_appveyor_finished_build(self, mock_get):
        expected_response = {
            "build": {"jobs": [{"jobId": "732059764"}]},
            "finishTime": "NOW",
            "buildNumber": "20190725.8",
            "status": "inProgress",
            "sourceVersion": "c739768fcac68144a3a6d82305b9c4106934d31a",
            "project": {"visibility": "public", "repositoryType": "github"},
            "repository": {"type": "GitHub"},
            "triggerInfo": {"pr.sourceSha": "c739768fcac68144a3a6d82305b9c4106934d31a"},
        }
        mock_get.return_value.status_code.return_value = 200
        mock_get.return_value.json.return_value = expected_response

        params = {
            "project": "project123",
            "job": "732059764",
            "server_uri": "https://",
            "commit": "c739768fcac68144a3a6d82305b9c4106934d31a",
            "build": "20190725.8",
        }

        expected_error = """Build already finished, unable to accept new reports. Please upload with the Codecov repository upload token to resolve issue."""

        with pytest.raises(NotFound) as e:
            TokenlessUploadHandler("appveyor", params).verify_upload()
        assert [line.strip() for line in e.value.args[0].split("\n")] == [
            line.strip() for line in expected_error.split("\n")
        ]

    @patch.object(requests, "get")
    def test_appveyor_no_errors(self, mock_get):
        expected_response = {
            "build": {"jobs": [{"jobId": "732059764"}]},
            "finishTime": "NOW",
            "buildNumber": "20190725.8",
            "status": "inProgress",
            "sourceVersion": "c739768fcac68144a3a6d82305b9c4106934d31a",
            "project": {"visibility": "public", "repositoryType": "github"},
            "repository": {"type": "GitHub"},
            "triggerInfo": {"pr.sourceSha": "c739768fcac68144a3a6d82305b9c4106934d31a"},
        }
        mock_get.return_value.status_code.return_value = 200
        mock_get.return_value.json.return_value = expected_response

        params = {
            "project": "project123",
            "job": "732059764",
            "server_uri": "https://",
            "commit": "c739768fcac68144a3a6d82305b9c4106934d31a",
            "build": "732059764",
        }

        res = TokenlessUploadHandler("appveyor", params).verify_upload()

        assert res == "github"

    @patch.object(requests, "get")
    def test_appveyor_invalid_service(self, mock_get):
        expected_response = {
            "build": {"jobs": [{"jobId": "732059764"}]},
            "finishTime": "NOW",
            "buildNumber": "20190725.8",
            "status": "inProgress",
            "sourceVersion": "c739768fcac68144a3a6d82305b9c4106934d31a",
            "project": {"visibility": "public", "repositoryType": "gitthub"},
            "repository": {"type": "GittHub"},
            "triggerInfo": {"pr.sourceSha": "c739768fcac68144a3a6d82305b9c4106934d31a"},
        }
        mock_get.return_value.status_code.return_value = 200
        mock_get.return_value.json.return_value = expected_response

        params = {
            "project": "project123",
            "job": "732059764",
            "server_uri": "https://",
            "commit": "c739768fcac68144a3a6d82305b9c4106934d31a",
            "build": "732059764",
        }
        expected_error = """Sorry this service is not supported. Codecov currently only works with GitHub, GitLab, and BitBucket repositories"""

        with pytest.raises(NotFound) as e:
            TokenlessUploadHandler("appveyor", params).verify_upload()
        assert [line.strip() for line in e.value.args[0].split("\n")] == [
            line.strip() for line in expected_error.split("\n")
        ]


class UploadHandlerCircleciTokenlessTest(TestCase):
    def test_circleci_no_build(self):
        params = {}

        expected_error = """Missing "build" argument. Please upload with the Codecov repository upload token to resolve issue."""

        with pytest.raises(NotFound) as e:
            TokenlessUploadHandler("circleci", params).verify_upload()
        assert [line.strip() for line in e.value.args[0].split("\n")] == [
            line.strip() for line in expected_error.split("\n")
        ]

    def test_circleci_no_owner(self):
        params = {"build": 1234}

        expected_error = """Missing "owner" argument. Please upload with the Codecov repository upload token to resolve issue."""

        with pytest.raises(NotFound) as e:
            TokenlessUploadHandler("circleci", params).verify_upload()
        assert [line.strip() for line in e.value.args[0].split("\n")] == [
            line.strip() for line in expected_error.split("\n")
        ]

    def test_circleci_no_repo(self):
        params = {"build": "12.34", "owner": "owner"}

        expected_error = """Missing "repo" argument. Please upload with the Codecov repository upload token to resolve issue."""

        with pytest.raises(NotFound) as e:
            TokenlessUploadHandler("circleci", params).verify_upload()
        assert [line.strip() for line in e.value.args[0].split("\n")] == [
            line.strip() for line in expected_error.split("\n")
        ]

    @patch.object(requests, "get")
    def test_circleci_http_error(self, mock_get):
        mock_get.side_effect = [requests.exceptions.HTTPError("Not found")]

        params = {"build": "12.34", "owner": "owner", "repo": "repo"}

        expected_error = """Unable to locate build via CircleCI API. Please upload with the Codecov repository upload token to resolve issue."""

        with pytest.raises(NotFound) as e:
            TokenlessUploadHandler("circleci", params).verify_upload()
        assert [line.strip() for line in e.value.args[0].split("\n")] == [
            line.strip() for line in expected_error.split("\n")
        ]

    @patch.object(requests, "get")
    def test_circleci_connection_error(self, mock_get):
        mock_get.side_effect = [requests.exceptions.ConnectionError("Not found")]

        params = {"build": "12.34", "owner": "owner", "repo": "repo"}

        expected_error = """Unable to locate build via CircleCI API. Please upload with the Codecov repository upload token to resolve issue."""

        with pytest.raises(NotFound) as e:
            TokenlessUploadHandler("circleci", params).verify_upload()
        assert [line.strip() for line in e.value.args[0].split("\n")] == [
            line.strip() for line in expected_error.split("\n")
        ]

    @patch.object(requests, "get")
    def test_circleci_invalid_commit(self, mock_get):
        expected_response = {"vcs_revision": "739768fcac68144a3a6d82305b9c4106934d31a"}
        mock_get.return_value.status_code.return_value = 200
        mock_get.return_value.json.return_value = expected_response

        params = {
            "build": "12.34",
            "owner": "owner",
            "repo": "repo",
            "commit": "c739768fcac68144a3a6d82305b9c4106934d31a",
        }
        expected_error = """Commit sha does not match Circle build. Please upload with the Codecov repository upload token to resolve issue."""

        with pytest.raises(NotFound) as e:
            TokenlessUploadHandler("circleci", params).verify_upload()
        assert [line.strip() for line in e.value.args[0].split("\n")] == [
            line.strip() for line in expected_error.split("\n")
        ]

    @patch.object(requests, "get")
    def test_circleci_invalid_stop_time(self, mock_get):
        expected_response = {"vcs_revision": "c739768fcac68144a3a6d82305b9c4106934d31a"}
        mock_get.return_value.status_code.return_value = 200
        mock_get.return_value.json.return_value = expected_response

        params = {
            "build": "12.34",
            "owner": "owner",
            "repo": "repo",
            "commit": "c739768fcac68144a3a6d82305b9c4106934d31a",
        }
        expected_error = """Build has already finished, uploads rejected."""

        with pytest.raises(NotFound) as e:
            TokenlessUploadHandler("circleci", params).verify_upload()
        assert [line.strip() for line in e.value.args[0].split("\n")] == [
            line.strip() for line in expected_error.split("\n")
        ]

    @patch.object(requests, "get")
    def test_circleci_invalid_stop_time(self, mock_get):
        expected_response = {
            "vcs_revision": "c739768fcac68144a3a6d82305b9c4106934d31a",
            "vcs_type": "github",
        }
        mock_get.return_value.status_code.return_value = 200
        mock_get.return_value.json.return_value = expected_response

        params = {
            "build": "12.34",
            "owner": "owner",
            "repo": "repo",
            "commit": "c739768fcac68144a3a6d82305b9c4106934d31a",
        }

        assert TokenlessUploadHandler("circleci", params).verify_upload() == "github"


class UploadHandlerGithubActionsTokenlessTest(TestCase):
    @patch(
        "upload.tokenless.github_actions.TokenlessGithubActionsHandler.get_build",
        new_callable=PropertyMock,
    )
    def test_underscore_replace(self, mock_get):
        expected_response = {
            "commit_sha": "c739768fcac68144a3a6d82305b9c4106934d31a",
            "slug": "owner/repo",
            "public": True,
            "finish_time": f"{datetime.utcnow()}".split(".")[0],
        }
        mock_get.return_value.status_code.return_value = 200
        mock_get.return_value.return_value = expected_response

        params = {
            "build": "12.34",
            "owner": "owner",
            "repo": "repo",
            "commit": "c739768fcac68144a3a6d82305b9c4106934d31a",
        }

        assert (
            TokenlessUploadHandler("github-actions", params).verify_upload() == "github"
        )

    def test_github_actions_no_owner(self):
        params = {}

        expected_error = """Missing "owner" argument. Please upload with the Codecov repository upload token to resolve issue."""

        with pytest.raises(NotFound) as e:
            TokenlessUploadHandler("github_actions", params).verify_upload()
        assert [line.strip() for line in e.value.args[0].split("\n")] == [
            line.strip() for line in expected_error.split("\n")
        ]

    def test_github_actions_no_repo(self):
        params = {"owner": "owner"}

        expected_error = """Missing "repo" argument. Please upload with the Codecov repository upload token to resolve issue."""

        with pytest.raises(NotFound) as e:
            TokenlessUploadHandler("github_actions", params).verify_upload()
        assert [line.strip() for line in e.value.args[0].split("\n")] == [
            line.strip() for line in expected_error.split("\n")
        ]

    @patch("upload.tokenless.github_actions.get", new_callable=PropertyMock)
    def test_github_actions_client_error(self, mock_get_torngit):
        mock_get = mock_get_torngit.return_value.get_workflow_run
        mock_get.side_effect = [TorngitClientGeneralError(500, None, None)]

        params = {"build": "12.34", "owner": "owner", "repo": "repo"}

        with pytest.raises(NotFound) as e:
            TokenlessUploadHandler("github_actions", params).verify_upload()
        assert (
            e.value.args[0]
            == "Unable to locate build via Github Actions API. Please upload with the Codecov repository upload token to resolve issue."
        )
        mock_get_torngit.assert_called_with(
            "github",
            token={"key": None},
            repo={"name": "repo"},
            owner={"username": "owner"},
            oauth_consumer_token={"key": ANY, "secret": ANY},
        )
        mock_get.assert_called_with("12.34")
        mock_get.reset_mock()
        mock_get.side_effect = [Exception("Not Found")]

        with pytest.raises(NotFound) as e:
            TokenlessUploadHandler("github_actions", params).verify_upload()
        assert (
            e.value.args[0]
            == "Unable to locate build via Github Actions API. Please upload with the Codecov repository upload token to resolve issue."
        )
        mock_get.assert_called_with("12.34")

    @patch(
        "upload.tokenless.github_actions.TokenlessGithubActionsHandler.get_build",
        new_callable=PropertyMock,
    )
    def test_github_actions_non_public(self, mock_get):
        expected_response = {"public": False, "slug": "slug", "commit_sha": "abc"}
        mock_get.return_value.status_code.return_value = 200
        mock_get.return_value.return_value = expected_response

        params = {
            "build": "12.34",
            "owner": "owner",
            "repo": "repo",
            "commit": "c739768fcac68144a3a6d82305b9c4106934d31a",
        }

        expected_error = """Repository slug or commit sha do not match Github actions build. Please upload with the Codecov repository upload token to resolve issue."""

        with pytest.raises(NotFound) as e:
            TokenlessUploadHandler("github_actions", params).verify_upload()
        assert [line.strip() for line in e.value.args[0].split("\n")] == [
            line.strip() for line in expected_error.split("\n")
        ]

    @patch(
        "upload.tokenless.github_actions.TokenlessGithubActionsHandler.get_build",
        new_callable=PropertyMock,
    )
    def test_github_actions_wrong_slug(self, mock_get):
        expected_response = {"slug": "slug", "public": True, "commit_sha": "abc"}
        mock_get.return_value.status_code.return_value = 200
        mock_get.return_value.return_value = expected_response

        params = {
            "build": "12.34",
            "owner": "owner",
            "repo": "repo",
            "commit": "c739768fcac68144a3a6d82305b9c4106934d31a",
        }

        expected_error = """Repository slug or commit sha do not match Github actions build. Please upload with the Codecov repository upload token to resolve issue."""

        with pytest.raises(NotFound) as e:
            TokenlessUploadHandler("github_actions", params).verify_upload()
        assert [line.strip() for line in e.value.args[0].split("\n")] == [
            line.strip() for line in expected_error.split("\n")
        ]

    @patch(
        "upload.tokenless.github_actions.TokenlessGithubActionsHandler.get_build",
        new_callable=PropertyMock,
    )
    def test_github_actions_wrong_commit(self, mock_get):
        expected_response = {"commit_sha": "abc", "slug": "owner/repo", "public": True}
        mock_get.return_value.status_code.return_value = 200
        mock_get.return_value.return_value = expected_response

        params = {
            "build": "12.34",
            "owner": "owner",
            "repo": "repo",
            "commit": "c739768fcac68144a3a6d82305b9c4106934d31a",
        }

        expected_error = """Repository slug or commit sha do not match Github actions build. Please upload with the Codecov repository upload token to resolve issue."""

        with pytest.raises(NotFound) as e:
            TokenlessUploadHandler("github_actions", params).verify_upload()
        assert [line.strip() for line in e.value.args[0].split("\n")] == [
            line.strip() for line in expected_error.split("\n")
        ]

    @patch(
        "upload.tokenless.github_actions.TokenlessGithubActionsHandler.get_build",
        new_callable=PropertyMock,
    )
    def test_github_actions_no_build_status(self, mock_get):
        expected_response = {
            "commit_sha": "c739768fcac68144a3a6d82305b9c4106934d31a",
            "slug": "owner/repo",
            "public": True,
            "finish_time": f"{datetime.utcnow() - timedelta(minutes=10)}".split(".")[0],
        }
        mock_get.return_value.status_code.return_value = 200
        mock_get.return_value.return_value = expected_response

        params = {
            "build": "12.34",
            "owner": "owner",
            "repo": "repo",
            "commit": "c739768fcac68144a3a6d82305b9c4106934d31a",
        }

        expected_error = """Actions workflow run is stale"""

        with pytest.raises(NotFound) as e:
            TokenlessUploadHandler("github_actions", params).verify_upload()
        assert [line.strip() for line in e.value.args[0].split("\n")] == [
            line.strip() for line in expected_error.split("\n")
        ]

    @patch(
        "upload.tokenless.github_actions.TokenlessGithubActionsHandler.get_build",
        new_callable=PropertyMock,
    )
    def test_github_actions(self, mock_get):
        expected_response = {
            "commit_sha": "c739768fcac68144a3a6d82305b9c4106934d31a",
            "slug": "owner/repo",
            "public": True,
            "finish_time": f"{datetime.utcnow()}".split(".")[0],
        }
        mock_get.return_value.status_code.return_value = 200
        mock_get.return_value.return_value = expected_response

        params = {
            "build": "12.34",
            "owner": "owner",
            "repo": "repo",
            "commit": "c739768fcac68144a3a6d82305b9c4106934d31a",
        }

        assert (
            TokenlessUploadHandler("github_actions", params).verify_upload() == "github"
        )

    @patch(
        "upload.tokenless.github_actions.TokenlessGithubActionsHandler.get_build",
        new_callable=PropertyMock,
    )
    def test_github_actions_in_progress(self, mock_get):
        expected_response = {
            "commit_sha": "c739768fcac68144a3a6d82305b9c4106934d31a",
            "slug": "owner/repo",
            "public": True,
            "status": "in_progress",
        }
        mock_get.return_value.status_code.return_value = 200
        mock_get.return_value.return_value = expected_response

        params = {
            "build": "12.34",
            "owner": "owner",
            "repo": "repo",
            "commit": "c739768fcac68144a3a6d82305b9c4106934d31a",
        }
        assert (
            TokenlessUploadHandler("github_actions", params).verify_upload() == "github"
        )

    @patch(
        "upload.tokenless.github_actions.TokenlessGithubActionsHandler.get_build",
        new_callable=PropertyMock,
    )
    def test_github_actions_queued(self, mock_get):
        expected_response = {
            "commit_sha": "c739768fcac68144a3a6d82305b9c4106934d31a",
            "slug": "owner/repo",
            "public": True,
            "status": "queued",
        }
        mock_get.return_value.status_code.return_value = 200
        mock_get.return_value.return_value = expected_response

        params = {
            "build": "12.34",
            "owner": "owner",
            "repo": "repo",
            "commit": "c739768fcac68144a3a6d82305b9c4106934d31a",
        }
        assert (
            TokenlessUploadHandler("github_actions", params).verify_upload() == "github"
        )

    @patch(
        "upload.tokenless.cirrus.TokenlessCirrusHandler.get_build",
        new_callable=PropertyMock,
    )
    def test_cirrus_ci(self, mock_get):
        expected_response = {
            "data": {
                "build": {
                    "changeIdInRepo": "bbeefc070d847ff1ed526d412b7f97c5e743b1c1",
                    "repository": {"name": "mtail", "owner": "google"},
                    "status": "COMPLETED",
                    "buildCreatedTimestamp": time.time() - 90,
                    "durationInSeconds": 90,
                }
            }
        }
        mock_get.return_value.status_code.return_value = 200
        mock_get.return_value.return_value = expected_response

        params = {
            "build": "5699563004624896",
            "owner": "google",
            "repo": "mtail",
            "commit": "bbeefc070d847ff1ed526d412b7f97c5e743b1c1",
        }

        assert TokenlessUploadHandler("cirrus_ci", params).verify_upload() == "github"

    @patch(
        "upload.tokenless.cirrus.TokenlessCirrusHandler.get_build",
        new_callable=PropertyMock,
    )
    def test_cirrus_ci_executing(self, mock_get):
        expected_response = {
            "data": {
                "build": {
                    "changeIdInRepo": "bbeefc070d847ff1ed526d412b7f97c5e743b1c1",
                    "repository": {"name": "mtail", "owner": "google"},
                    "status": "EXECUTING",
                }
            }
        }
        mock_get.return_value.status_code.return_value = 200
        mock_get.return_value.return_value = expected_response

        params = {
            "build": "5699563004624896",
            "owner": "google",
            "repo": "mtail",
            "commit": "bbeefc070d847ff1ed526d412b7f97c5e743b1c1",
        }

        assert TokenlessUploadHandler("cirrus_ci", params).verify_upload() == "github"

    @patch(
        "upload.tokenless.cirrus.TokenlessCirrusHandler.get_build",
        new_callable=PropertyMock,
    )
    def test_cirrus_ci_no_owner(self, mock_get):
        expected_response = {
            "data": {
                "build": {
                    "changeIdInRepo": "bbeefc070d847ff1ed526d412b7f97c5e743b1c1",
                    "repository": {"owner": "google", "name": "mtail"},
                    "status": "EXECUTING",
                }
            }
        }
        mock_get.return_value.status_code.return_value = 200
        mock_get.return_value.return_value = expected_response

        params = {
            "build": "5699563004624896",
            "repo": "mtail",
            "commit": "bbeefc070d847ff1ed526d412b7f97c5e743b1c1",
        }

        expected_error = """Missing "owner" argument. Please upload with the Codecov repository upload token to resolve this issue."""

        with pytest.raises(NotFound) as e:
            TokenlessUploadHandler("cirrus_ci", params).verify_upload()
        assert [line.strip() for line in e.value.args[0].split("\n")] == [
            line.strip() for line in expected_error.split("\n")
        ]

    @patch(
        "upload.tokenless.cirrus.TokenlessCirrusHandler.get_build",
        new_callable=PropertyMock,
    )
    def test_cirrus_ci_no_repo(self, mock_get):
        expected_response = {
            "data": {
                "build": {
                    "changeIdInRepo": "bbeefc070d847ff1ed526d412b7f97c5e743b1c1",
                    "repository": {"owner": "google", "name": "mtail"},
                    "status": "EXECUTING",
                }
            }
        }
        mock_get.return_value.status_code.return_value = 200
        mock_get.return_value.return_value = expected_response

        params = {
            "build": "5699563004624896",
            "owner": "google",
            "commit": "bbeefc070d847ff1ed526d412b7f97c5e743b1c1",
        }

        expected_error = """Missing "repo" argument. Please upload with the Codecov repository upload token to resolve this issue."""

        with pytest.raises(NotFound) as e:
            TokenlessUploadHandler("cirrus_ci", params).verify_upload()
        assert [line.strip() for line in e.value.args[0].split("\n")] == [
            line.strip() for line in expected_error.split("\n")
        ]

    @patch(
        "upload.tokenless.cirrus.TokenlessCirrusHandler.get_build",
        new_callable=PropertyMock,
    )
    def test_cirrus_ci_no_commit(self, mock_get):
        expected_response = {
            "data": {
                "build": {
                    "changeIdInRepo": "bbeefc070d847ff1ed526d412b7f97c5e743b1c1",
                    "repository": {"owner": "google", "name": "mtail"},
                    "status": "EXECUTING",
                }
            }
        }
        mock_get.return_value.status_code.return_value = 200
        mock_get.return_value.return_value = expected_response

        params = {"build": "5699563004624896", "owner": "google", "repo": "mtail"}

        expected_error = """Missing "commit" argument. Please upload with the Codecov repository upload token to resolve this issue."""

        with pytest.raises(NotFound) as e:
            TokenlessUploadHandler("cirrus_ci", params).verify_upload()
        assert [line.strip() for line in e.value.args[0].split("\n")] == [
            line.strip() for line in expected_error.split("\n")
        ]

    @patch(
        "upload.tokenless.cirrus.TokenlessCirrusHandler.get_build",
        new_callable=PropertyMock,
    )
    def test_cirrus_ci_wrong_repository(self, mock_get):
        expected_response = {
            "data": {
                "build": {
                    "changeIdInRepo": "bbeefc070d847ff1ed526d412b7f97c5e743b1c1",
                    "repository": {"owner": "test", "name": "test"},
                    "status": "EXECUTING",
                }
            }
        }
        mock_get.return_value.status_code.return_value = 200
        mock_get.return_value.return_value = expected_response

        params = {
            "build": "5699563004624896",
            "owner": "google",
            "repo": "mtail",
            "commit": "bbeefc070d847ff1ed526d412b7f97c5e743b1c1",
        }

        expected_error = """Repository slug does not match Cirrus CI build. Please upload with the Codecov repository upload token to resolve this issue."""

        with pytest.raises(NotFound) as e:
            TokenlessUploadHandler("cirrus_ci", params).verify_upload()
        assert [line.strip() for line in e.value.args[0].split("\n")] == [
            line.strip() for line in expected_error.split("\n")
        ]

    @patch(
        "upload.tokenless.cirrus.TokenlessCirrusHandler.get_build",
        new_callable=PropertyMock,
    )
    def test_cirrus_ci_wrong_commit(self, mock_get):
        expected_response = {
            "data": {
                "build": {
                    "changeIdInRepo": "testtesttesttest",
                    "repository": {"owner": "google", "name": "mtail"},
                    "status": "EXECUTING",
                }
            }
        }
        mock_get.return_value.status_code.return_value = 200
        mock_get.return_value.return_value = expected_response

        params = {
            "build": "5699563004624896",
            "owner": "google",
            "repo": "mtail",
            "commit": "bbeefc070d847ff1ed526d412b7f97c5e743b1c1",
        }

        expected_error = """Commit sha does not match Cirrus CI build. Please upload with the Codecov repository upload token to resolve issue."""

        with pytest.raises(NotFound) as e:
            TokenlessUploadHandler("cirrus_ci", params).verify_upload()
        assert [line.strip() for line in e.value.args[0].split("\n")] == [
            line.strip() for line in expected_error.split("\n")
        ]

    @patch(
        "upload.tokenless.cirrus.TokenlessCirrusHandler.get_build",
        new_callable=PropertyMock,
    )
    def test_cirrus_ci_stale(self, mock_get):
        expected_response = {
            "data": {
                "build": {
                    "changeIdInRepo": "bbeefc070d847ff1ed526d412b7f97c5e743b1c1",
                    "repository": {"name": "mtail", "owner": "google"},
                    "status": "COMPLETED",
                    "buildCreatedTimestamp": time.time() - 100000,
                    "durationInSeconds": 1,
                }
            }
        }
        mock_get.return_value.status_code.return_value = 200
        mock_get.return_value.return_value = expected_response

        params = {
            "build": "5699563004624896",
            "owner": "google",
            "repo": "mtail",
            "commit": "bbeefc070d847ff1ed526d412b7f97c5e743b1c1",
        }

        expected_error = """Cirrus run is stale"""

        with pytest.raises(NotFound) as e:
            TokenlessUploadHandler("cirrus_ci", params).verify_upload()
        assert [line.strip() for line in e.value.args[0].split("\n")] == [
            line.strip() for line in expected_error.split("\n")
        ]
