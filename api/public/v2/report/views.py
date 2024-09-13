from typing import Optional

from drf_spectacular.types import OpenApiTypes
from drf_spectacular.utils import OpenApiParameter, extend_schema
from rest_framework import mixins, viewsets
from rest_framework.authentication import BasicAuthentication, SessionAuthentication
from rest_framework.decorators import action
from rest_framework.exceptions import NotFound, ValidationError
from rest_framework.response import Response
from shared.reports.resources import Report
from shared.utils.match import match

from api.public.v2.report.serializers import (
    CoverageReportSerializer,
    FileReportSerializer,
)
from api.public.v2.schema import repo_parameters
from api.shared.mixins import RepoPropertyMixin
from api.shared.permissions import RepositoryArtifactPermissions, SuperTokenPermissions
from api.shared.report.serializers import TreeSerializer
from codecov_auth.authentication import (
    SuperTokenAuthentication,
    UserTokenAuthentication,
)
from core.models import Commit
from services.components import commit_components
from services.path import ReportPaths, dashboard_commit_file_url


class ReportMixin:
    def _commit_file_url(self, commit: Commit, path: str):
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
            commit=commit,
        )
        return commit_file_url


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
class BaseReportViewSet(
    viewsets.GenericViewSet, mixins.RetrieveModelMixin, RepoPropertyMixin, ReportMixin
):
    serializer_class = CoverageReportSerializer
    permission_classes = [RepositoryArtifactPermissions]

    def filter_report(
        self,
        commit: Commit,
        report: Report,
        path: Optional[str] = None,
        flag: Optional[str] = None,
        component_id: Optional[str] = None,
    ) -> Report:
        if component_id:
            component = next(
                (
                    component
                    for component in commit_components(commit, self.owner)
                    if component.component_id == component_id
                ),
                None,
            )
            if component is None:
                raise NotFound(
                    f"The component {component_id} does not exist in commit {commit.commitid}"
                )

            if path and not match(component.paths, path):
                # empty report since the path is not part of the component
                return Report()

            component_flags = component.get_matching_flags(report.flags.keys())
            if flag and len(component.flag_regexes) > 0 and flag not in component_flags:
                # empty report since the flag is not part of the component
                return Report()

        if path and flag:
            report = report.filter(flags=[flag], paths=[f"{path}.*"])
        elif path:
            report = report.filter(paths=[f"{path}.*"])
        elif flag:
            report = report.filter(flags=[flag])
        elif component_id:
            report = report.filter(flags=component_flags, paths=component.paths)

        if path and len(report.files) == 0:
            raise NotFound(f"No files or directories found matching path: {path}")

        return report

    def get_object(self):
        commit = self.get_commit()
        report = commit.full_report

        if report is None:
            raise NotFound(f"No coverage report found for commit {commit.commitid}")

        path = self.request.query_params.get("path", None)
        report = self.filter_report(
            commit,
            report,
            path=path,
            flag=self.request.query_params.get("flag", None),
            component_id=self.request.query_params.get("component_id", None),
        )

        # Add commit url to report object
        report.commit_file_url = self._commit_file_url(commit, path)

        return report

    def retrieve(self, request, *args, **kwargs):
        report = self.get_object()
        serializer = self.get_serializer(report)
        return Response(serializer.data)


class TotalsViewSet(BaseReportViewSet):
    def get_serializer_context(self, *args, **kwargs):
        context = super().get_serializer_context(*args, **kwargs)
        context.update({"include_line_coverage": False})
        return context

    @extend_schema(summary="Commit coverage totals")
    def retrieve(self, request, *args, **kwargs):
        """
        Returns the coverage totals for a given commit and the
        coverage totals broken down by file.

        By default that commit is the head of the default branch but can also be specified explictily by:
        * `sha` - return totals for the commit with the given SHA
        * `branch` - return totals for the head commit of the branch with the given name

        The totals can be optionally filtered by specifying:
        * `path` - only show totals for pathnames that start with this value
        * `flag` - only show totals that applies to the specified flag name
        * `component_id` - only show totals that applies to the specified component
        """
        return super().retrieve(request, *args, **kwargs)


