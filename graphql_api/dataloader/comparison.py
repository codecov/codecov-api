from codecov.db import sync_to_async
from compare.models import CommitComparison
from core.models import Commit
from services.comparison import CommitComparisonService
from services.task import TaskService

from .commit import CommitLoader
from .loader import BaseLoader

comparison_table = CommitComparison._meta.db_table
commit_table = Commit._meta.db_table


class CommitCache:
    def __init__(self, commits):
        self.commits = [commit for commit in commits if commit]
        self._by_pk = {commit.pk: commit for commit in self.commits}
        self._by_commitid = {commit.commitid: commit for commit in self.commits}

    def get_by_pk(self, pk):
        return self._by_pk.get(pk)

    def get_by_commitid(self, commitid):
        return self._by_commitid.get(commitid)


class ComparisonLoader(BaseLoader):
    @classmethod
    def key(cls, commit_comparison):
        return (commit_comparison.base_commitid, commit_comparison.compare_commitid)

    def __init__(self, info, repository_id, *args, **kwargs):
        self.repository_id = repository_id
        return super().__init__(info, *args, **kwargs)

    def batch_queryset(self, keys):
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
        )

    async def batch_load_fn(self, keys):
        # flat list of all commits involved in all comparisons
        commitids = set(commitid for key in keys for commitid in key)

        commit_loader = CommitLoader.loader(self.info, self.repository_id)
        commits = await commit_loader.load_many(commitids)

        commit_cache = CommitCache(commits)

        return await self._load_comparisons(keys, commit_cache)

    @sync_to_async
    def _load_comparisons(self, keys, commit_cache):
        # initial fetch of comparisons (we may be missing some at this point)
        queryset = self.batch_queryset(keys)
        comparisons = {self.key(record): record for record in queryset}

        # handle missing comparisons
        missing_keys = set(keys) - set(comparisons.keys())
        if len(missing_keys) > 0:
            # create comparisons for the missing keys
            for record in self._create_comparisons(missing_keys, commit_cache):
                comparisons[self.key(record)] = record

        # recalculate comparisons if needed
        self._refresh_comparisons(comparisons, missing_keys, commit_cache)

        # return comparisons in the same order as `keys`
        return [comparisons.get(key) for key in keys]

    def _create_comparisons(self, keys, commit_cache):
        """
        Insert new comparisons for the given keys (skipping insert of any duplicates).
        """
        CommitComparison.objects.bulk_create(
            [
                CommitComparison(
                    base_commit=commit_cache.get_by_commitid(base_commitid),
                    compare_commit=commit_cache.get_by_commitid(compare_commitid),
                )
                for (base_commitid, compare_commitid) in keys
                if base_commitid
                and commit_cache.get_by_commitid(base_commitid)
                and compare_commitid
                and commit_cache.get_by_commitid(compare_commitid)
            ],
            ignore_conflicts=True,
        )

        # refetch missing comparisons (since they cannot be returned from the create call abbove)
        return self.batch_queryset(keys)

    def _refresh_comparisons(self, comparisons, missing_keys, commit_cache):
        """
        Recalculate comparisons for newly added or out-of-date comparisons.
        """
        comparison_ids = []
        for key, comparison in comparisons.items():
            comparison.base_commit = commit_cache.get_by_pk(comparison.base_commit_id)
            comparison.compare_commit = commit_cache.get_by_pk(
                comparison.compare_commit_id
            )

            commit_comparison_service = CommitComparisonService(comparison)
            if key in missing_keys or commit_comparison_service.needs_recompute():
                comparison_ids.append(comparison.pk)
                commit_comparison_service.commit_comparison.state = (
                    CommitComparison.CommitComparisonStates.PENDING
                )

        if len(comparison_ids) > 0:
            CommitComparison.objects.filter(pk__in=comparison_ids).update(
                state=CommitComparison.CommitComparisonStates.PENDING
            )
            TaskService().compute_comparisons(comparison_ids)
