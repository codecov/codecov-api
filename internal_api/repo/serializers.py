from rest_framework import serializers

from core.models import Commit, Repository
from internal_api.commit.serializers import (
    CommitTotalsSerializer,
    CommitWithFileLevelReportSerializer,
)
from internal_api.owner.serializers import OwnerSerializer
from services.segment import SegmentService


class RepoSerializer(serializers.ModelSerializer):
    author = OwnerSerializer()

    class Meta:
        model = Repository
        read_only_fields = (
            "repoid",
            "service_id",
            "name",
            "private",
            "updatestamp",
            "author",
            "language",
            "hookid",
            "using_integration",
        )
        fields = read_only_fields + ("branch", "active", "activated",)


class RepoWithMetricsSerializer(RepoSerializer):
    latest_commit_totals = CommitTotalsSerializer()
    latest_coverage_change = serializers.FloatField()

    class Meta(RepoSerializer.Meta):
        fields = (
            "latest_commit_totals",
            "latest_coverage_change",
        ) + RepoSerializer.Meta.fields


class RepoDetailsSerializer(RepoSerializer):
    fork = RepoSerializer()
    latest_commit = serializers.SerializerMethodField(source="get_latest_commit")
    bot = serializers.SerializerMethodField()

    # Permissions
    can_view = serializers.SerializerMethodField()
    can_edit = serializers.SerializerMethodField()

    class Meta(RepoSerializer.Meta):
        read_only_fields = (
            "fork",
            "upload_token",
            "yaml",
            "image_token",
        ) + RepoSerializer.Meta.read_only_fields
        fields = (
            ("can_edit", "can_view", "latest_commit", "bot")
            + RepoSerializer.Meta.fields
            + read_only_fields
        )

    def get_bot(self, repo):
        if repo.bot:
            return repo.bot.username

    def get_latest_commit(self, repo):
        commits_queryset = (
            repo.commits.filter(state=Commit.CommitStates.COMPLETE,)
            .defer("report")
            .order_by("-timestamp")
        )

        branch_param = self.context["request"].query_params.get("branch", None)

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

    def update(self, instance, validated_data):
        # Segment tracking
        segment = SegmentService()
        if "active" in validated_data:
            if validated_data["active"] and not instance.active:
                segment.account_activated_repository(
                    self.context["request"].user.ownerid, instance
                )
            elif not validated_data["active"] and instance.active:
                segment.account_deactivated_repository(
                    self.context["request"].user.ownerid, instance
                )

        return super().update(instance, validated_data)


class SecretStringPayloadSerializer(serializers.Serializer):
    value = serializers.CharField(required=True)
