from rest_framework import viewsets
from rest_framework.decorators import action
from rest_framework.exceptions import NotFound
from rest_framework.response import Response

from api.shared.mixins import RepoPropertyMixin
from api.shared.permissions import RepositoryArtifactPermissions
from api.shared.report.serializers import TreeSerializer
import services.components as components_service
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
                    f"The branch '{branch_name}' is not in our records. Please provide a valid branch name.",
                    404,
                )
            commit_sha = branch.head

        commit = self.repo.commits.filter(commitid=commit_sha).first()
        if commit is None:
            raise NotFound(
                f"The commit {commit_sha} is not in our records. Please specify a valid commit.",
                404,
            )

        report = commit.full_report
        if report is None:
            raise NotFound(f"Coverage report for {commit_sha} not found")

        components = self.request.query_params.getlist("components")
        component_paths = []
        if components:
            all_components = components_service.commit_components(
                commit, self.request.user
            )
            filtered_components = components_service.filter_components_by_name(
                all_components, components
            )
            for component in filtered_components:
                component_paths.extend(component.paths)

        flags = self.request.query_params.getlist("flags")

        paths = ReportPaths(
            report=report, filter_flags=flags, filter_paths=component_paths
        )

        return paths

    @action(detail=False, methods=["get"], url_path="tree")
    def tree(self, request, *args, **kwargs):
        paths = self.get_object()
        serializer = TreeSerializer(paths.single_directory(), many=True)
        return Response(serializer.data)
