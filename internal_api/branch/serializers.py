from rest_framework import serializers

from core.models import Branch, Commit
from codecov_auth.models import Owner


class BranchAuthorSerializer(serializers.ModelSerializer):
    ownerid = serializers.CharField()
    username = serializers.CharField()
    email = serializers.CharField()
    name = serializers.CharField()

    class Meta:
        model = Owner
        fields = ('ownerid', 'username', 'email', 'name')


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
    # authors = BranchAuthorSerializer(many=True)
    # default = serializers.BooleanField()
    # repository = serializers.CharField()

    class Meta:
        model = Branch
        fields = ('name', 'head', 'updatestamp')
