import asyncio

from rest_framework import generics

from compare.services import Comparison
from internal_api.compare.serializers import CommitsComparisonSerializer
from internal_api.mixins import CompareSlugMixin


class CompareCommits(CompareSlugMixin, generics.RetrieveAPIView):
    serializer_class = CommitsComparisonSerializer

    def get_object(self):
        asyncio.set_event_loop(asyncio.new_event_loop())
        base, head = self.get_commits()
        report = Comparison(base_commit=base, head_commit=head, user=self.request.user)
        return {
            'commit_uploads': report.upload_commits,
            'git_commits': report.git_commits
        }
