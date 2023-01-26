from typing import List, Optional

from drf_spectacular.types import OpenApiTypes
from drf_spectacular.utils import OpenApiParameter, extend_schema
from rest_framework import mixins, viewsets
from rest_framework.authentication import BasicAuthentication, SessionAuthentication
from rest_framework.exceptions import NotFound
from rest_framework.response import Response

from api.public.v2.report.serializers import CoverageReportSerializer
from api.public.v2.schema import repo_parameters
from api.shared.mixins import RepoPropertyMixin
from api.shared.permissions import RepositoryArtifactPermissions, SuperTokenPermissions
from codecov_auth.authentication import (
    CodecovTokenAuthentication,
    SuperTokenAuthentication,
    UserTokenAuthentication,
)
from services.components import Component, commit_components, component_filtered_report
from services.path import dashboard_commit_file_url


@extend_schema(
    parameters=repo_parameters
    + [
        OpenApiParameter(
            "sha",
            OpenApiTypes.STR,
            OpenApiParameter.QUERY,
            description="commit SHA for which to return report",
        ),
        OpenApiParameter(
            "branch",
            OpenApiTypes.STR,
            OpenApiParameter.QUERY,
            description="branch name for which to return report (of head commit)",
        ),
        OpenApiParameter(
            "path",
            OpenApiTypes.STR,
            OpenApiParameter.QUERY,
            description="filter report to only include file paths starting with this value",
        ),
        OpenApiParameter(
            "flag",
            OpenApiTypes.STR,
            OpenApiParameter.QUERY,
            description="filter report to only include info pertaining to given flag name",
        ),
        OpenApiParameter(
            "component_id",
            OpenApiTypes.STR,
            OpenApiParameter.QUERY,
            description="filter report to only include info pertaining to given component id",
        ),
    ],
    tags=["Coverage"],
)
class ReportViewSet(
    viewsets.GenericViewSet, mixins.RetrieveModelMixin, RepoPropertyMixin
):
    serializer_class = CoverageReportSerializer
    authentication_classes = [
        SuperTokenAuthentication,
        CodecovTokenAuthentication,
        UserTokenAuthentication,
        BasicAuthentication,
        SessionAuthentication,
    ]
    permission_classes = [SuperTokenPermissions | RepositoryArtifactPermissions]

    def get_object(self):
        commit = self.get_commit()
        report = commit.full_report

        path = self.request.query_params.get("path", None)
        if path:
            paths = [file for file in report.files if file.startswith(path)]
            if not paths:
                raise NotFound(
                    f"The file path '{path}' does not exist. Please provide an existing file path.",
                    404,
                )
            report = report.filter(paths=paths)

        flag = self.request.query_params.get("flag", None)
        if flag:
            report = report.filter(flags=[flag])

        component_id = self.request.query_params.get("component_id", None)
        if component_id:
            component = next(
                (
                    component
                    for component in commit_components(commit, self.request.user)
                    if component.component_id == component_id
                ),
                None,
            )
            if component is None:
                raise NotFound(
                    f"The component {component_id} does not exist in commit {commit.commitid}",
                    404,
                )
            report = component_filtered_report(report, component)

        # Add commit url to report object
        service, owner, repo = (
            self.kwargs["service"],
            self.kwargs["owner_username"],
            self.kwargs["repo_name"],
        )
        commit_file_url = dashboard_commit_file_url(
            path=path,
            service=service,
            owner=owner,
            repo=repo,
            commit_sha=commit.commitid,
        )
        report.commit_file_url = commit_file_url

        return report

    @extend_schema(summary="Commit coverage report")
    def retrieve(self, request, *args, **kwargs):
        """
        Returns the coverage report for a given commit.

        By default that commit is the head of the default branch but can also be specified explictily by:
        * `sha` - return report for the commit with the given SHA
        * `branch` - return report for the head commit of the branch with the given name

        The report can be optionally filtered by specifying:
        * `path` - only show report info for pathnames that start with this value
        * `flag` - only show report info that applies to the specified flag name
        * `component_id` - only show report info that applies to the specified component
        """
        try:
            report = self.get_object()
        except NotFound as inst:
            (detail, code) = inst.args
            raise NotFound(detail)

        serializer = self.get_serializer(report)
        return Response(serializer.data)
