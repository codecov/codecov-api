from rest_framework import serializers
from .models import Pull
from codecov_auth.models import Owner
from internal_api.commit.models import Commit


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
    base = PullCommitSerializer()
    head = PullCommitSerializer()
    compared_to = PullCommitSerializer()
    state = serializers.CharField()
    diff = serializers.JSONField()
    flare = serializers.JSONField()
    author = PullAuthorSerializer()

    class Meta:
        model = Pull
        fields = '__all__'