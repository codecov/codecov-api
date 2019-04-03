from rest_framework import serializers
from .models import Branch
from codecov_auth.models import Owner


class BranchAuthorSerializer(serializers.ModelSerializer):
    username = serializers.CharField()
    email = serializers.CharField()
    name = serializers.CharField()

    class Meta:
        model = Owner
        fields = ('username', 'email', 'name')

class BranchSerializer(serializers.ModelSerializer):
    name = serializers.CharField()
    author = BranchAuthorSerializer()
    repository = serializers.CharField()
    head = serializers.CharField()
    updatestamp = serializers.DateTimeField()

    class Meta:
        model = Branch
        fields = ('name', 'head', 'updatestamp')