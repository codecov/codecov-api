import fnmatch
import logging
import re

from asgiref.sync import async_to_sync
from rest_framework import status
from rest_framework.exceptions import NotFound
from rest_framework.generics import CreateAPIView
from rest_framework.response import Response
from shared.torngit.exceptions import TorngitClientError, TorngitClientGeneralError
from shared.validation.helpers import translate_glob_to_regex

from codecov_auth.authentication.repo_auth import (
    GlobalTokenAuthentication,
    OrgLevelTokenAuthentication,
    RepositoryLegacyTokenAuthentication,
)
from services.repo_providers import RepoProviderService
from services.task import TaskService
from services.yaml import final_commit_yaml
from upload.helpers import try_to_get_best_possible_bot_token
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


class EmptyUploadView(CreateAPIView, GetterMixin):
    permission_classes = [CanDoCoverageUploadsPermission]
    authentication_classes = [
        GlobalTokenAuthentication,
        OrgLevelTokenAuthentication,
        RepositoryLegacyTokenAuthentication,
    ]

    def post(self, request, *args, **kwargs):
        repo = self.get_repo()
        commit = self.get_commit(repo)
        yaml = final_commit_yaml(commit, request.user).to_dict()
        token = try_to_get_best_possible_bot_token(repo)
        provider = RepoProviderService().get_adapter(repo.author, repo, token=token)
        pull_id = commit.pullid
        try:
            if pull_id is None:
                pull_id = async_to_sync(provider.find_pull_request)(
                    commit=commit.commitid
                )
        except TorngitClientGeneralError as e:
            log.warning(
                f"Request client error {e}",
                extra=dict(
                    commit=commit.commitid,
                    repo_name=repo.name,
                ),
            )
            raise NotFound(f"Unable to get pull request for commit: {commit.commitid}")

        try:
            changed_files = async_to_sync(provider.get_pull_request_files)(pull_id)
        except TorngitClientError as e:
            log.warning(
                f"Request client error {e}",
                extra=dict(
                    commit=commit.commitid,
                    repo_name=repo.name,
                ),
            )
            raise NotFound("Unable to get pull request's files.")

        ignored_files = yaml.get("ignore", [])
        regex_non_testable_files = [
            translate_glob_to_regex(path) for path in GLOB_NON_TESTABLE_FILES
        ]
        compiled_files_to_ignore = [
            re.compile(path) for path in (regex_non_testable_files + ignored_files)
        ]
        ignored_changed_files = [
            file
            for file in changed_files
            if any(map(lambda regex: regex.match(file), compiled_files_to_ignore))
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
