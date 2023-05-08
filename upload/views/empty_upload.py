import fnmatch
import logging
import re

from asgiref.sync import async_to_sync
from django.http import HttpRequest, HttpResponseNotAllowed
from rest_framework import status
from rest_framework.generics import ListCreateAPIView
from rest_framework.response import Response
from shared.torngit.exceptions import TorngitObjectNotFoundError

from codecov_auth.authentication.repo_auth import (
    GlobalTokenAuthentication,
    RepositoryLegacyTokenAuthentication,
)
from services.repo_providers import RepoProviderService
from services.task import TaskService
from services.yaml import final_commit_yaml
from upload.views.base import GetterMixin
from upload.views.uploads import CanDoCoverageUploadsPermission

log = logging.getLogger(__name__)

GLOB_NON_TESTABLE_FILES = [
    "*.cfg",
    "*.conf",
    "*.css",
    "*.csv",
    "*.db",
    "*.doc",
    "*.egg",
    "*.env",
    "*.git",
    "*.html",
    "*.htmlypertext",
    "*.ini",
    "*.jar*",
    "*.jpeg",
    "*.jpg",
    "*.jsonipt",
    "*.mak*",
    "*.md",
    "*.pdf",
    "*.png",
    "*.ppt",
    "*.svg",
    "*.tar.tz",
    "*.template",
    "*.txt",
    "*.whl",
    "*.xls",
    "*.xml",
    "*.yaml",
    "*.yml",
]


class EmptyUploadView(ListCreateAPIView, GetterMixin):
    permission_classes = [CanDoCoverageUploadsPermission]
    authentication_classes = [
        GlobalTokenAuthentication,
        RepositoryLegacyTokenAuthentication,
    ]

    def post(self, request, *args, **kwargs):
        repo = self.get_repo()
        commit = self.get_commit(repo)
        yaml = final_commit_yaml(commit, request.user).to_dict()

        provider = RepoProviderService().get_adapter(repo.author, repo)
        pull_id = commit.pullid
        try:
            if pull_id is None:
                pull_id = async_to_sync(provider.find_pull_request)(
                    commit=commit.commitid
                )
        except:
            raise TorngitObjectNotFoundError(
                f"Pull not found for commit: {commit.commitid}"
            )

        changed_files = async_to_sync(provider.get_pull_request_files)(pull_id)

        ignored_files = yaml.get("ignore", [])
        compiled_ignored_files = [re.compile(path) for path in ignored_files]
        regex_non_testable_files = [
            fnmatch.translate(path) for path in GLOB_NON_TESTABLE_FILES
        ]
        compiled_non_testable_files = [
            re.compile(path) for path in regex_non_testable_files
        ]

        ignored_changed_files = [
            file
            for file in changed_files
            if any(map(lambda regex: regex.match(file), compiled_ignored_files))
        ] + [
            file
            for file in changed_files
            if any(map(lambda regex: regex.match(file), compiled_non_testable_files))
        ]
        if set(changed_files) == set(ignored_changed_files):
            TaskService().notify(
                repoid=repo.repoid, commitid=commit.commitid, empty_upload="pass"
            )
            return Response(
                data={
                    "result": "All changed files are ignored. Triggering passing notifications.",
                    "non_ignored_files": [],
                },
                status=status.HTTP_200_OK,
            )

        non_ignored_files = set(changed_files) - set(ignored_changed_files)
        TaskService().notify(
            repoid=repo.repoid, commitid=commit.commitid, empty_upload="fail"
        )
        return Response(
            data={
                "result": "Some files cannot be ignored. Triggering failing notifications.",
                "non_ignored_files": non_ignored_files,
            },
            status=status.HTTP_200_OK,
        )

    def list(
        self,
        request: HttpRequest,
        service: str,
        repo: str,
        commit_sha: str,
    ):
        return HttpResponseNotAllowed(permitted_methods=["POST"])
