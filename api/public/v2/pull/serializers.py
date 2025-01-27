from rest_framework import serializers

from api.public.v2.owner.serializers import OwnerSerializer
from api.shared.commit.serializers import CommitTotalsSerializer
from compare.models import CommitComparison
from core.models import Pull, PullStates
from services.comparison import ComparisonReport


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

    def get_patch(self, obj: Pull):
        # 1) Fetch the CommitComparison for (compared_to, head)
        comparison_qs = CommitComparison.objects.filter(
            base_commit__commitid=obj.compared_to,
            compare_commit__commitid=obj.head,
            base_commit__repository_id=obj.repository_id,
            compare_commit__repository_id=obj.repository_id,
        ).select_related("compare_commit", "base_commit")

        commit_comparison = comparison_qs.first()
        if not commit_comparison or not commit_comparison.is_processed:
            return None

        # 2) Wrap it in ComparisonReport
        cr = ComparisonReport(commit_comparison)

        # 3) Summation of patch coverage across impacted files
        hits = misses = partials = 0
        for f in cr.impacted_files:
            pc = f.patch_coverage
            if pc:
                hits += pc.hits
                misses += pc.misses
                partials += pc.partials

        total_branches = hits + misses + partials
        if total_branches == 0:
            return None

        return dict(
            hits=hits,
            misses=misses,
            partials=partials,
            coverage=100 * hits / total_branches,
        )
