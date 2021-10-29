from aiodataloader import DataLoader
from asgiref.sync import sync_to_async

from codecov_auth.models import Owner


class OwnerLoader(DataLoader):
    @sync_to_async
    def batch_load_fn(self, ids):
        # Need to return a list of owners in the same order as the ids
        # So fetching in bulk and generate a list based on ids
        owners = Owner.objects.in_bulk(ids, field_name="ownerid")
        return [owners.get(id) for id in ids]


CONTEXT_KEY = "__owner_loader"


def load_owner_by_id(info, id):
    if CONTEXT_KEY not in info.context:
        # One loader per HTTP request that we init when we need it
        info.context[CONTEXT_KEY] = OwnerLoader()

    return info.context[CONTEXT_KEY].load(id)
