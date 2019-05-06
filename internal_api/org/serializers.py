from rest_framework import serializers
from internal_api.repo.models import Repository
from codecov_auth.models import Owner


class OrgOrgsSerializer(serializers.ModelSerializer):
    class Meta:
        model = Owner
        fields = ('ownerid', 'username', 'email', 'name', 'active_repos')


class OrgActiveReposSerializer(serializers.ModelSerializer):
    class Meta:
        model = Repository
        fields = ('repoid', 'name')


class OrgSerializer(serializers.ModelSerializer):
    ownerid = serializers.CharField()
    service = serializers.CharField()
    username = serializers.CharField()
    email = serializers.CharField()
    name = serializers.CharField()
    active_repos = OrgActiveReposSerializer(many=True)
    orgs = OrgOrgsSerializer(many=True)

    class Meta:
        model = Owner
        fields = ('ownerid', 'service', 'username', 'email', 'name', 'active_repos', 'orgs')