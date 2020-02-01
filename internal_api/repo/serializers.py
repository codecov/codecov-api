from rest_framework import serializers

from core.models import Repository, Commit

from internal_api.owner.serializers import OwnerSerializer
from internal_api.commit.serializers import (
    CommitWithFileLevelReportSerializer,
)


class RepoSerializer(serializers.ModelSerializer):
    author = OwnerSerializer()

    class Meta:
        model = Repository
        fields = (
            'repoid',
            'service_id',
            'name',
            'branch',
            'private',
            'updatestamp',
            'author',
            'active',
            'language',
            "hookid",
        )


class RepoDetailsSerializer(RepoSerializer):
    fork = RepoSerializer()
    latest_commit = serializers.SerializerMethodField(
        source="get_latest_commit")
    bot = serializers.SerializerMethodField()

    # Permissions
    can_view = serializers.SerializerMethodField()
    can_edit = serializers.SerializerMethodField()

    class Meta(RepoSerializer.Meta):
        fields = (
            'fork',
            'upload_token',
            'can_edit',
            'can_view',
            'latest_commit',
            'yaml',
            'image_token',
            'bot'
        ) + RepoSerializer.Meta.fields

    def get_bot(self, repo):
        if repo.bot:
            return repo.bot.username

    def get_latest_commit(self, repo):
        commits_queryset = repo.commits.filter(
            state=Commit.CommitStates.COMPLETE,
        ).order_by('-timestamp')

        branch_param = self.context['request'].query_params.get('branch', None)

        commits_queryset = commits_queryset.filter(branch=branch_param or repo.branch)

        commit = commits_queryset.first()
        if commit:
            return CommitWithFileLevelReportSerializer(commit).data

    def get_can_view(self, _):
        return self.context.get("can_view")

    def get_can_edit(self, _):
        return self.context.get("can_edit")

    def to_representation(self, repo):
        rep = super().to_representation(repo)
        if not rep.get("can_edit"):
            del rep["upload_token"]
        return rep


class SecretStringPayloadSerializer(serializers.Serializer):
    value = serializers.CharField(required=True)
