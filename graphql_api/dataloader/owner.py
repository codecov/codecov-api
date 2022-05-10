from codecov_auth.models import Owner

from .loader import BaseLoader


class OwnerLoader(BaseLoader):
    @classmethod
    def key(cls, owner):
        return owner.ownerid

    def batch_queryset(self, keys):
        return Owner.objects.filter(ownerid__in=keys)
