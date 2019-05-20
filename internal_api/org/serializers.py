from rest_framework import serializers

from core.models import Repository
from codecov_auth.models import Owner


class OrgActiveReposSerializer(serializers.ModelSerializer):
    class Meta:
        model = Repository
        fields = ('repoid', 'name')


class OrgOrgsSerializer(serializers.ModelSerializer):
    ownerid = serializers.IntegerField()
    service = serializers.CharField()
    username = serializers.CharField()
    email = serializers.CharField()
    name = serializers.CharField()
    cache = serializers.JSONField()
    active_repos = OrgActiveReposSerializer(many=True)

    class Meta:
        model = Owner
        fields = ('ownerid', 'service', 'username',
                  'email', 'name', 'cache', 'active_repos')


class OrgSerializer(serializers.ModelSerializer):
    ownerid = serializers.IntegerField()
    service = serializers.CharField()
    username = serializers.CharField()
    email = serializers.CharField()
    name = serializers.CharField()
    cache = serializers.JSONField()
    active_repos = OrgActiveReposSerializer(many=True)
    orgs = OrgOrgsSerializer(many=True)

    class Meta:
        model = Owner
        fields = ('ownerid', 'service', 'username',
                  'email', 'name', 'cache', 'active_repos', 'orgs')
