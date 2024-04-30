from rest_framework import serializers


class FeatureIdentifierDataSerializer(serializers.Serializer):
    email = serializers.CharField(max_length=200)
    user_id = serializers.CharField(max_length=200)
    repo_id = serializers.CharField(max_length=200)
    org_id = serializers.CharField(max_length=200)


class FeatureRequestSerializer(serializers.Serializer):
    feature_flags = serializers.ListField(
        child=serializers.CharField(max_length=200), allow_empty=True
    )
    identifier_data = FeatureIdentifierDataSerializer()
