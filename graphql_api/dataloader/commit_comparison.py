import functools
import operator

from django.db.models import Q

from compare.models import CommitComparison

from .loader import BaseLoader


class CommitComparisonLoader(BaseLoader):
    @classmethod
    def key(cls, commit_comparison):
        return (
            commit_comparison.base_commit.commitid,
            commit_comparison.compare_commit.commitid,
        )

    def batch_queryset(self, keys):
        # TODO: can we generate SQL like "WHERE (base_commitid, compare_commitid) IN ((1, 2), (3, 4))" instead?
        filter = functools.reduce(
            operator.or_,
            [
                Q(base_commit__commitid=base_id, compare_commit__commitid=compare_id)
                for base_id, compare_id in keys
            ],
        )

        return CommitComparison.objects.filter(filter).prefetch_related(
            "base_commit", "compare_commit"
        )
