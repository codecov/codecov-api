from asgiref.sync import sync_to_async

from compare.models import CommitComparison
from core.models import Commit
from services.comparison import recalculate_comparison

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
        queryset = self.batch_queryset(keys)
        comparisons = {self.key(record): record for record in queryset}

        # create missing comparisons
        missing_keys = set(keys) - set(comparisons.keys())
        created_comparisons = self._create_missing_comparisons(
            missing_keys, commit_cache
        )
        for comparison in created_comparisons:
            key = (
                comparison.base_commit.commitid,
                comparison.compare_commit.commitid,
            )
            comparisons[key] = comparison

        # return comparisons in order
        results = [comparisons.get(key) for key in keys]
        self._refresh_comparisons(results, commit_cache)
        return results

    def _create_missing_comparisons(self, keys, commit_cache):
        """
        Create new comparisons for the given keys.
        """
        created_comparisons = CommitComparison.objects.bulk_create(
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
            ]
        )
        for comparison in created_comparisons:
            comparison.base_commit = commit_cache.get_by_pk(comparison.base_commit_id)
            comparison.compare_commit = commit_cache.get_by_pk(
                comparison.compare_commit_id
            )
            recalculate_comparison(comparison)

        return created_comparisons

    def _refresh_comparisons(self, comparisons, commit_cache):
        """
        Make sure all the given comparison calculations are up-to-date.
        """
        for comparison in comparisons:
            if comparison:
                comparison.base_commit = commit_cache.get_by_pk(
                    comparison.base_commit_id
                )
                comparison.compare_commit = commit_cache.get_by_pk(
                    comparison.compare_commit_id
                )
                if comparison.needs_recalculation:
                    recalculate_comparison(comparison)
