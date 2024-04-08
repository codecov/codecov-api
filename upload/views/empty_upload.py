import fnmatch
from loguru import logger
from typing import List

import regex
from asgiref.sync import async_to_sync
from rest_framework import serializers, status
from rest_framework.exceptions import NotFound
from rest_framework.generics import CreateAPIView
from rest_framework.response import Response
from shared.torngit.exceptions import TorngitClientError, TorngitClientGeneralError

from codecov_auth.authentication.repo_auth import (
    GitHubOIDCTokenAuthentication,
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


class EmptyUploadSerializer(serializers.Serializer):
    should_force = serializers.BooleanField(required=False)


class EmptyUploadView(CreateAPIView, GetterMixin):
    permission_classes = [CanDoCoverageUploadsPermission]
    authentication_classes = [
        GlobalTokenAuthentication,
        OrgLevelTokenAuthentication,
        GitHubOIDCTokenAuthentication,
        RepositoryLegacyTokenAuthentication,
    ]

    def post(self, request, *args, **kwargs):
        serializer = EmptyUploadSerializer(data=request.data)
        if not serializer.is_valid():
            return Response(serializer.errors, status=status.HTTP_400_BAD_REQUEST)
        data = serializer.validated_data
        should_force = data.get("should_force", False)

        repo = self.get_repo()
        commit = self.get_commit(repo)

        if should_force is True:
            TaskService().notify(
                repoid=repo.repoid, commitid=commit.commitid, empty_upload="pass"
            )
            return Response(
                data={
                    "result": "Force option was enabled. Triggering passing notifications.",
                    "non_ignored_files": [],
                },
                status=status.HTTP_200_OK,
            )

        yaml = final_commit_yaml(commit, request.user).to_dict()
        token = try_to_get_best_possible_bot_token(repo)
        provider = RepoProviderService().get_adapter(repo.author, repo, token=token)
        pull_id = commit.pullid
        if pull_id is None:
            pull_id = self.get_pull_request_id(commit, provider, pull_id)

        changed_files: List[str] = self.get_changed_files_from_provider(
            commit, provider, pull_id
        )

        ignored_files = yaml.get("ignore", [])

        regex_non_testable_files = [
            fnmatch.translate(path) for path in GLOB_NON_TESTABLE_FILES
        ]

        compiled_files_to_ignore = [
            regex.compile(path) for path in (regex_non_testable_files + ignored_files)
        ]

        ignored_changed_files = [
            file
            for file in changed_files
            if any(
                map(
                    lambda regex_patt: regex.match(regex_patt, file, timeout=2),
                    compiled_files_to_ignore,
                )
            )
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

    def get_changed_files_from_provider(self, commit, provider, pull_id):
        try:
            changed_files = async_to_sync(provider.get_pull_request_files)(pull_id)
        except TorngitClientError:
            logger.warning(
                f"Request client error",
                extra=dict(
                    commit=commit.commitid,
                    repoid=commit.repository.repoid,
                ),
                exc_info=True,
            )
            raise NotFound("Unable to get pull request's files.")
        return changed_files

    def get_pull_request_id(self, commit, provider, pull_id):
        try:
            if pull_id is None:
                pull_id = async_to_sync(provider.find_pull_request)(
                    commit=commit.commitid
                )
        except TorngitClientGeneralError:
            logger.warning(
                f"Request client error",
                extra=dict(
                    commit=commit.commitid,
                    repoid=commit.repository.repoid,
                ),
                exc_info=True,
            )
            raise NotFound(f"Unable to get pull request for commit: {commit.commitid}")
        return pull_id
