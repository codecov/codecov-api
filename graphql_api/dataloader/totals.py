from os import sync
from aiodataloader import DataLoader
from asgiref.sync import sync_to_async

from core.models import Commit

class TotalsLoader(DataLoader):

    def __init__(self, repository_id, *args, **kwargs):
        self.repository_id = repository_id
        return super().__init__(*args, **kwargs)

    @sync_to_async
    def batch_load_fn(self, ids):
        queryset = {commit.commitid: commit for commit in Commit.objects.filter(commitid__in=ids, repository_id=self.repository_id)}
        return [queryset.get(commit_id).commitreport.reportleveltotals for commit_id in ids]


def load_totals_by_id(info, commit_id, repository_id):
    CONTEXT_KEY = f"__totals_loader_{repository_id}"
    if CONTEXT_KEY not in info.context:
        # One loader per HTTP request that we init when we need it
        info.context[CONTEXT_KEY] = TotalsLoader(repository_id)

    return info.context[CONTEXT_KEY].load(commit_id)
