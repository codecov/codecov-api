import uuid

from rest_framework import serializers

from codecov_auth.models import Owner
from core.models import Repository
from internal_api.serializers import AuthorSerializer
from internal_api.commit.serializers import CommitWithReportSerializer, CommitWithFileLevelReportSerializer


class RepoSerializer(serializers.ModelSerializer):
    repoid = serializers.IntegerField()
    service_id = serializers.CharField()
    name = serializers.CharField()
    branch = serializers.CharField()
    private = serializers.BooleanField()
    updatestamp = serializers.DateTimeField()
    author = AuthorSerializer()
    language = serializers.CharField()
    latest_commit = CommitWithReportSerializer()

    class Meta:
        model = Repository
        fields = ('repoid', 'service_id', 'name', 'branch',
                  'private', 'updatestamp', 'author', 'active',
                  'latest_commit', 'language', 'fork')

    def update(self, instance, validated_data):
        instance.branch = validated_data.get('branch', instance.branch)
        instance.save()
        return instance


class RepoDetailsSerializer(RepoSerializer):
    fork = RepoSerializer()
    latest_commit = CommitWithFileLevelReportSerializer()

    def to_representation(self, repo):
        representation = super().to_representation(repo)
        representation['can_edit'] = self.context['can_edit']
        representation['can_view'] = self.context['can_view']
        representation['has_uploads'] = self.context['has_uploads']
        if self.context['can_edit']:
            representation['upload_token'] = repo.upload_token
        return representation


class RepoNewUploadTokenSerializer(serializers.ModelSerializer):
    upload_token = serializers.UUIDField()

    class Meta:
        model = Repository
        fields = ('upload_token',)

    def update(self, instance, validated_data):
        instance.upload_token = uuid.uuid4()
        instance.save()
        return instance
