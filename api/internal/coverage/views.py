from rest_framework import viewsets
from rest_framework.decorators import action
from rest_framework.exceptions import NotFound
from rest_framework.response import Response
from rest_framework.views import APIView

from api.shared.mixins import RepoPropertyMixin
from api.shared.permissions import RepositoryArtifactPermissions
from api.shared.report.serializers import TreeSerializer
from services.path import ReportPaths
from utils.temp_branch_fix import get_or_update_branch_head


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
            commit_sha = get_or_update_branch_head(
                self.repo.commits, branch, self.repo.repoid
            )
            if commit_sha is None:
                raise NotFound(
                    f"The head of this branch '{branch_name}' is not in our records. Please specify a valid branch name.",
                    404,
                )

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
        report = self.get_object()
        paths = ReportPaths(report)
        serializer = TreeSerializer(paths.single_directory(), many=True)
        return Response(serializer.data)
