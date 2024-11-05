import logging

from rest_framework import status
from rest_framework.generics import ListCreateAPIView
from rest_framework.response import Response

from codecov_auth.authentication.repo_auth import (
    GitHubOIDCTokenAuthentication,
    GlobalTokenAuthentication,
    OrgLevelTokenAuthentication,
    RepositoryLegacyTokenAuthentication,
    TokenlessAuthentication,
    UploadTokenRequiredAuthenticationCheck,
    repo_auth_custom_exception_handler,
)
from upload.serializers import (
    CommitReportSerializer,
    CommitSerializer,
    UploadSerializer,
)
from upload.throttles import UploadsPerCommitThrottle, UploadsPerWindowThrottle
from upload.views.commits import CommitLogicMixin
from upload.views.reports import ReportLogicMixin
from upload.views.uploads import CanDoCoverageUploadsPermission, UploadLogicMixin

log = logging.getLogger(__name__)


class CombinedUploadMixin(CommitLogicMixin, ReportLogicMixin, UploadLogicMixin):
    pass


class CombinedUploadView(ListCreateAPIView, CombinedUploadMixin):
    permission_classes = [CanDoCoverageUploadsPermission]
    authentication_classes = [
        UploadTokenRequiredAuthenticationCheck,
        GlobalTokenAuthentication,
        OrgLevelTokenAuthentication,
        GitHubOIDCTokenAuthentication,
        RepositoryLegacyTokenAuthentication,
        TokenlessAuthentication,
    ]
    throttle_classes = [UploadsPerCommitThrottle, UploadsPerWindowThrottle]

    def get_exception_handler(self):
        return repo_auth_custom_exception_handler

    def create(self, request, *args, **kwargs):
        # Create commit
        create_commit_data = dict(
            branch=request.data.get("branch"),
            commit_sha=request.data.get("commit_sha"),
            fail_on_error=True,
            git_service=request.data.get("git_service"),
            parent_sha=request.data.get("parent_sha"),
            pull_request_number=request.data.get("pull_request_number"),
            slug=request.data.get("slug"),
            token=request.data.get("token"),
        )
        commit_serializer = CommitSerializer(data=create_commit_data)
        commit_serializer.is_valid(raise_exception=True)

        repository = self.get_repo()
        commit = self.create_commit(commit_serializer, repository)

        # Create report
        commit_report_data = dict(
            code=request.data.get("code"),
            commit_sha=request.data.get("commit_sha"),
            fail_on_error=True,
            git_service=request.data.get("git_service"),
            slug=request.data.get("slug"),
            token=request.data.get("token"),
        )
        commit_report_serializer = CommitReportSerializer(data=commit_report_data)
        report = self.create_report(commit_report_serializer, repository, commit)

        # Do upload
        upload_data = dict(
            branch=request.data.get("branch"),
            build_code=request.data.get("build_code"),
            build_url=request.data.get("build_url"),
            commit_sha=request.data.get("commit_sha"),
            disable_file_fixes=request.data.get("disable_file_fixes"),
            disable_search=request.data.get("disable_search"),
            dry_run=request.data.get("dry_run"),
            env_vars=request.data.get("env_vars"),
            fail_on_error=request.data.get("fail_on_error"),
            files_search_exclude_folders=request.data.get(
                "files_search_exclude_folders"
            ),
            files_search_explicitly_listed_files=request.data.get(
                "files_search_explicitly_listed_files"
            ),
            files_search_root_folder=request.data.get("files_search_root_folder"),
            flags=request.data.get("flags"),
            gcov_args=request.data.get("gcov_args"),
            gcov_executable=request.data.get("gcov_executable"),
            gcov_ignore=request.data.get("gcov_ignore"),
            gcov_include=request.data.get("gcov_include"),
            git_service=request.data.get("git_service"),
            handle_no_reports_found=request.data.get("handle_no_reports_found"),
            job_code=request.data.get("job_code"),
            name=request.data.get("name"),
            network_filter=request.data.get("network_filter"),
            network_prefix=request.data.get("network_prefix"),
            network_root_folder=request.data.get("network_root_folder"),
            plugin_names=request.data.get("plugin_names"),
            pull_request_number=request.data.get("pull_request_number"),
            report_code=report.code,
            report_type=request.data.get("report_type"),
            slug=request.data.get("slug"),
            swift_project=request.data.get("swift_project"),
            token=request.data.get("token"),
            use_legacy_uploader=request.data.get("use_legacy_uploader"),
        )
        upload_serializer = UploadSerializer(data=upload_data)
        upload_serializer.is_valid(raise_exception=True)

        instance = self.create_upload(upload_serializer, repository, commit, report)
        if instance:
            return Response(data=instance.data, status=status.HTTP_201_CREATED)
        else:
            return Response(
                upload_serializer.errors, status=status.HTTP_400_BAD_REQUEST
            )
