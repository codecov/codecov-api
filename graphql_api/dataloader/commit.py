from core.models import Commit

from .loader import BaseLoader


class CommitLoader(BaseLoader):
    @classmethod
    def key(cls, commit):
        return commit.commitid

    def __init__(self, repository_id, *args, **kwargs):
        self.repository_id = repository_id
        return super().__init__(*args, **kwargs)

    def batch_queryset(self, keys):
        return Commit.objects.filter(
            commitid__in=keys, repository_id=self.repository_id
        )
