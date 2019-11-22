from rest_framework import serializers

from core.models import Repository
from internal_api.serializers import AuthorSerializer
from internal_api.commit.serializers import (
    CommitWithReportSerializer,
    CommitWithFileLevelReportSerializer,
)


class RepoSerializer(serializers.ModelSerializer):
    author = AuthorSerializer()
    latest_commit = CommitWithReportSerializer()

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
            'latest_commit',
        )


class RepoDetailsSerializer(RepoSerializer):
    fork = RepoSerializer()
    latest_commit = CommitWithFileLevelReportSerializer()

    ## Permissions
    can_view = serializers.SerializerMethodField()
    can_edit = serializers.SerializerMethodField()

    def get_can_view(self, _):
        return self.context.get("can_view")

    def get_can_edit(self, _):
        return self.context.get("can_edit")

    class Meta:
        model = Repository
        fields = (
            'fork',
            'upload_token',
            'can_edit',
            'can_view',
            'yaml',
            'image_token',
        ) + RepoSerializer.Meta.fields

    def to_representation(self, repo):
        rep = super().to_representation(repo)
        if not rep.get("can_edit"):
            del rep["upload_token"]
        return rep


class SecretStringPayloadSerializer(serializers.Serializer):
    value = serializers.CharField(required=True)
