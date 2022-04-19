from aiodataloader import DataLoader
from asgiref.sync import sync_to_async
from django.db.models import Prefetch

from core.models import Commit
from reports.models import CommitReport


class CommitLoader(DataLoader):
    def __init__(self, repository_id, *args, **kwargs):
        self.repository_id = repository_id
        return super().__init__(*args, **kwargs)

    @sync_to_async
    def batch_load_fn(self, ids):
        queryset = Commit.objects.filter(
            commitid__in=ids, repository_id=self.repository_id
        ).prefetch_related(
            Prefetch(
                "reports",
                queryset=CommitReport.objects.select_related("reportleveltotals"),
            )
        )

        # Need to return a list of commits in the same order as the ids
        # So fetching in bulk and generate a list based on ids
        results = {commit.commitid: commit for commit in queryset}
        return [results.get(commit_id) for commit_id in ids]


def commit_loader(info, repository_id):
    CONTEXT_KEY = f"__commit_loader_{repository_id}"
    if CONTEXT_KEY not in info.context:
        # One loader per HTTP request that we init when we need it
        info.context[CONTEXT_KEY] = CommitLoader(repository_id)
    return info.context[CONTEXT_KEY]


def load_commit_by_id(info, commit_id, repository_id):
    return commit_loader(info, repository_id).load(commit_id)


def cache_commit_by_id(info, repository_id, commit):
    loader = commit_loader(info, repository_id)
    loader.prime(commit.id, commit)
