from aiodataloader import DataLoader
from asgiref.sync import sync_to_async

from core.models import Commit

class CommitLoader(DataLoader):

    @sync_to_async
    def batch_load_fn(self, ids):
        # Need to return a list of commits in the same order as the ids
        # So fetching in bulk and generate a list based on ids
        commits = Commit.objects.in_bulk(ids, field_name='commitid')
        return [commits.get(id) for id in ids]


CONTEXT_KEY = "__commit_loader"

def load_commit_by_id(info, id):
    if CONTEXT_KEY not in info.context:
        # One loader per HTTP request that we init when we need it
        info.context[CONTEXT_KEY] = CommitLoader()

    return info.context[CONTEXT_KEY].load(id)
