from rest_framework import serializers

from api.public.v2.commit.serializers import CommitDetailSerializer
from core.models import Branch, Commit


class BranchSerializer(serializers.ModelSerializer):
    name = serializers.CharField(label="branch name")
    updatestamp = serializers.DateTimeField(label="last updated timestamp")

    class Meta:
        model = Branch
        fields = ("name", "updatestamp")


class BranchDetailSerializer(BranchSerializer):
    head_commit = serializers.SerializerMethodField(
        label="branch's current head commit"
    )

    def get_head_commit(self, branch: Branch) -> CommitDetailSerializer:
        commit = (
            Commit.objects.filter(
                repository_id=branch.repository_id, commitid=branch.head
            )
            .defer("report")
            .first()
        )
        return CommitDetailSerializer(commit).data

    class Meta:
        model = Branch
        fields = BranchSerializer.Meta.fields + ("head_commit",)
