from rest_framework import serializers
from .models import Repository
from codecov_auth.models import Owner


class RepoAuthorSerializer(serializers.ModelSerializer):
    username = serializers.CharField()
    email = serializers.CharField()
    name = serializers.CharField()

    class Meta:
        model = Owner
        fields = ('username', 'email', 'name')

class RepoSerializer(serializers.ModelSerializer):
    repoid = serializers.CharField()
    service_id = serializers.CharField()
    name = serializers.CharField()
    private = serializers.BooleanField()
    updatestamp = serializers.DateTimeField()
    author = RepoAuthorSerializer()

    class Meta:
        model = Repository
        fields = '__all__'