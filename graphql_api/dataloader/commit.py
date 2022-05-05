from aiodataloader import DataLoader
from asgiref.sync import sync_to_async

from core.models import Commit


class CommitLoader(DataLoader):
    def __init__(self, repository_id, *args, **kwargs):
        self.repository_id = repository_id
        return super().__init__(*args, **kwargs)

    @sync_to_async
    def batch_load_fn(self, ids):
        # Need to return a list of commits in the same order as the ids
        # So fetching in bulk and generate a list based on ids
        queryset = {
            commit.commitid: commit
            for commit in Commit.objects.filter(
                commitid__in=ids, repository_id=self.repository_id
            )
        }
        return [queryset.get(commit_id) for commit_id in ids]


def load_commit_by_id(info, commit_id, repository_id):
    CONTEXT_KEY = f"__commit_loader_{repository_id}"
    if CONTEXT_KEY not in info.context:
        # One loader per HTTP request that we init when we need it
        info.context[CONTEXT_KEY] = CommitLoader(repository_id)

    return info.context[CONTEXT_KEY].load(commit_id)
