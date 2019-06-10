from rest_framework import serializers

from codecov_auth.models import Owner
from core.models import Repository
from internal_api.commit.serializers import ShortParentlessCommitSerializer


class RepoAuthorSerializer(serializers.ModelSerializer):
    username = serializers.CharField()
    email = serializers.CharField()
    name = serializers.CharField()

    class Meta:
        model = Owner
        fields = ('username', 'email', 'name')


class RepoSerializer(serializers.ModelSerializer):
    repoid = serializers.IntegerField()
    service_id = serializers.CharField()
    name = serializers.CharField()
    private = serializers.BooleanField()
    updatestamp = serializers.DateTimeField()
    author = RepoAuthorSerializer()
    latest_commit = ShortParentlessCommitSerializer()

    class Meta:
        model = Repository
        fields = ('repoid', 'service_id', 'name',
                  'private', 'updatestamp', 'author', 'active', 'latest_commit')
