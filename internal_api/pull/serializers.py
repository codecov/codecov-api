from rest_framework import serializers

from core.models import Pull, Commit
from codecov_auth.models import Owner
from internal_api.owner.serializers import OwnerSerializer


class PullCommitSerializer(serializers.ModelSerializer):
    author = OwnerSerializer()
    totals = serializers.JSONField()
    updatestamp = serializers.DateTimeField()

    class Meta:
        model = Commit
        fields = ('author', 'totals', 'updatestamp', 'ci_passed')


class PullSerializer(serializers.ModelSerializer):
    title = serializers.CharField()
    author = OwnerSerializer()
    base = serializers.SerializerMethodField()
    head = serializers.SerializerMethodField()
    updatestamp = serializers.DateTimeField()
    state = serializers.CharField()
    diff = serializers.JSONField()
    flare = serializers.JSONField()

    def get_base(self, pull):
        commit = Commit.objects.filter(commitid=pull.base_id, repository=pull.repository)
        if commit.exists():
            return PullCommitSerializer(commit.get()).data

    def get_head(self, pull):
        commit = Commit.objects.filter(commitid=pull.head_id, repository=pull.repository)
        if commit.exists():
            return PullCommitSerializer(commit.get()).data


    class Meta:
        model = Pull
        fields = ('pullid', 'title', 'author', 'base', 'head',
                  'compared_to', 'updatestamp', 'state', 'diff', 'flare')
