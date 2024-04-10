from rest_framework import viewsets
from rest_framework.decorators import action
from rest_framework.exceptions import NotFound
from rest_framework.response import Response
from rest_framework.views import APIView

from api.shared.mixins import RepoPropertyMixin
from api.shared.permissions import RepositoryArtifactPermissions
from api.shared.report.serializers import TreeSerializer
from services.path import ReportPaths


class CoverageViewSet(viewsets.ViewSet, RepoPropertyMixin):
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
                f"The commit {commit_sha} is not in our records. Please specify valid commit.",
                404,
            )

        report = commit.full_report
        if report is None:
            raise NotFound(f"Coverage report for {commit_sha} not found")

        return report

    @action(
        detail=False,
        methods=["get"],
        url_path="tree",
    )
    def tree(self, request, *args, **kwargs):
        flags = request.query_params.get("flags")  # Optional flags parameter
        components = request.query_params.get("components")  # Optional components parameter
        report = self.get_object()

        paths = ReportPaths(report = report, filter_flags=flags, filter_paths=components)
        serializer = TreeSerializer(paths.single_directory(), many=True)
        return Response(serializer.data)
