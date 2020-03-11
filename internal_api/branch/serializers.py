from rest_framework import serializers

from core.models import Branch, Commit
from internal_api.owner.serializers import OwnerSerializer


class BranchSerializer(serializers.ModelSerializer):
    name = serializers.CharField()
    most_recent_commiter = serializers.SerializerMethodField()
    updatestamp = serializers.DateTimeField()

    def get_most_recent_commiter(self, branch):
        return Commit.objects.filter(
            commitid=branch.head,
            repository=branch.repository
        ).values_list('author__username', flat=True).get()

    class Meta:
        model = Branch
        fields = ('name', 'most_recent_commiter', 'updatestamp')
