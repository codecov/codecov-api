from rest_framework import serializers

from .models import Pull
from internal_api.commit.models import Commit
from codecov_auth.models import Owner


class PullAuthorSerializer(serializers.ModelSerializer):
    username = serializers.CharField()
    email = serializers.CharField()
    name = serializers.CharField()

    class Meta:
        model = Owner
        fields = ('username', 'email', 'name')


class PullCommitSerializer(serializers.ModelSerializer):
    author = PullAuthorSerializer()
    totals = serializers.JSONField()
    updatestamp = serializers.DateTimeField()

    class Meta:
        model = Commit
        fields = ('author', 'totals', 'updatestamp')


class PullSerializer(serializers.ModelSerializer):
    title = serializers.CharField()
    author = PullAuthorSerializer()
    base = PullCommitSerializer()
    head = PullCommitSerializer()
    compared_to = PullCommitSerializer()
    updatestamp = serializers.DateTimeField()
    state = serializers.CharField()
    diff = serializers.JSONField()
    flare = serializers.JSONField()

    class Meta:
        model = Pull
        fields = ('title', 'author', 'base', 'head',
                  'compared_to', 'updatestamp', 'state', 'diff', 'flare')
