import logging

from rest_framework import viewsets
from rest_framework.decorators import action
from rest_framework.exceptions import NotFound
from rest_framework.response import Response

from api.shared.mixins import CompareSlugMixin
from api.shared.permissions import RepositoryArtifactPermissions
from compare.models import CommitComparison
from services.comparison import (
    CommitComparisonService,
    Comparison,
    MissingComparisonCommit,
    MissingComparisonReport,
    PullRequestComparison,
)
from services.decorators import torngit_safe
from services.task import TaskService

from .serializers import (
    FileComparisonSerializer,
    FlagComparisonSerializer,
    ImpactedFilesComparisonSerializer,
    ImpactedFileSegmentsSerializer,
)

log = logging.getLogger(__name__)


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

    def get_or_create_commit_comparison(
        self, comparison: Comparison
    ) -> CommitComparison:
        """
        Retrieves the pre-computed CommitComparison
        if not found will create one and return None
        """
        commit_comparison = CommitComparisonService.fetch_precomputed(
            comparison.head_commit.repository_id,
            [(comparison.base_commit.commitid, comparison.head_commit.commitid)],
        )

        # Can't use pre-computed impacted files from CommitComparison
        # first trigger a Celery task to create a comparison for this commit pair for the future
        if not commit_comparison:
            new_comparison = CommitComparison(
                base_commit=comparison.base_commit,
                compare_commit=comparison.head_commit,
                state=CommitComparison.CommitComparisonStates.PENDING,
            )
            new_comparison.save()
            TaskService().compute_comparison(new_comparison.pk)
            log.info(
                "CommitComparison not found, creating and request to compute new entry"
            )
            return new_comparison
        return commit_comparison[0]

    @torngit_safe
    def retrieve(self, request, *args, **kwargs):
        comparison = self.get_object()

        # Some checks here for pseudo-comparisons. Basically, when pseudo-comparing,
        # we sometimes might need to tweak the base report
        if isinstance(comparison, PullRequestComparison):
            if comparison.pseudo_diff_adjusts_tracked_lines:
                comparison.update_base_report_with_pseudo_diff()
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

    @action(detail=False, methods=["get"])
    @torngit_safe
    def impacted_files(self, request, *args, **kwargs):
        comparison = self.get_object()
        return Response(
            ImpactedFilesComparisonSerializer(
                comparison,
                context={
                    "commit_comparison": self.get_or_create_commit_comparison(
                        comparison
                    )
                },
            ).data
        )

    @action(detail=False, methods=["get"])
    @torngit_safe
    def segments(self, request, *args, **kwargs):
        file_path = file_path = kwargs.get("file_path")
        comparison = self.get_object()

        return Response(
            ImpactedFileSegmentsSerializer(
                file_path, context={"comparison": comparison}
            ).data
        )
