from rest_framework import mixins, viewsets
from rest_framework.decorators import action
from rest_framework.exceptions import NotFound, PermissionDenied
from rest_framework.response import Response

from api.shared.mixins import CompareSlugMixin
from api.shared.permissions import RepositoryArtifactPermissions
from services.comparison import (
    Comparison,
    MissingComparisonCommit,
    MissingComparisonReport,
    PullRequestComparison,
)
from services.decorators import torngit_safe

from .serializers import FileComparisonSerializer, FlagComparisonSerializer


class CompareViewSetMixin(CompareSlugMixin, viewsets.GenericViewSet):
    permission_classes = [RepositoryArtifactPermissions]

    def get_object(self) -> Comparison:
        compare_data = self.get_compare_data()

        if "pull" in compare_data:
            comparison = PullRequestComparison(
                user=self.request.current_owner,
                pull=compare_data["pull"],
            )
            try:
                # make sure we have a base and head commit
                comparison.base_commit
                comparison.head_commit
            except MissingComparisonCommit:
                raise NotFound("Sorry, we are missing a commit for that pull request.")
        else:
            comparison = Comparison(
                user=self.request.current_owner,
                base_commit=compare_data["base"],
                head_commit=compare_data["head"],
            )

        return comparison

    @torngit_safe
    def retrieve(self, request, *args, **kwargs):
        comparison = self.get_object()

        # Some checks here for pseudo-comparisons. Basically, when pseudo-comparing,
        # we sometimes might need to tweak the base report if the user allows us to
        # in their yaml, or raise an error if not.
        if isinstance(comparison, PullRequestComparison):
            if (
                comparison.pseudo_diff_adjusts_tracked_lines
                and comparison.allow_coverage_offsets
            ):
                comparison.update_base_report_with_pseudo_diff()
            elif comparison.pseudo_diff_adjusts_tracked_lines:
                return Response(
                    data={
                        "detail": f"Changes found in between %.7s...%.7s (pseudo...base) "
                        f"which prevent comparing this pull request."
                        % (comparison.pull.compared_to, comparison.pull.base)
                    },
                    status=400,
                )
        serializer = self.get_serializer(comparison)

        try:
            return Response(serializer.data)
        except MissingComparisonReport:
            raise NotFound("Raw report not found for base or head reference.")

    @action(
        detail=False,
        methods=["get"],
        url_path="file/(?P<file_path>.+)",
        url_name="file",
    )
    @torngit_safe
    def file(self, request, *args, **kwargs):
        comparison = self.get_object()
        file_path = file_path = kwargs.get("file_path")
        if file_path not in comparison.head_report:
            raise NotFound("File not found in head report.")
        return Response(
            FileComparisonSerializer(
                comparison.get_file_comparison(
                    file_path, with_src=True, bypass_max_diff=True
                )
            ).data
        )

    @action(detail=False, methods=["get"])
    @torngit_safe
    def flags(self, request, *args, **kwargs):
        comparison = self.get_object()
        flags = [
            comparison.flag_comparison(flag_name)
            for flag_name in comparison.non_carried_forward_flags
        ]
        return Response(FlagComparisonSerializer(flags, many=True).data)
