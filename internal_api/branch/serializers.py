from rest_framework import serializers
from .models import Branch
from codecov_auth.models import Owner
from internal_api.commit.models import Commit


class BranchAuthorSerializer(serializers.ModelSerializer):
    username = serializers.CharField()
    email = serializers.CharField()
    name = serializers.CharField()

    class Meta:
        model = Owner
        fields = ('username', 'email', 'name')

class BranchCommitSerializer(serializers.ModelSerializer):
    author = BranchAuthorSerializer()
    totals = serializers.JSONField()
    updatestamp = serializers.DateTimeField()

    class Meta:
        model = Commit
        fields = ('author', 'totals', 'updatestamp')

class BranchSerializer(serializers.ModelSerializer):
    name = serializers.CharField()
    head = BranchCommitSerializer()
    updatestamp = serializers.DateTimeField()
    # default = serializers.BooleanField()
    # author = BranchAuthorSerializer()
    # repository = serializers.CharField()

    class Meta:
        model = Branch
        fields = ('name', 'head', 'updatestamp')