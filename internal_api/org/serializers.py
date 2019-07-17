from rest_framework import serializers

from core.models import Repository
from codecov_auth.models import Owner


class OwnerActiveReposSerializer(serializers.ModelSerializer):
    class Meta:
        model = Repository
        fields = ('repoid', 'name')


class OwnerSerializer(serializers.ModelSerializer):
    ownerid = serializers.IntegerField()
    service = serializers.CharField()
    username = serializers.CharField()
    email = serializers.CharField()
    name = serializers.CharField()
    active_repos = OwnerActiveReposSerializer(many=True)
    stats = serializers.SerializerMethodField()

    def get_stats(self, obj):
        if obj.cache['stats']:
            return obj.cache['stats']

    class Meta:
        model = Owner
        fields = ('ownerid', 'service', 'username',
                  'email', 'name', 'stats', 'active_repos')


class OwnerListSerializer(OwnerSerializer):
    orgs = OwnerSerializer(many=True)

    class Meta:
        model = Owner
        fields = ('ownerid', 'service', 'username',
                  'email', 'name', 'stats', 'active_repos', 'orgs')
