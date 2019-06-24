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

    class Meta:
        model = Repository
        fields = ('repoid', 'service_id', 'name',
                  'private', 'updatestamp', 'author', 'active', 'latest_commit')
