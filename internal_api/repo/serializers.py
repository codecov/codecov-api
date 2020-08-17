from datetime import datetime

from django.db.models.functions import Trunc
from rest_framework import serializers

from core.models import Repository, Commit

from internal_api.owner.serializers import OwnerSerializer
from internal_api.commit.serializers import (
    CommitWithFileLevelReportSerializer,
    CommitSerializer,
)


class RepoSerializer(serializers.ModelSerializer):
    author = OwnerSerializer()
    latest_commit = serializers.SerializerMethodField()

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
            "activated",
            "using_integration",
            "latest_commit",
        )

    def get_latest_commit(self, repo):
        latest_commit = repo.commits.annotate(
            truncated_date=Trunc("timestamp", "day")
        ).filter(
            state=Commit.CommitStates.COMPLETE,
            branch=self.context["request"].query_params.get("branch", None) or repo.branch,
            truncated_date__lte=self.context["request"].query_params.get("before_date", None) or datetime.now()
        ).select_related('author').order_by('-timestamp').first()
        return CommitSerializer(latest_commit).data


class RepoWithMetricsSerializer(RepoSerializer):
    total_commit_count = serializers.IntegerField()
    latest_coverage_change = serializers.FloatField()

    class Meta(RepoSerializer.Meta):
        fields = (
            'total_commit_count',
            'latest_coverage_change',
        ) + RepoSerializer.Meta.fields


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
