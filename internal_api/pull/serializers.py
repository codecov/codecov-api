from rest_framework import serializers

from core.models import Pull, Commit
from codecov_auth.models import Owner
from internal_api.serializers import AuthorSerializer


class PullCommitSerializer(serializers.ModelSerializer):
    author = AuthorSerializer()
    totals = serializers.JSONField()
    updatestamp = serializers.DateTimeField()

    class Meta:
        model = Commit
        fields = ('author', 'totals', 'updatestamp')


class PullSerializer(serializers.ModelSerializer):
    title = serializers.CharField()
    author = AuthorSerializer()
    base = PullCommitSerializer()
    head = PullCommitSerializer()
    compared_to = PullCommitSerializer()
    updatestamp = serializers.DateTimeField()
    state = serializers.CharField()
    diff = serializers.JSONField()
    flare = serializers.JSONField()

    class Meta:
        model = Pull
        fields = ('pullid', 'title', 'author', 'base', 'head',
                  'compared_to', 'updatestamp', 'state', 'diff', 'flare')