class ReportViewSet(BaseReportViewSet):
    authentication_classes = [
        SuperTokenAuthentication,
        UserTokenAuthentication,
        BasicAuthentication,
        SessionAuthentication,
    ]
    permission_classes = [SuperTokenPermissions | RepositoryArtifactPermissions]

    def get_queryset(self):
        return None

    def get_serializer_context(self, *args, **kwargs):
        context = super().get_serializer_context(*args, **kwargs)
        context.update({"include_line_coverage": True})
        return context

    @extend_schema(summary="Commit coverage report")
    def retrieve(self, request, *args, **kwargs):
        """
        Similar to the coverage totals endpoint but also returns line-by-line
        coverage info (hit=0/miss=1/partial=2).

        By default that commit is the head of the default branch but can also be specified explictily by:
        * `sha` - return report for the commit with the given SHA
        * `branch` - return report for the head commit of the branch with the given name

        The report can be optionally filtered by specifying:
        * `path` - only show report info for pathnames that start with this value
        * `flag` - only show report info that applies to the specified flag name
        * `component_id` - only show report info that applies to the specified component
        """
        return super().retrieve(request, *args, **kwargs)

    @extend_schema(
        summary="Coverage report tree",
        parameters=[
            OpenApiParameter(
                "depth",
                OpenApiTypes.STR,
                OpenApiParameter.QUERY,
                description="depth of the traversal (default=1)",
            ),
            OpenApiParameter(
                "path",
                OpenApiTypes.STR,
                OpenApiParameter.QUERY,
                description="starting path of the traversal (default is root path)",
            ),
        ],
        responses={200: TreeSerializer},
    )
    @action(
        detail=False,
        methods=["get"],
        url_path="tree",
    )
    def tree(self, request, *args, **kwargs):
        """
        Returns a hierarchical view of the report that matches the file structure of the covered files
        with coverage info rollups at each level.

        Returns only top-level data by default but the depth of the traversal can be controlled via
        the `depth` parameter.

        * `depth` - how deep in the tree to traverse (default=1)
        * `path` - path in the tree from which to start the traversal (default is the root)
        """
        report = self.get_object()
        path = request.query_params.get("path")
        paths = ReportPaths(report, path=path)
        serializer = TreeSerializer(
            paths.single_directory(),
            many=True,
            context={
                "max_depth": int(request.query_params.get("depth", 1)),
            },
        )
        return Response(serializer.data)


@extend_schema(
    parameters=repo_parameters
    + [
        OpenApiParameter(
            "path",
            OpenApiTypes.STR,
            OpenApiParameter.PATH,
            description="the file path for which to retrieve coverage info",
        ),
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
    ],
    tags=["Coverage"],
)
class FileReportViewSet(
    viewsets.GenericViewSet, mixins.RetrieveModelMixin, RepoPropertyMixin, ReportMixin
):
    authentication_classes = [
        SuperTokenAuthentication,
        UserTokenAuthentication,
        BasicAuthentication,
        SessionAuthentication,
    ]
    permission_classes = [SuperTokenPermissions | RepositoryArtifactPermissions]
    serializer_class = FileReportSerializer

    def get_queryset(self):
        return None

    def get_object(self):
        self.path = self.kwargs.get("path")

        walk_back = int(self.request.query_params.get("walk_back", 0))
        if walk_back > 20:
            raise ValidationError("walk_back must be <= 20")

        self.commit = self.get_commit()
        report = self.commit.full_report

        oldest_sha = self.request.query_params.get("oldest_sha")

        for i in range(walk_back):
            if self._is_valid_commit(self.commit) and self._is_valid_report(
                report, self.path
            ):
                break
            else:
                # walk commit ancestors until we find coverage info for the given path
                if not self.commit.parent_commit_id:
                    report = None
                    break
                self.commit = self.repo.commits.filter(
                    commitid=self.commit.parent_commit_id
                ).first()
                if not self.commit:
                    report = None
                    break
                report = self.commit.full_report

                if oldest_sha and oldest_sha == self.commit.commitid:
                    break

        if not self._is_valid_report(report, self.path):
            raise NotFound(f"coverage info not found for path '{self.path}'")

        return report.get(self.path)

    def get_serializer_context(self, *args, **kwargs):
        context = super().get_serializer_context(*args, **kwargs)
        context.update(
            {
                "include_line_coverage": True,
                "commit_sha": self.commit.commitid,
                "commit_file_url": self._commit_file_url(self.commit, self.path),
            }
        )
        return context

    @extend_schema(summary="File coverage report")
    def retrieve(self, request, *args, **kwargs):
        """
        Similar to the coverage report endpoint but only returns coverage info for a single
        file specified by `path`.

        By default that commit is the head of the default branch but can also be specified explictily by:
        * `sha` - return report for the commit with the given SHA
        * `branch` - return report for the head commit of the branch with the given name
        """
        return super().retrieve(request, *args, **kwargs)

    def _is_valid_commit(self, commit: Commit) -> bool:
        return commit.state == Commit.CommitStates.COMPLETE

    def _is_valid_report(self, report: Report, path: str) -> bool:
        if report is None:
            return False

        report_file = report.get(path)
        if report_file is None:
            return False

        return True
