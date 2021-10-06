from aiodataloader import DataLoader
from asgiref.sync import sync_to_async

from core.models import Repository

class RepositoryLoader(DataLoader):

    @sync_to_async
    def batch_load_fn(self, ids):
        # Need to return a list of repositories in the same order as the ids
        # So fetching in bulk and generate a list based on ids
        repositories = Repository.objects.in_bulk(ids, field_name='repository_id')
        return [repositories.get(id) for id in ids]


CONTEXT_KEY = "__repository_loader"

def load_repository_by_id(info, id):
    if CONTEXT_KEY not in info.context:
        # One loader per HTTP request that we init when we need it
        info.context[CONTEXT_KEY] = RepositoryLoader()

    return info.context[CONTEXT_KEY].load(id)
