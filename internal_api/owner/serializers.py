from rest_framework import serializers

from core.models import Repository
from codecov_auth.models import Owner


# TODO (Matt): this serializer should be coming from the repo serializer
class RepositorySerializer(serializers.ModelSerializer):
    class Meta:
        model = Repository
        fields = ('repoid', 'name')


class OwnerSerializer(serializers.ModelSerializer):
    active_repos = RepositorySerializer(many=True)
    stats = serializers.SerializerMethodField()

    def get_stats(self, obj):
        if obj.cache and 'stats' in obj.cache:
            return obj.cache['stats']

    class Meta:
        model = Owner
        fields = ('service', 'username', 'email',
            'name', 'stats', 'active_repos')


class OwnerDetailsSerializer(OwnerSerializer):
    orgs = OwnerSerializer(many=True)

    class Meta(OwnerSerializer.Meta):
        fields = OwnerSerializer.Meta.fields + ('avatar_url', 'orgs')
