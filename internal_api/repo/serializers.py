from rest_framework import serializers

from codecov_auth.models import Owner
from core.models import Repository
from internal_api.commit.serializers import ShortParentlessCommitSerializer
from internal_api.serializers import AuthorSerializer


class RepoSerializer(serializers.ModelSerializer):
    repoid = serializers.IntegerField()
    service_id = serializers.CharField()
    name = serializers.CharField()
    private = serializers.BooleanField()
    updatestamp = serializers.DateTimeField()
    author = AuthorSerializer()
    latest_commit = ShortParentlessCommitSerializer()
    language = serializers.CharField()
    branch = serializers.CharField()

    class Meta:
        model = Repository
        fields = ('repoid', 'service_id', 'name',
                  'private', 'updatestamp', 'author', 'active',
                  'latest_commit', 'language', 'branch', 'fork')


class RepoDetailsSerializer(RepoSerializer):
    fork = RepoSerializer()

    def to_representation(self, repo):
        representation = super().to_representation(repo)
        representation['can_edit'] = self.context['can_edit']
        representation['can_view'] = self.context['can_view']
        representation['has_uploads'] = self.context['has_uploads']
        if self.context['can_edit']:
            representation['upload_token'] = repo.upload_token
        return representation
