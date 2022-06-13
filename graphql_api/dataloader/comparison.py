from asgiref.sync import sync_to_async
from django.db.models import Prefetch

from compare.models import CommitComparison
from core.models import Commit
from reports.models import CommitReport
from services.comparison import recalculate_comparison

from .loader import BaseLoader

comparison_table = CommitComparison._meta.db_table
commit_table = Commit._meta.db_table


class ComparisonLoader(BaseLoader):
    @classmethod
    def key(cls, commit_comparison):
        return (commit_comparison.base_commitid, commit_comparison.compare_commitid)

    def __init__(self, repository_id, *args, **kwargs):
        self.repository_id = repository_id
        return super().__init__(*args, **kwargs)

    def batch_queryset(self, keys):
        # prefetch the CommitReport with the ReportLevelTotals
        reports_prefetch = Prefetch(
            "reports", queryset=CommitReport.objects.select_related("reportleveltotals")
        )

        return CommitComparison.objects.raw(
            f"""
            select
                {comparison_table}.*,
                base_commit.commitid as base_commitid,
                compare_commit.commitid as compare_commitid
            from {comparison_table}
            inner join {commit_table} base_commit
                on base_commit.id = {comparison_table}.base_commit_id and base_commit.repoid = {self.repository_id}
            inner join {commit_table} compare_commit
                on compare_commit.id = {comparison_table}.compare_commit_id and compare_commit.repoid = {self.repository_id}
            where (base_commit.commitid, compare_commit.commitid) in %s
        """,
            [tuple(keys)],
        ).prefetch_related(
            Prefetch(
                "base_commit",
                queryset=Commit.objects.prefetch_related(reports_prefetch),
            ),
            Prefetch(
                "compare_commit",
                queryset=Commit.objects.prefetch_related(reports_prefetch),
            ),
        )

    @sync_to_async
    def batch_load_fn(self, keys):
        queryset = self.batch_queryset(keys)
        comparisons = {self.key(record): record for record in queryset}

        # keys for comparisons that were not found
        missing_keys = set(keys) - set(comparisons.keys())

        # commits relevant to the missing comparisons
        commit_queryset = Commit.objects.filter(
            repository_id=self.repository_id,
            commitid__in=set(commitid for key in missing_keys for commitid in key),
        )
        commits_by_commitid = {commit.commitid: commit for commit in commit_queryset}
        commits_by_pk = {commit.pk: commit for commit in commit_queryset}

        # create missing comparisons
        created_comparisons = CommitComparison.objects.bulk_create(
            [
                CommitComparison(
                    base_commit=commits_by_commitid[base_commitid],
                    compare_commit=commits_by_commitid[compare_commitid],
                )
                for (base_commitid, compare_commitid) in missing_keys
                if base_commitid
                and commits_by_commitid[base_commitid]
                and compare_commitid
                and commits_by_commitid[compare_commitid]
            ]
        )
        for comparison in created_comparisons:
            comparison.base_commit = commits_by_pk[comparison.base_commit_id]
            comparison.compare_commit = commits_by_pk[comparison.compare_commit_id]
            key = (
                comparison.base_commit.commitid,
                comparison.compare_commit.commitid,
            )
            comparisons[key] = comparison
            recalculate_comparison(comparison)

        # return comparisons in order
        results = [comparisons.get(key) for key in keys]
        for comparison in results:
            if comparison and comparison.needs_recalculation:
                recalculate_comparison(comparison)
        return results
