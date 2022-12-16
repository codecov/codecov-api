from drf_spectacular.types import OpenApiTypes
from drf_spectacular.utils import OpenApiParameter, extend_schema
from rest_framework import mixins, viewsets
from rest_framework.exceptions import NotFound
from rest_framework.response import Response

from api.public.v2.commit.serializers import ReportSerializer
from api.public.v2.schema import repo_parameters
from api.shared.mixins import RepoPropertyMixin
from api.shared.permissions import RepositoryArtifactPermissions


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
    ],
    tags=["Coverage"],
)
class ReportViewSet(
    viewsets.GenericViewSet, mixins.RetrieveModelMixin, RepoPropertyMixin
):
    serializer_class = ReportSerializer
    permission_classes = [RepositoryArtifactPermissions]

    def get_object(self):
        commit_sha = self.request.query_params.get("sha")
        if not commit_sha:
            branch_name = self.request.query_params.get("branch", self.repo.branch)
            branch = self.repo.branches.filter(name=branch_name).first()
            if branch is None:
                raise NotFound(
                    f"The branch '{branch_name}' in not in our records. Please provide a valid branch name.",
                    404,
                )
            commit_sha = branch.head

        commit = self.repo.commits.filter(commitid=commit_sha).first()
        if commit is None:
            raise NotFound(
                f"The commit {commit_sha} in not in our records. Please specify valid commit.",
                404,
            )

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
        """
        try:
            report = self.get_object()
        except NotFound as inst:
            (detail, code) = inst.args
            raise NotFound(detail)

        serializer = self.get_serializer(report)
        return Response(serializer.data)
