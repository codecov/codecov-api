from rest_framework import mixins, viewsets
from rest_framework.response import Response

from api.public.v2.commit.serializers import ReportSerializer
from api.shared.mixins import RepoPropertyMixin
from api.shared.permissions import RepositoryArtifactPermissions


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
            commit_sha = branch.head

        commit = self.repo.commits.filter(commitid=commit_sha).first()

        report = commit.full_report

        path = self.request.query_params.get("path", None)
        if path:
            paths = [file for file in report.files if file.startswith(path)]
            report = report.filter(paths=paths)

        flag = self.request.query_params.get("flag", None)
        if flag:
            report = report.filter(flags=[flag])

        return report

    def retrieve(self, request, *args, **kwargs):
        report = self.get_object()
        serializer = self.get_serializer(report)
        return Response(serializer.data)
