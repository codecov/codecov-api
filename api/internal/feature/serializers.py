from rest_framework import serializers


class FeatureIdentifierDataSerializer(serializers.Serializer):
    email = serializers.CharField(max_length=200, allow_blank=True)
    user_id = serializers.IntegerField()
    repo_id = serializers.IntegerField()
    org_id = serializers.IntegerField()


class FeatureRequestSerializer(serializers.Serializer):
    feature_flags = serializers.ListField(
        child=serializers.CharField(max_length=200), allow_empty=True
    )
    identifier_data = FeatureIdentifierDataSerializer()
