from typing import Dict, Optional

from rest_framework import serializers

from api.public.v2.owner.serializers import OwnerSerializer
from api.shared.commit.serializers import (
    CommitTotalsSerializer,
    PatchCoverageSerializer,
)
from core.models import Pull, PullStates
from services.comparison import CommitComparisonService, ComparisonReport


class PullSerializer(serializers.ModelSerializer):
    pullid = serializers.IntegerField(label="pull ID number")
    title = serializers.CharField(label="title of the pull")
    base_totals = CommitTotalsSerializer(label="coverage totals of base commit")
    head_totals = CommitTotalsSerializer(label="coverage totals of head commit")
    updatestamp = serializers.DateTimeField(label="last updated timestamp")
    state = serializers.ChoiceField(
        label="state of the pull", choices=PullStates.choices
    )
    ci_passed = serializers.BooleanField(
        label="indicates whether the CI process passed for the head commit of this pull"
    )
    author = OwnerSerializer(label="pull author")
    patch = serializers.SerializerMethodField()

    class Meta:
        model = Pull
        read_only_fields = (
            "pullid",
            "title",
            "base_totals",
            "head_totals",
            "updatestamp",
            "state",
            "ci_passed",
            "author",
            "patch",
        )
        fields = read_only_fields

    def get_patch(self, obj: Pull) -> Optional[Dict[str, float]]:
        commit_comparison = CommitComparisonService.get_commit_comparison_for_pull(obj)
        if not commit_comparison or not commit_comparison.is_processed:
            return None
        cr = ComparisonReport(commit_comparison)
        hits = misses = partials = 0
        for f in cr.impacted_files:
            pc = f.patch_coverage
            if pc:
                hits += pc.hits
                misses += pc.misses
                partials += pc.partials
        total_branches = hits + misses + partials
        coverage = 0.0
        if total_branches != 0:
            coverage = round(100 * hits / total_branches, 2)
        data = dict(
            hits=hits,
            misses=misses,
            partials=partials,
            coverage=coverage,
        )
        return PatchCoverageSerializer(data).data
