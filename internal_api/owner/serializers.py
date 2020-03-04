from rest_framework import serializers

from core.models import Repository
from codecov_auth.models import Owner


# TODO (Matt): this serializer should be coming from the repo serializer
class RepositorySerializer(serializers.ModelSerializer):
    class Meta:
        model = Repository
        fields = ('repoid', 'name')


class OwnerSerializer(serializers.ModelSerializer):
    class Meta:
        model = Owner
        fields = (
            'service',
            'username',
            'avatar_url'
        )


class OwnerDetailsSerializer(OwnerSerializer):
    active_repos = RepositorySerializer(many=True)
    orgs = OwnerSerializer(many=True)
    stats = serializers.SerializerMethodField()

    def get_stats(self, obj):
        if obj.cache and 'stats' in obj.cache:
            return obj.cache['stats']

    class Meta(OwnerSerializer.Meta):
        fields = OwnerSerializer.Meta.fields + (
            'active_repos',
            'orgs',
            'email',
            'name',
            'stats',
        )
