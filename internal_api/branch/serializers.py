from rest_framework import serializers

from core.models import Branch, Commit
from internal_api.owner.serializers import OwnerSerializer


class BranchCommitSerializer(serializers.ModelSerializer):
    author = OwnerSerializer()
    totals = serializers.JSONField()
    updatestamp = serializers.DateTimeField()

    class Meta:
        model = Commit
        fields = ('author', 'totals', 'updatestamp')


class BranchSerializer(serializers.ModelSerializer):
    name = serializers.CharField()
    head = serializers.SerializerMethodField()
    updatestamp = serializers.DateTimeField()

    def get_head(self, branch):
        commit = Commit.objects.get(commitid=branch.head_id, repository=branch.repository)
        return BranchCommitSerializer(commit).data

    class Meta:
        model = Branch
        fields = ('name', 'head', 'updatestamp')
