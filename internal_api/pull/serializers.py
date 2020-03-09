from rest_framework import serializers

from core.models import Pull, Commit
from codecov_auth.models import Owner
from internal_api.owner.serializers import OwnerSerializer


class PullCommitSerializer(serializers.ModelSerializer):
    class Meta:
        model = Commit
        fields = ('totals', 'ci_passed')


class PullSerializer(serializers.ModelSerializer):
    most_recent_commiter = serializers.SerializerMethodField()
    base = serializers.SerializerMethodField()
    head = serializers.SerializerMethodField()

    def get_most_recent_commiter(self, pull):
        commit = Commit.objects.filter(commitid=pull.head, repository=pull.repository)
        if commit.exists():
            return commit.values_list('author__username', flat=True).get()

    def get_base(self, pull):
        commit = Commit.objects.filter(commitid=pull.base, repository=pull.repository)
        if commit.exists():
            return PullCommitSerializer(commit.values('totals', 'ci_passed').get()).data

    def get_head(self, pull):
        commit = Commit.objects.filter(commitid=pull.head, repository=pull.repository)
        if commit.exists():
            return PullCommitSerializer(commit.values('totals', 'ci_passed').get()).data

    class Meta:
        model = Pull
        fields = (
            'pullid',
            'title',
            'most_recent_commiter',
            'base',
            'head',
            'updatestamp',
            'state',
        )


class PullDetailSerializer(PullSerializer):
    author = OwnerSerializer()

    class Meta:
        model = Pull
        fields = PullSerializer.Meta.fields + ('author',)
